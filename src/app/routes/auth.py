from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, status
from sqlalchemy.orm import Session

from src.app.config.session import get_db
from src.app.middleware.guard.permission import CurrentUser
from src.app.schema import Message
from src.app.schema.auth import LoginRequest, TokenResponse
from src.app.schema.user import UserOut
from src.app.services import auth as auth_service

router = APIRouter(tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/login", response_model=TokenResponse, summary="Log in (admin, staff or tenant)")
def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    """The only open endpoint. Tenants use the same route as staff — role comes off the row."""
    return auth_service.login(db, request, payload.email, payload.password)


@router.get("/me", response_model=UserOut, summary="Who am I")
def me(user: CurrentUser) -> UserOut:
    return user


@router.post("/me/password", response_model=Message, status_code=status.HTTP_200_OK)
def change_password(
    user: CurrentUser,
    db: DbSession,
    current_password: Annotated[str, Body(min_length=1)],
    new_password: Annotated[str, Body(min_length=8, max_length=128)],
) -> Message:
    auth_service.change_password(db, user, current_password, new_password)
    return Message(message="Password updated")
