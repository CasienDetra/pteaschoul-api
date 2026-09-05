from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.config.base import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        # One active tenant per room, one active tenancy per login — enforced in the DB,
        # partial so checked-out rows keep their history without blocking the next tenant.
        Index("uq_active_tenant_room", "room_id", unique=True, postgresql_where=text("is_active")),
        Index("uq_active_tenant_user", "user_id", unique=True, postgresql_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), default=None)

    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    id_card: Mapped[str | None] = mapped_column(String(60), default=None)
    photo: Mapped[str | None] = mapped_column(String(255), default=None)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    check_in_date: Mapped[date] = mapped_column(Date, default=date.today)
    check_out_date: Mapped[date | None] = mapped_column(Date, default=None)

    # Meter faces at move-in. Without these the first bill would charge the tenant for
    # every unit the previous occupants ever used.
    electricity_start: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    water_start: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User | None"] = relationship(back_populates="tenant", lazy="joined")  # noqa: F821
    room: Mapped["Room | None"] = relationship(back_populates="tenants", lazy="joined")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Tenant {self.id} {self.name} room={self.room_id} active={self.is_active}>"
