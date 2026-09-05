from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status

from src.app.config.config import settings


def create_access_token(user_id: int, role: str, expires_minutes: int | None = None) -> tuple[str, int]:
    """Returns (token, expires_in_seconds). `sub` is a string per the JWT spec."""
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": expire}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, minutes * 60


def decode_token(token: str) -> dict[str, Any]:
    try:
        # algorithms is a whitelist — never read the alg out of the token header
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has expired",
                            headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token",
                            headers={"WWW-Authenticate": "Bearer"})


def verify_token(token: str) -> int:
    """Validate and return the user id carried by the token."""
    payload = decode_token(token)
    sub = payload.get("sub")
    if sub is None or not str(sub).isdigit():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token subject",
                            headers={"WWW-Authenticate": "Bearer"})
    return int(sub)
