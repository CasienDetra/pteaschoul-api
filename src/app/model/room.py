from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.config.base import Base


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_room_price_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # monthly rent
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenants: Mapped[list["Tenant"]] = relationship(back_populates="room")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Room {self.id} {self.name} {'vacant' if self.is_available else 'occupied'}>"
