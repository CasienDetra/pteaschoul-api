"""Monthly billing: rent + metered electricity + metered water, and payments against it.

Period model
------------
An invoice for month M is created on the 1st of M and covers that month's rent up front.
Utilities are unknown at that point, so the bill opens at rent-only with both meters at
their carried-over reading. Staff read the meters at the end of M and PUT the readings,
which recomputes the total. Payment is due on INVOICE_DUE_DAY of M+1.
"""

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Select, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.app.config.config import settings
from src.app.config.logger import get_logger
from src.app.model import Invoice, InvoiceStatus, Payment, Role, Tenant, User, money

log = get_logger(__name__)


def due_date_for(month: int, year: int) -> date:
    """INVOICE_DUE_DAY of the month after the billed one, clamped to that month's length."""
    year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return date(year, month, min(settings.INVOICE_DUE_DAY, calendar.monthrange(year, month)[1]))


def recalculate(invoice: Invoice) -> Invoice:
    """rent + (electricity units x rate) + (water units x rate). The one place a total is set."""
    invoice.amount = money(invoice.room_price + invoice.electricity_charge + invoice.water_charge)
    return invoice


def sync_status(invoice: Invoice) -> Invoice:
    if invoice.amount_paid >= invoice.amount and invoice.amount > 0:
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = invoice.paid_at or datetime.now(timezone.utc)
    else:
        invoice.status = InvoiceStatus.PARTIAL if invoice.amount_paid > 0 else InvoiceStatus.PENDING
        invoice.paid_at = None
    return invoice


def previous_readings(db: Session, tenant: Tenant, month: int, year: int) -> tuple[Decimal, Decimal]:
    """Closing meters of this tenant's most recent earlier invoice, else their move-in faces.

    Scoped to the tenant, not the room: the incoming tenant of a re-let room must not
    inherit the outgoing tenant's unbilled units.
    """
    last = db.scalars(
        select(Invoice)
        .where(Invoice.tenant_id == tenant.id, tuple_(Invoice.year, Invoice.month) < tuple_(year, month))
        .order_by(Invoice.year.desc(), Invoice.month.desc())
        .limit(1)
    ).first()
    if last:
        return last.electricity_curr, last.water_curr
    return tenant.electricity_start, tenant.water_start


def generate_monthly_invoices(db: Session, month: int, year: int) -> list[Invoice]:
    """Idempotent: one invoice per occupied room per period, existing ones are left alone."""
    tenants = db.scalars(
        select(Tenant).where(Tenant.is_active.is_(True), Tenant.room_id.is_not(None))
    ).all()
    # room -> tenant already billed for this period
    already = {
        room_id: tenant_id
        for room_id, tenant_id in db.execute(
            select(Invoice.room_id, Invoice.tenant_id).where(Invoice.year == year, Invoice.month == month)
        )
    }

    created: list[Invoice] = []
    for tenant in tenants:
        if tenant.room is None:
            continue
        if tenant.room_id in already:
            if already[tenant.room_id] != tenant.id:
                # ponytail: billing is whole-month per room, so a mid-month hand-over leaves
                # the incoming tenant unbilled for that month. Logged rather than silently
                # skipped; add pro-rating (and relax uq_invoice_room_period) if that matters.
                log.warning(
                    "tenant %s (room %s) not billed for %d-%02d: the room was already invoiced "
                    "to tenant %s this period",
                    tenant.id, tenant.room_id, year, month, already[tenant.room_id],
                )
            continue
        elec, water = previous_readings(db, tenant, month, year)
        invoice = Invoice(
            room_id=tenant.room_id,
            tenant_id=tenant.id,
            month=month,
            year=year,
            room_price=money(tenant.room.price),
            electricity_rate=settings.ELECTRICITY_RATE,
            water_rate=settings.WATER_RATE,
            electricity_prev=elec,
            electricity_curr=elec,  # no consumption booked until the meters are read
            water_prev=water,
            water_curr=water,
            amount=Decimal("0"),
            amount_paid=Decimal("0"),
            status=InvoiceStatus.PENDING,
            due_date=due_date_for(month, year),
        )
        db.add(recalculate(invoice))
        created.append(invoice)

    try:
        db.commit()
    except IntegrityError:
        # ponytail: the unique (room, year, month) index is the real backstop; a second
        # concurrent trigger loses the race and is told to retry rather than double-bill.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Invoices for this period are already being created")

    log.info("generated %d invoice(s) for %d-%02d", len(created), year, month)
    return created


def record_reading(db: Session, invoice: Invoice, electricity_curr: Decimal, water_curr: Decimal) -> Invoice:
    if invoice.status is InvoiceStatus.PAID:
        raise HTTPException(status.HTTP_409_CONFLICT, "Invoice is already settled; issue an adjustment instead")
    for label, curr, prev in (
        ("electricity", electricity_curr, invoice.electricity_prev),
        ("water", water_curr, invoice.water_prev),
    ):
        if curr < prev:
            # ponytail: a physical meter rolling past its last digit also lands here.
            # Deliberately rejected rather than guessed at — add a rollover span if it happens.
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{label} reading {curr} is below the opening reading {prev}",
            )

    invoice.electricity_curr = electricity_curr
    invoice.water_curr = water_curr
    invoice.reading_recorded_at = datetime.now(timezone.utc)
    recalculate(invoice)

    if invoice.amount < invoice.amount_paid:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Corrected total {invoice.amount} is below the {invoice.amount_paid} already paid; refund first",
        )

    sync_status(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def pay_invoice(
    db: Session, invoice: Invoice, amount: Decimal, method: str, note: str | None, actor: User | None
) -> Invoice:
    if invoice.status is InvoiceStatus.PAID:
        raise HTTPException(status.HTTP_409_CONFLICT, "Invoice is already paid in full")
    amount = money(amount)
    if amount <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Payment must be positive")
    if amount > invoice.balance_due:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Payment {amount} exceeds the outstanding balance {invoice.balance_due}",
        )

    db.add(Payment(
        invoice_id=invoice.id, amount=amount, method=method, note=note,
        recorded_by_id=actor.id if actor else None,
    ))
    invoice.amount_paid = money(invoice.amount_paid + amount)
    sync_status(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def get_invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    return invoice


def visible_invoices(user: User) -> Select:
    """Tenants see only their own bills; staff and admin see everything."""
    stmt = select(Invoice)
    if user.role is Role.TENANT:
        tenant_ids = select(Tenant.id).where(Tenant.user_id == user.id)
        stmt = stmt.where(Invoice.tenant_id.in_(tenant_ids))
    return stmt
