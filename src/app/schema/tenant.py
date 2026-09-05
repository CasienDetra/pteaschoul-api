from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from src.app.schema.room import RoomOut


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    room_id: int
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    id_card: str | None = Field(default=None, max_length=60)
    check_in_date: date | None = None

    # supply both to give the tenant a login ("room login")
    password: str | None = Field(default=None, min_length=8, max_length=128)

    electricity_start: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    water_start: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)

    @model_validator(mode="after")
    def _login_needs_email(self):
        if self.password and not self.email:
            raise ValueError("email is required when a password is set (it is the login id)")
        return self


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr | None
    phone: str | None
    id_card: str | None
    photo: str | None
    room_id: int | None
    user_id: int | None
    is_active: bool
    check_in_date: date
    check_out_date: date | None
    electricity_start: Decimal
    water_start: Decimal
    created_at: datetime
    room: RoomOut | None = None
