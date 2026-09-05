"""Seeder CLI.  Run from the project root:

    uv run python -m src.app.database.index --rooms 20 --tenants 12
    uv run python -m src.app.database.index --dry-run
    uv run python -m src.app.database.index --no-clear          # add on top of existing data
"""

import argparse
import random
import sys

from sqlalchemy import text

from src.app.config.session import SessionLocal
from src.app.database.seed.billing import seed_billing, unpaid_summary
from src.app.database.seed.room import seed_rooms
from src.app.database.seed.tenant import seed_tenants
from src.app.database.seed.user import seed_users
from src.app.utils import color

# child tables first is irrelevant under CASCADE, but the order documents the graph
TABLES = ("payments", "invoices", "tenants", "rooms", "users")


def clear(db) -> None:
    db.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    db.commit()
    color.warn(f"truncated: {', '.join(TABLES)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="seed", description="Seed the rental room database")
    parser.add_argument("--rooms", type=int, default=20)
    parser.add_argument("--tenants", type=int, default=20)
    parser.add_argument("--months", type=int, default=3, help="months of billing history")
    parser.add_argument("--no-clear", action="store_true", help="keep existing rows")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    parser.add_argument("--seed", type=int, default=2026, help="RNG seed for reproducible data")
    args = parser.parse_args(argv)

    if args.dry_run:
        color.title("dry run — nothing will be written")
        if not args.no_clear:
            color.warn(f"would truncate: {', '.join(TABLES)}")
        color.info(f"would seed 4 users, {args.rooms} rooms, "
                   f"up to {args.tenants} tenants, {args.months} month(s) of billing")
        return 0

    random.seed(args.seed)
    with SessionLocal() as db:
        if not args.no_clear:
            color.title("Clearing")
            clear(db)

        color.title("Users")
        seed_users(db)

        color.title("Rooms")
        seed_rooms(db, args.rooms)

        color.title("Tenants")
        seed_tenants(db, args.tenants)

        color.title("Billing")
        seed_billing(db, args.months)

        color.title("Done")
        color.info(unpaid_summary(db))
    return 0


if __name__ == "__main__":
    sys.exit(main())
