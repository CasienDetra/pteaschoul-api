from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.config.base import Base
from src.app.config.config import settings


class Payment(Base):
    """One received payment. Kept as a ledger so partial settlements are auditable.

    `amount` is always in BASE_CURRENCY and is the only figure that moves the invoice
    balance. The `tendered_*` pair plus `fx_rate` preserve what was physically handed
    over, so a riel payment can be reconciled against the cash box at the rate that was
    actually applied on the day rather than today's house rate.
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        CheckConstraint("tendered_amount > 0", name="ck_payment_tendered_positive"),
        CheckConstraint("fx_rate > 0", name="ck_payment_fx_rate_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # riel amounts are five to seven digits, so this is wider than the base-currency column
    tendered_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tendered_currency: Mapped[str] = mapped_column(String(3))
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(14, 6))  # tendered units per 1 base unit
    method: Mapped[str] = mapped_column(String(30), default="cash")
    note: Mapped[str | None] = mapped_column(String(255), default=None)
    recorded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")  # noqa: F821

    @property
    def base_currency(self) -> str:
        """What `amount` is denominated in — surfaced so a client never has to assume it."""
        return settings.BASE_CURRENCY

    def __repr__(self) -> str:
        tender = f" tendered={self.tendered_amount} {self.tendered_currency}"
        return f"<Payment {self.id} invoice={self.invoice_id} {self.amount}{tender}>"
