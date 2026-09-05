from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    price: Decimal = Field(ge=0, decimal_places=2, description="monthly rent")
    description: str | None = None


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    description: str | None = None
    is_available: bool | None = None


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price: Decimal
    is_available: bool
    created_at: datetime
    updated_at: datetime


class MonthlyReport(BaseModel):
    month: int
    year: int
    currency: str
    rooms_total: int
    rooms_occupied: int
    invoices: int
    billed: Decimal
    collected: Decimal
    outstanding: Decimal
    electricity_units: Decimal
    water_units: Decimal
