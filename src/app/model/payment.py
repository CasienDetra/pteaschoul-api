from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.config.base import Base


class Payment(Base):
    """One received payment. Kept as a ledger so partial settlements are auditable."""

    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payment_amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    method: Mapped[str] = mapped_column(String(30), default="cash")
    note: Mapped[str | None] = mapped_column(String(255), default=None)
    recorded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Payment {self.id} invoice={self.invoice_id} {self.amount}>"
