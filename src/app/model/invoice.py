import enum
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import (
    CheckConstraint, Date, DateTime, Enum as SQLEnum, ForeignKey, Index, Numeric, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.config.base import Base

CENTS = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round half-up to cents. Every amount that hits the DB goes through here."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"


status_enum = SQLEnum(InvoiceStatus, name="invoice_status", values_callable=lambda e: [m.value for m in e])


class Invoice(Base):
    """One month of charges for one room: rent + metered electricity + metered water.

    Rent and both tariffs are snapshotted at generation time so a reissued bill from
    last March still adds up after this year's price change.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        # generation is idempotent because of this: one bill per room per month
        Index("uq_invoice_room_period", "room_id", "year", "month", unique=True),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_invoice_month"),
        CheckConstraint("electricity_curr >= electricity_prev", name="ck_invoice_elec_forward"),
        CheckConstraint("water_curr >= water_prev", name="ck_invoice_water_forward"),
        CheckConstraint("amount_paid >= 0 AND amount_paid <= amount", name="ck_invoice_paid_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    month: Mapped[int] = mapped_column()
    year: Mapped[int] = mapped_column()

    room_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    electricity_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4))  # per kWh
    water_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4))  # per m3

    electricity_prev: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    electricity_curr: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    water_prev: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    water_curr: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    reading_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    status: Mapped[InvoiceStatus] = mapped_column(status_enum, default=InvoiceStatus.PENDING, index=True)

    due_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    room: Mapped["Room"] = relationship(lazy="joined")  # noqa: F821
    tenant: Mapped["Tenant"] = relationship(lazy="joined")  # noqa: F821
    payments: Mapped[list["Payment"]] = relationship(  # noqa: F821
        back_populates="invoice", lazy="selectin", cascade="all, delete-orphan"
    )

    # --- derived bill lines: never stored, so they cannot drift from the readings ---
    @property
    def electricity_units(self) -> Decimal:
        return self.electricity_curr - self.electricity_prev

    @property
    def water_units(self) -> Decimal:
        return self.water_curr - self.water_prev

    @property
    def electricity_charge(self) -> Decimal:
        return money(self.electricity_units * self.electricity_rate)

    @property
    def water_charge(self) -> Decimal:
        return money(self.water_units * self.water_rate)

    @property
    def balance_due(self) -> Decimal:
        return money(self.amount - self.amount_paid)

    @property
    def is_overdue(self) -> bool:
        return self.status is not InvoiceStatus.PAID and self.due_date < date.today()

    # both relations are eager-loaded, so these are free labels for the printed bill
    @property
    def room_name(self) -> str | None:
        return self.room.name if self.room else None

    @property
    def tenant_name(self) -> str | None:
        return self.tenant.name if self.tenant else None

    def __repr__(self) -> str:
        return f"<Invoice {self.id} room={self.room_id} {self.year}-{self.month:02d} {self.amount} {self.status.value}>"
