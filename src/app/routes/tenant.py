from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.app.config.session import get_db
from src.app.middleware.guard.permission import CurrentUser, StaffUser
from src.app.model import Role
from src.app.schema import Page
from src.app.schema.tenant import TenantCreate, TenantOut
from src.app.services import tenant as tenant_service

router = APIRouter(prefix="/tenants", tags=["tenants"])

DbSession = Annotated[Session, Depends(get_db)]


class CheckoutResult(BaseModel):
    message: str
    tenant: TenantOut
    outstanding: Decimal


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED,
             summary="Check a tenant into a vacant room")
def create_tenant(_staff: StaffUser, db: DbSession, payload: TenantCreate) -> TenantOut:
    """Supply `email` + `password` to also issue the tenant a login for their own bills."""
    return tenant_service.create_tenant(db, payload)


@router.get("", response_model=Page[TenantOut], summary="List tenants with filters")
def list_tenants(
    _staff: StaffUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    is_active: bool | None = None,
    room_id: int | None = None,
    q: Annotated[str | None, Query(description="match name or phone")] = None,
) -> Page[TenantOut]:
    items, total = tenant_service.list_tenants(db, page, limit, is_active, room_id, q)
    return Page(items=items, total=total, page=page, limit=limit)


@router.get("/{tenant_id}", response_model=TenantOut, summary="Get one tenant")
def get_tenant(tenant_id: int, caller: CurrentUser, db: DbSession) -> TenantOut:
    tenant = tenant_service.get_tenant_or_404(db, tenant_id)
    if caller.role is Role.TENANT and tenant.user_id != caller.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return tenant


@router.delete("/{tenant_id}", response_model=CheckoutResult, summary="Check out — frees the room")
def checkout(tenant_id: int, _staff: StaffUser, db: DbSession) -> CheckoutResult:
    tenant, outstanding = tenant_service.checkout(db, tenant_service.get_tenant_or_404(db, tenant_id))
    return CheckoutResult(
        message=f"{tenant.name} checked out", tenant=TenantOut.model_validate(tenant), outstanding=outstanding
    )
