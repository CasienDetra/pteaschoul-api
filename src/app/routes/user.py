from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.app.config.session import get_db
from src.app.middleware.guard.permission import AdminUser, CurrentUser, StaffUser
from src.app.model import Role
from src.app.schema import Message, Page
from src.app.schema.user import UserCreate, UserOut, UserUpdate
from src.app.services import user as user_service

router = APIRouter(prefix="/users", tags=["users"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             summary="Create a staff (or admin) account — admin only")
def create_user(_admin: AdminUser, db: DbSession, payload: Annotated[UserCreate, Form()]) -> UserOut:
    """Send as multipart/form-data. Default role is `staff`; pass `role=admin` for another admin."""
    return user_service.create_user(db, payload)


@router.get("", response_model=Page[UserOut], summary="List users")
def list_users(
    _staff: StaffUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    role: Role | None = None,
    q: Annotated[str | None, Query(description="match name or email")] = None,
) -> Page[UserOut]:
    items, total = user_service.list_users(db, page, limit, role, q)
    return Page(items=items, total=total, page=page, limit=limit)


@router.get("/{user_id}", response_model=UserOut, summary="Get one user")
def get_user(user_id: int, caller: CurrentUser, db: DbSession) -> UserOut:
    if caller.role is Role.TENANT and caller.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tenants may only read their own account")
    return user_service.get_user_or_404(db, user_id)


@router.put("/{user_id}", response_model=UserOut, summary="Update a user — admin only")
def update_user(
    user_id: int, _admin: AdminUser, db: DbSession, payload: Annotated[UserUpdate, Form()]
) -> UserOut:
    user = user_service.get_user_or_404(db, user_id)
    return user_service.update_user(db, user, payload)


@router.delete("/{user_id}", response_model=Message, summary="Delete a user — admin only")
def delete_user(user_id: int, admin: AdminUser, db: DbSession) -> Message:
    user = user_service.get_user_or_404(db, user_id)
    user_service.delete_user(db, user, admin)
    return Message(message=f"User {user_id} deleted")
