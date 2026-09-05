from datetime import datetime

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.app.model import Role


class UserCreate(BaseModel):
    """Sent as multipart/form-data — `image` is optional and travels in the same request."""

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.STAFF
    image: UploadFile | None = Field(default=None, description="jpeg/png/webp, max 5 MB")


class UserUpdate(BaseModel):
    """Also multipart/form-data. Omit a field to leave it untouched."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: Role | None = None
    is_active: bool | None = None
    image: UploadFile | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: Role
    image: str | None
    is_active: bool
    created_at: datetime
