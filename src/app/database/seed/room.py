"""Rooms across three floors with varied rent."""

import random
from decimal import Decimal

from sqlalchemy.orm import Session

from src.app.schema.room import RoomCreate
from src.app.services.room import create_room
from src.app.utils import color

SIZES = [
    ("Studio", Decimal("120")),
    ("One bedroom", Decimal("180")),
    ("Two bedroom", Decimal("260")),
    ("Corner suite", Decimal("340")),
]


def seed_rooms(db: Session, count: int) -> int:
    for i in range(count):
        floor, number = divmod(i, 10)
        kind, base = random.choice(SIZES)
        price = base + Decimal(random.randrange(0, 41, 5))
        create_room(db, RoomCreate(
            name=f"{chr(ord('A') + floor)}-{floor + 1}{number:02d}",
            price=price,
            description=f"{kind}, floor {floor + 1}",
        ))
    color.ok(f"{count} rooms")
    return count
