import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.config.base import Base


class Role(str, enum.Enum):
    ADMIN = "admin"
    STAFF = "staff"
    TENANT = "tenant"


# store the lowercase values, not the python member names
role_enum = SQLEnum(Role, name="user_role", values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))  # argon2 hash
    image: Mapped[str | None] = mapped_column(String(255), default=None)
    role: Mapped[Role] = mapped_column(role_enum, default=Role.STAFF, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant | None"] = relationship(  # noqa: F821
        back_populates="user", uselist=False, lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email} {self.role.value}>"
