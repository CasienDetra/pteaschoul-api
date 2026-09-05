from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.app.config.logger import get_logger

log = get_logger(__name__)
scheduler = BackgroundScheduler()


def run_monthly_billing() -> None:
    """Invoice every occupied room for the month that just started."""
    # imported here so the scheduler module stays free of model import order
    from src.app.config.session import SessionLocal
    from src.app.services import billing

    today = date.today()
    with SessionLocal() as db:
        created = billing.generate_monthly_invoices(db, today.month, today.year)
    log.info("monthly_billing: created %d invoice(s) for %s-%02d", len(created), today.year, today.month)


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        run_monthly_billing,
        CronTrigger(day=1, hour=2, minute=0),
        id="monthly_billing",
        replace_existing=True,
        coalesce=True,
        # ponytail: a restart that straddles the 1st past this window skips the run.
        # Generation is idempotent, so POST /billing/generate covers it; swap in a
        # persistent jobstore if unattended catch-up matters.
        misfire_grace_time=6 * 3600,
    )
    scheduler.start()
    log.info("scheduler started with jobs: %s", [j.id for j in scheduler.get_jobs()])


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
