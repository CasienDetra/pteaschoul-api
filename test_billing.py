"""The one check that matters: the money math.

    uv run python test_billing.py     # or: uv run pytest test_billing.py

No DB and no fixtures — Invoice totals are computed from plain in-memory values, so
this fails the moment the billing arithmetic, the rounding, the status transitions or
the currency conversion drift.
"""

from contextlib import contextmanager
from datetime import date
from decimal import Decimal

from fastapi import HTTPException

from src.app.config.config import settings
from src.app.model import Invoice, InvoiceStatus, money
from src.app.services.billing import due_date_for, recalculate, resolve_tender, sync_status


def make(rent="200.00", e_prev="1000", e_curr="1150", w_prev="40", w_curr="49",
         e_rate="0.25", w_rate="0.60", paid="0") -> Invoice:
    return Invoice(
        room_id=1, tenant_id=1, month=3, year=2026,
        room_price=Decimal(rent),
        electricity_rate=Decimal(e_rate), water_rate=Decimal(w_rate),
        electricity_prev=Decimal(e_prev), electricity_curr=Decimal(e_curr),
        water_prev=Decimal(w_prev), water_curr=Decimal(w_curr),
        amount=Decimal("0"), amount_paid=Decimal(paid),
        status=InvoiceStatus.PENDING, due_date=date(2026, 4, 10),
    )


@contextmanager
def rates(**table: str):
    """Swap in a known rate table: these checks must not ride on the deployment's own."""
    original = settings.EXCHANGE_RATES
    settings.EXCHANGE_RATES = {code: Decimal(value) for code, value in table.items()}
    try:
        yield
    finally:
        settings.EXCHANGE_RATES = original


def refused(fn, *args) -> str:
    """Call `fn`, assert it was rejected as unprocessable, and hand back the reason given."""
    try:
        fn(*args)
    except HTTPException as exc:
        assert exc.status_code == 422, exc.status_code
        return exc.detail
    raise AssertionError(f"{fn.__name__}{args} should have been refused")


def test_total_is_rent_plus_metered_utilities():
    inv = recalculate(make())
    assert inv.electricity_units == Decimal("150")
    assert inv.water_units == Decimal("9")
    assert inv.electricity_charge == Decimal("37.50")  # 150 x 0.25
    assert inv.water_charge == Decimal("5.40")  # 9 x 0.60
    assert inv.amount == Decimal("242.90")  # 200 + 37.50 + 5.40
    assert inv.amount == inv.room_price + inv.electricity_charge + inv.water_charge


def test_zero_consumption_bills_rent_only():
    inv = recalculate(make(e_curr="1000", w_curr="40"))
    assert inv.electricity_units == Decimal("0")
    assert inv.amount == Decimal("200.00")


def test_rounding_is_half_up_not_bankers():
    # 1 unit x 0.1250 = 0.1250 exactly: half-up gives 0.13, half-even would give 0.12
    assert money(Decimal("0.125")) == Decimal("0.13")
    inv = recalculate(make(rent="0", e_prev="0", e_curr="1", e_rate="0.1250",
                           w_prev="0", w_curr="0"))
    assert inv.electricity_charge == Decimal("0.13")
    assert inv.amount == Decimal("0.13")


def test_fractional_meters_and_cents_stay_exact():
    # a float implementation drifts here; Decimal must land on the cent
    inv = recalculate(make(rent="149.99", e_prev="0", e_curr="0.10", e_rate="0.1000",
                           w_prev="0", w_curr="0.20", w_rate="0.1000"))
    assert inv.electricity_charge == Decimal("0.01")
    assert inv.water_charge == Decimal("0.02")
    assert inv.amount == Decimal("150.02")


def test_status_walks_pending_to_partial_to_paid():
    inv = recalculate(make())  # 242.90 due
    assert sync_status(inv).status is InvoiceStatus.PENDING
    assert inv.paid_at is None

    inv.amount_paid = Decimal("100.00")
    assert sync_status(inv).status is InvoiceStatus.PARTIAL
    assert inv.balance_due == Decimal("142.90")
    assert inv.paid_at is None

    inv.amount_paid = inv.amount
    assert sync_status(inv).status is InvoiceStatus.PAID
    assert inv.balance_due == Decimal("0.00")
    assert inv.paid_at is not None


