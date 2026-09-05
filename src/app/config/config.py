from decimal import Decimal
from functools import lru_cache

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
    CURRENCY: str = "USD"
    INVOICE_DUE_DAY: int = 10

    API_PREFIX: str = "/api/v1"
    UPLOAD_DIR: str = "uploads"
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
