from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.app.config.config import settings
from src.app.config.logger import get_logger, setup_logging
from src.app.config.scheduler import shutdown_scheduler, start_scheduler
from src.app.routes import api_router

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    start_scheduler()
    log.info("API ready at %s", settings.API_PREFIX)
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Rental Room API",
    description=(
        "Rooms, tenants and monthly billing. A bill is **rent + metered electricity + "
        "metered water**; the tariff and rent in force are snapshotted onto every invoice.\n\n"
        "Bills are totalled and settled in the base currency, but a tenant may hand over any "
        "currency listed at `GET /` — the payment keeps the tender and the rate applied.\n\n"
        "Log in at `POST /api/v1/login`, then paste the `access_token` into **Authorize**."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_PREFIX)
# uploaded avatars are stored as relative paths on the row; serve them from here
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR, check_dir=False), name="uploads")


@app.get("/", tags=["meta"], summary="Service info")
def root() -> dict:
    return {
        "service": "Rental Room API",
        "docs": "/docs",
        "api": settings.API_PREFIX,
        # what a tenant may hand over, and at what house rate: a client renders its
        # currency picker from this rather than hard-coding the pair
        "base_currency": settings.BASE_CURRENCY,
        "exchange_rates": settings.EXCHANGE_RATES,
    }
