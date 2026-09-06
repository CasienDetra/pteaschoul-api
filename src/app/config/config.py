from decimal import Decimal
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://postgres:admin2026@localhost:5432/db_room"

    SECRET_KEY: str = "change-me-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Utility tariffs: per kWh and per m3. Real meters and real tariffs drift,
    # so these are knobs — the rate in force is snapshotted onto every invoice.
    ELECTRICITY_RATE: Decimal = Decimal("0.25")
    WATER_RATE: Decimal = Decimal("0.60")

    # Bills are priced, totalled and settled in BASE_CURRENCY. A tenant may hand over any
    # currency listed in EXCHANGE_RATES; the tender and the rate applied are both recorded
    # on the payment, and only the converted base amount moves the invoice balance.
    BASE_CURRENCY: str = "USD"
    # units of the foreign currency per 1 BASE_CURRENCY — the house rate, not a live feed
    EXCHANGE_RATES: dict[str, Decimal] = {"KHR": Decimal("4100")}

    INVOICE_DUE_DAY: int = 10

    API_PREFIX: str = "/api/v1"
    UPLOAD_DIR: str = "uploads"
    LOG_LEVEL: str = "INFO"

    @model_validator(mode="after")
    def _normalise_currencies(self):
        """Codes are compared as upper case, so settle that here rather than at every use."""
        self.BASE_CURRENCY = self.BASE_CURRENCY.strip().upper()
        self.EXCHANGE_RATES = {
            code.strip().upper(): rate
            for code, rate in self.EXCHANGE_RATES.items()
            # the base currency is not a rate against itself; an entry for it would only
            # show up as a duplicate in the list of what the house accepts
            if code.strip().upper() != self.BASE_CURRENCY
        }
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
