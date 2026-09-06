"""Invoices and payments for the last few months, built through the real billing service.

Going through the service (rather than inserting rows) means the seeded data obeys the
same arithmetic and status rules as production, and exercises them on every run.
"""

import random
from collections import Counter
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.config.config import settings
from src.app.model import Invoice, InvoiceStatus, Role, Tenant, User, money
from src.app.schema.invoice import PaymentCreate
from src.app.services import billing
from src.app.utils import color


def _tender(amount: Decimal, method: str, note: str | None = None) -> PaymentCreate:
    """Hand over `amount` of base-currency value, in a currency picked at random.

    A foreign tender is the exactly converted figure, so a seeded bill still lands on the
    status the caller intended instead of a cent short of it.
    """
    code = random.choice([*settings.EXCHANGE_RATES, *[settings.BASE_CURRENCY] * 2])
    if code == settings.BASE_CURRENCY:
        return PaymentCreate(amount=amount, method=method, note=note)
    return PaymentCreate(
        amount=money(amount * settings.EXCHANGE_RATES[code]), currency=code, method=method, note=note
    )


def _periods(months: int) -> list[tuple[int, int]]:
    """Oldest first, ending on the current month, so meter readings chain forward."""
    today = date.today()
    out = []
    for back in range(months - 1, -1, -1):
        month = today.month - back
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        out.append((year, month))
    return out


def seed_billing(db: Session, months: int = 3) -> int:
    periods = _periods(months)
    staff = db.scalars(select(User).where(User.role == Role.STAFF).limit(1)).first()

    # tenancies must predate the oldest bill for the history to make sense
    first_year, first_month = periods[0]
    for tenant in db.scalars(select(Tenant)).unique().all():
        tenant.check_in_date = date(first_year, first_month, 1)
    db.commit()

    total = paid = partial = 0
    tenders: Counter[str] = Counter()
    for year, month in periods:
        invoices = billing.generate_monthly_invoices(db, month, year)
        current = (year, month) == periods[-1]
        for invoice in invoices:
            total += 1
            if current:
                continue  # this month's meters have not been read yet
            billing.record_reading(
                db, invoice,
                invoice.electricity_prev + Decimal(random.randrange(40, 220)),
                invoice.water_prev + Decimal(random.randrange(2, 16)),
            )
            outcome = random.choices(["full", "partial", "none"], weights=[60, 25, 15])[0]
            if outcome == "none":
                continue
            if outcome == "full":
                tender = _tender(invoice.amount, "cash")
                paid += 1
            else:
                tender = _tender(money(invoice.amount / 2), "bank_transfer", "part payment")
                partial += 1
            billing.pay_invoice(db, invoice, tender, staff)
            tenders[tender.currency or settings.BASE_CURRENCY] += 1
        color.ok(f"{year}-{month:02d}: {len(invoices)} invoice(s)"
                 + (" (current month, awaiting meter readings)" if current else ""))

    color.info(f"{total} invoices — {paid} paid, {partial} partial, "
               f"{total - paid - partial} outstanding")
    color.info("tendered as " + ", ".join(f"{n} x {code}" for code, n in sorted(tenders.items())))
    return total


def unpaid_summary(db: Session) -> str:
    owed = db.scalar(
        select(func.coalesce(func.sum(Invoice.amount - Invoice.amount_paid), 0))
        .where(Invoice.status != InvoiceStatus.PAID)
    )
    return f"outstanding across all invoices: {owed}"