def test_reread_meters_recompute_the_total_and_reopen_status():
    inv = recalculate(make(paid="242.90"))
    sync_status(inv)
    assert inv.status is InvoiceStatus.PAID

    inv.electricity_curr = Decimal("1300")  # corrected upward: 300 kWh
    recalculate(inv)
    sync_status(inv)
    assert inv.amount == Decimal("280.40")  # 200 + 75.00 + 5.40
    assert inv.status is InvoiceStatus.PARTIAL
    assert inv.paid_at is None
    assert inv.balance_due == Decimal("37.50")


def test_overdue_only_applies_to_unsettled_bills():
    inv = recalculate(make())
    inv.due_date = date(2020, 1, 1)
    sync_status(inv)
    assert inv.is_overdue is True

    inv.amount_paid = inv.amount
    sync_status(inv)
    assert inv.is_overdue is False


def test_a_base_currency_tender_passes_straight_through():
    tendered, code, rate, settled = resolve_tender(Decimal("50.00"))
    assert code == settings.BASE_CURRENCY
    assert rate == Decimal("1")
    assert tendered == settled == Decimal("50.00")


def test_a_riel_tender_converts_to_the_base_currency():
    with rates(KHR="4100"):
        tendered, code, rate, settled = resolve_tender(Decimal("200000"), "khr")  # lowercase too
    assert (tendered, code, rate) == (Decimal("200000.00"), "KHR", Decimal("4100"))
    assert settled == Decimal("48.78")  # 200000 / 4100 = 48.7804...


def test_a_full_riel_tender_clears_the_bill_to_the_cent():
    inv = recalculate(make())  # 242.90 due
    with rates(KHR="4100"):
        *_, settled = resolve_tender(inv.amount * Decimal("4100"), "KHR")
    assert settled == inv.amount

    inv.amount_paid = settled
    assert sync_status(inv).status is InvoiceStatus.PAID
    assert inv.balance_due == Decimal("0.00")


def test_riel_conversion_rounds_half_up_like_every_other_total():
    with rates(KHR="4100"):
        *_, settled = resolve_tender(Decimal("512.50"), "KHR")  # 512.50 / 4100 = 0.125 exactly
    assert settled == Decimal("0.13")


def test_the_rate_actually_given_beats_the_house_rate():
    # the cashier settled at 4000 that day; the ledger has to record what was really applied
    with rates(KHR="4100"):
        _, _, rate, settled = resolve_tender(Decimal("200000"), "KHR", Decimal("4000"))
    assert rate == Decimal("4000")
    assert settled == Decimal("50.00")


def test_an_unaccepted_currency_is_refused():
    with rates(KHR="4100"):
        detail = refused(resolve_tender, Decimal("100"), "EUR")
    assert "EUR" in detail and "KHR" in detail  # the refusal lists what it will take


def test_riel_dust_that_rounds_to_nothing_is_refused():
    with rates(KHR="4100"):
        detail = refused(resolve_tender, Decimal("1"), "KHR")  # 1 riel is 0.0002 of a dollar
    assert "0.00" in detail


def test_a_rate_on_a_base_currency_tender_is_refused():
    # silently dropping it would hide a client that has its currencies muddled
    detail = refused(resolve_tender, Decimal("50.00"), settings.BASE_CURRENCY, Decimal("4100"))
    assert "fx_rate" in detail


def test_currency_config_is_normalised_case_insensitively():
    from src.app.config.config import Settings

    configured = Settings(BASE_CURRENCY="usd", EXCHANGE_RATES={"khr": "4100", "Usd": "1"})
    assert configured.BASE_CURRENCY == "USD"
    assert configured.EXCHANGE_RATES == {"KHR": Decimal("4100")}  # no rate against itself


def test_due_date_rolls_into_the_following_month():
    assert due_date_for(3, 2026) == date(2026, 4, 10)  # INVOICE_DUE_DAY default
    assert due_date_for(12, 2026) == date(2027, 1, 10)  # year boundary


def test_due_date_clamps_to_short_months():
    from src.app.config.config import settings

    original = settings.INVOICE_DUE_DAY
    settings.INVOICE_DUE_DAY = 31
    try:
        assert due_date_for(1, 2026) == date(2026, 2, 28)  # february, not the 31st
        assert due_date_for(1, 2028) == date(2028, 2, 29)  # leap year
    finally:
        settings.INVOICE_DUE_DAY = original


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
            passed += 1
    print(f"\n{passed} checks passed")
