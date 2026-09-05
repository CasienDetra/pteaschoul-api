from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app.config.logger import get_logger
from src.app.middleware.jwt_service import create_access_token
from src.app.model import User
from src.app.schema.auth import TokenResponse
from src.app.utils.argon2 import hash_password, verify_password
from src.app.utils.device_tracker import track

log = get_logger(__name__)

# Verified against when the email is unknown, so a miss costs the same time as a wrong
# password and the response cannot be used to enumerate accounts.
_DUMMY_HASH = hash_password("argon2-timing-equaliser")


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalars(select(User).where(User.email == email.lower())).first()
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not verify_password(password, user.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    return user


def login(db: Session, request: Request, email: str, password: str) -> TokenResponse:
    user = authenticate(db, email, password)
    token, expires_in = create_access_token(user.id, user.role.value)
    info = track(request)
    log.info("login: user=%s role=%s ip=%s %s/%s",
             user.email, user.role.value, info["ip"], info["os"], info["browser"])
    return TokenResponse(access_token=token, expires_in=expires_in, user=user, info=info)


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.password = hash_password(new)
    db.commit()
