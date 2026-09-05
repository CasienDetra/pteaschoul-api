from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.model import Invoice, Role, Tenant, User
from src.app.schema.tenant import TenantCreate
from src.app.services.room import get_room_or_404
from src.app.services.user import assert_email_free
from src.app.utils.argon2 import hash_password


def create_tenant(db: Session, payload: TenantCreate) -> Tenant:
    """Check a tenant into a vacant room, optionally issuing them a login."""
    room = get_room_or_404(db, payload.room_id)
    taken = db.scalars(
        select(Tenant.id).where(Tenant.room_id == room.id, Tenant.is_active.is_(True))
    ).first()
    if taken or not room.is_available:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Room {room.name} is already occupied")

    login: User | None = None
    if payload.password:
        assert_email_free(db, payload.email)
        login = User(
            name=payload.name,
            email=payload.email.lower(),
            password=hash_password(payload.password),
            role=Role.TENANT,
        )
        db.add(login)
        db.flush()  # need the id before linking

    tenant = Tenant(
        name=payload.name,
        room_id=room.id,
        user_id=login.id if login else None,
        email=payload.email.lower() if payload.email else None,
        phone=payload.phone,
        id_card=payload.id_card,
        check_in_date=payload.check_in_date or date.today(),
        electricity_start=payload.electricity_start,
        water_start=payload.water_start,
    )
    room.is_available = False
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def list_tenants(db: Session, page: int, limit: int, is_active: bool | None = None,
                 room_id: int | None = None, q: str | None = None):
    stmt = select(Tenant)
    if is_active is not None:
        stmt = stmt.where(Tenant.is_active.is_(is_active))
    if room_id is not None:
        stmt = stmt.where(Tenant.room_id == room_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Tenant.name).like(like) | func.lower(Tenant.phone).like(like))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Tenant.id).offset((page - 1) * limit).limit(limit)).unique().all()
    return items, total


def get_tenant_or_404(db: Session, tenant_id: int) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return tenant


def checkout(db: Session, tenant: Tenant) -> tuple[Tenant, Decimal]:
    """Free the room and disable the login. Returns the tenant and what they still owe.

    The tenancy row and its invoices are kept, so leaving with a balance is recorded
    rather than erased.
    """
    if not tenant.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tenant is already checked out")
    outstanding = db.scalar(
        select(func.coalesce(func.sum(Invoice.amount - Invoice.amount_paid), 0))
        .where(Invoice.tenant_id == tenant.id)
    )
    tenant.is_active = False
    tenant.check_out_date = date.today()
    if tenant.room:
        tenant.room.is_available = True
    if tenant.user:
        tenant.user.is_active = False
    db.commit()
    db.refresh(tenant)
    return tenant, Decimal(outstanding or 0)
