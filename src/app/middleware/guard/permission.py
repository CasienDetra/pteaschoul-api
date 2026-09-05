from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.app.config.session import get_db
from src.app.middleware.jwt_service import verify_token
from src.app.model import Role, User

bearer_scheme = HTTPBearer(description="Paste the access_token from POST /api/v1/login")


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the bearer token to a live user row.

    The role is re-read from the DB rather than trusted from the token claim, so a
    demotion or deactivation takes effect immediately instead of at token expiry.
    """
    user = db.get(User, verify_token(creds.credentials))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer active",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_roles(*roles: Role):
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            allowed = ", ".join(r.value for r in roles)
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {allowed}")
        return user

    return dependency


class PermissionGuard:
    """Route dependencies. Use as `user = Depends(PermissionGuard.admin_only)`."""

    authenticated = staticmethod(get_current_user)
    admin_only = staticmethod(require_roles(Role.ADMIN))
    staff_only = staticmethod(require_roles(Role.ADMIN, Role.STAFF))


CurrentUser = Annotated[User, Depends(PermissionGuard.authenticated)]
AdminUser = Annotated[User, Depends(PermissionGuard.admin_only)]
StaffUser = Annotated[User, Depends(PermissionGuard.staff_only)]
