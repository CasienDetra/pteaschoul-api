from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.app.model import InvoiceStatus


class ReadingUpdate(BaseModel):
    """Meter faces read at the end of the billed month."""

    electricity_curr: Decimal = Field(ge=0, decimal_places=2, description="kWh on the meter now")
    water_curr: Decimal = Field(ge=0, decimal_places=2, description="m3 on the meter now")


class GenerateRequest(BaseModel):
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2100)


class PaymentCreate(BaseModel):
    """What the tenant handed over.

    `amount` is denominated in `currency`, which is the base currency unless stated —
    so an existing base-currency client keeps working unchanged.
    """

    amount: Decimal = Field(gt=0, decimal_places=2, description="amount handed over, in `currency`")
    currency: str | None = Field(
        default=None, min_length=3, max_length=3,
        description="ISO code of the cash handed over; the base currency when omitted",
    )
    fx_rate: Decimal | None = Field(
        default=None, gt=0, decimal_places=6,
        description="units of `currency` per 1 base unit; the configured house rate when omitted",
    )
    method: str = Field(default="cash", max_length=30)
    note: str | None = Field(default=None, max_length=255)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: Decimal  # settled, always in base_currency — this is what moved the balance
    base_currency: str
    tendered_amount: Decimal
    tendered_currency: str
    fx_rate: Decimal
    method: str
    note: str | None
    recorded_by_id: int | None
    paid_at: datetime


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    tenant_id: int
    room_name: str | None
    tenant_name: str | None
    month: int
    year: int

    room_price: Decimal

    electricity_prev: Decimal
    electricity_curr: Decimal
    electricity_units: Decimal
    electricity_rate: Decimal
    electricity_charge: Decimal

    water_prev: Decimal
    water_curr: Decimal
    water_units: Decimal
    water_rate: Decimal
    water_charge: Decimal

    amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal

    status: InvoiceStatus
    due_date: date
    is_overdue: bool
    reading_recorded_at: datetime | None
    created_at: datetime
    paid_at: datetime | None
    payments: list[PaymentOut] = []
