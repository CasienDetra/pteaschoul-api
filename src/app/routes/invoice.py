from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.config.scheduler import scheduler
from src.app.config.session import get_db
from src.app.middleware.guard.permission import CurrentUser, StaffUser
from src.app.model import Invoice, InvoiceStatus
from src.app.schema import Page
from src.app.schema.invoice import GenerateRequest, InvoiceOut, PaymentCreate, ReadingUpdate
from src.app.services import billing

router = APIRouter(prefix="/invoices", tags=["billing"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/generate", response_model=list[InvoiceOut], status_code=status.HTTP_201_CREATED,
             summary="Run monthly billing now (same job the scheduler runs on the 1st)")
def generate(_staff: StaffUser, db: DbSession, payload: GenerateRequest | None = None) -> list[InvoiceOut]:
    """Idempotent — rooms already invoiced for the period are skipped, so it is safe to re-run."""
    today = date.today()
    payload = payload or GenerateRequest()
    return billing.generate_monthly_invoices(db, payload.month or today.month, payload.year or today.year)


@router.get("/scheduler-status", summary="Scheduler jobs and next run times")
def scheduler_status(_staff: StaffUser) -> dict:
    return {
        "running": scheduler.running,
        "jobs": [
            {"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
            for j in scheduler.get_jobs()
        ],
    }


@router.get("", response_model=Page[InvoiceOut], summary="List invoices (tenants see only their own)")
def list_invoices(
    caller: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    room_id: int | None = None,
    tenant_id: int | None = None,
    invoice_status: Annotated[InvoiceStatus | None, Query(alias="status")] = None,
    overdue: Annotated[bool | None, Query(description="true = unpaid and past the due date")] = None,
) -> Page[InvoiceOut]:
    stmt = billing.visible_invoices(caller)
    if month is not None:
        stmt = stmt.where(Invoice.month == month)
    if year is not None:
        stmt = stmt.where(Invoice.year == year)
    if room_id is not None:
        stmt = stmt.where(Invoice.room_id == room_id)
    if tenant_id is not None:
        stmt = stmt.where(Invoice.tenant_id == tenant_id)
    if invoice_status is not None:
        stmt = stmt.where(Invoice.status == invoice_status)
    if overdue is not None:
        unsettled = (Invoice.status != InvoiceStatus.PAID) & (Invoice.due_date < date.today())
        stmt = stmt.where(unsettled if overdue else ~unsettled)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Invoice.year.desc(), Invoice.month.desc(), Invoice.room_id)
        .offset((page - 1) * limit).limit(limit)
    ).unique().all()
    return Page(items=items, total=total, page=page, limit=limit)


def _visible_or_404(db: Session, caller, invoice_id: int) -> Invoice:
    """404 rather than 403 for someone else's bill: no existence leak."""
    invoice = db.scalars(billing.visible_invoices(caller).where(Invoice.id == invoice_id)).unique().first()
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    return invoice


@router.get("/{invoice_id}", response_model=InvoiceOut, summary="One bill, itemised")
def get_invoice(invoice_id: int, caller: CurrentUser, db: DbSession) -> InvoiceOut:
    return _visible_or_404(db, caller, invoice_id)


@router.put("/{invoice_id}/reading", response_model=InvoiceOut,
            summary="Record end-of-month meters — recomputes the total")
def record_reading(invoice_id: int, _staff: StaffUser, db: DbSession, payload: ReadingUpdate) -> InvoiceOut:
    invoice = billing.get_invoice_or_404(db, invoice_id)
    return billing.record_reading(db, invoice, payload.electricity_curr, payload.water_curr)


@router.post("/{invoice_id}/payments", response_model=InvoiceOut,
             summary="Take a full or partial payment")
def pay(invoice_id: int, staff: StaffUser, db: DbSession, payload: PaymentCreate) -> InvoiceOut:
    invoice = billing.get_invoice_or_404(db, invoice_id)
    return billing.pay_invoice(db, invoice, payload.amount, payload.method, payload.note, staff)
