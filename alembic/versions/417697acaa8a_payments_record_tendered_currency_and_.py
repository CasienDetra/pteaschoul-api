"""payments: record tendered currency and fx rate

Revision ID: 417697acaa8a
Revises: 91267668c139
Create Date: 2026-09-06 08:43:49.061929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.app.config.config import settings


# revision identifiers, used by Alembic.
revision: str = '417697acaa8a'
down_revision: Union[str, Sequence[str], None] = '91267668c139'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = ('tendered_amount', 'tendered_currency', 'fx_rate')


def upgrade() -> None:
    """Upgrade schema."""
    # added nullable, backfilled, then pinned: the model declares these NOT NULL, but rows
    # written before multi-currency have to be given a value before the constraint can hold
    op.add_column('payments', sa.Column('tendered_amount', sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column('payments', sa.Column('tendered_currency', sa.String(length=3), nullable=True))
    op.add_column('payments', sa.Column('fx_rate', sa.Numeric(precision=14, scale=6), nullable=True))

    # an older payment was taken in the only currency the system had, at par with itself.
    # Read from settings rather than hardcoded so a non-USD deployment backfills its own
    # base currency — check BASE_CURRENCY is set before running this on such a deployment.
    op.execute(
        sa.text(
            "UPDATE payments SET tendered_amount = amount, tendered_currency = :base, fx_rate = 1"
            " WHERE tendered_currency IS NULL"
        ).bindparams(base=settings.BASE_CURRENCY)
    )

    for column in COLUMNS:
        op.alter_column('payments', column, nullable=False)

    op.create_check_constraint('ck_payment_tendered_positive', 'payments', 'tendered_amount > 0')
    op.create_check_constraint('ck_payment_fx_rate_positive', 'payments', 'fx_rate > 0')


def downgrade() -> None:
    """Downgrade schema."""
    # the tender detail is lost here; `amount` survives, and since every balance was built
    # from that column the invoices still add up afterwards
    for column in reversed(COLUMNS):
        op.drop_column('payments', column)  # takes its check constraint with it
