import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.config.config import settings
from src.app.model import Role, User
from src.app.schema.user import UserCreate, UserUpdate
from src.app.utils.argon2 import hash_password

_ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


def save_image(file: UploadFile, folder: str = "users") -> str:
    """Validate then store an upload. Returns the relative path kept on the row."""
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported image type {file.content_type}; allowed: {', '.join(_ALLOWED_IMAGE_TYPES)}",
        )
    data = file.file.read(_MAX_IMAGE_BYTES + 1)
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image exceeds 5 MB")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Image is empty")

    # name from a uuid, extension from the validated content type: the client-supplied
    # filename never reaches the filesystem, so it cannot traverse out of the folder
    target = Path(settings.UPLOAD_DIR) / folder
    target.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{_ALLOWED_IMAGE_TYPES[file.content_type]}"
    (target / name).write_bytes(data)
    return f"{folder}/{name}"


def assert_email_free(db: Session, email: str, exclude_id: int | None = None) -> None:
    stmt = select(User.id).where(User.email == email.lower())
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    if db.scalars(stmt).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"Email {email} is already registered")


def create_user(db: Session, payload: UserCreate) -> User:
    assert_email_free(db, payload.email)
    user = User(
        name=payload.name,
        email=payload.email.lower(),
        password=hash_password(payload.password),
        role=payload.role,
        image=save_image(payload.image) if payload.image else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, page: int, limit: int, role: Role | None = None, q: str | None = None):
    stmt = select(User)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(User.name).like(like) | func.lower(User.email).like(like))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(User.id).offset((page - 1) * limit).limit(limit)).all()
    return items, total


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


def _assert_not_last_admin(db: Session, user: User) -> None:
    if user.role is not Role.ADMIN:
        return
    others = db.scalar(
        select(func.count()).select_from(User)
        .where(User.role == Role.ADMIN, User.is_active.is_(True), User.id != user.id)
    )
    if not others:
        raise HTTPException(status.HTTP_409_CONFLICT, "This is the last active admin; promote another one first")


def update_user(db: Session, user: User, payload: UserUpdate) -> User:
    # image is an UploadFile, not a column value — kept out of the dump and applied below
    data = payload.model_dump(exclude_unset=True, exclude={"image"})
    if "email" in data and data["email"]:
        assert_email_free(db, data["email"], exclude_id=user.id)
        data["email"] = data["email"].lower()
    if data.get("password"):
        data["password"] = hash_password(data["password"])
    else:
        data.pop("password", None)
    # losing the only admin locks everybody out of user management for good
    if data.get("role", user.role) is not Role.ADMIN or data.get("is_active") is False:
        _assert_not_last_admin(db, user)
    for field, value in data.items():
        setattr(user, field, value)
    if payload.image:
        user.image = save_image(payload.image)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User, actor: User) -> None:
    if user.id == actor.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot delete your own account")
    _assert_not_last_admin(db, user)
    db.delete(user)
    db.commit()
