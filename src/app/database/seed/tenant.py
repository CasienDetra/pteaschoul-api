"""Tenants checked into vacant rooms, each with a login and opening meter faces."""

import random
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app.model import Room
from src.app.schema.tenant import TenantCreate
from src.app.services.tenant import create_tenant
from src.app.utils import color

FIRST = ["Sophia", "Dara", "Liam", "Chanda", "Noah", "Mony", "Ava", "Ratana",
         "Ethan", "Sreyleak", "Mia", "Vichea", "Lucas", "Bopha", "Leo", "Kanha"]
LAST = ["Sok", "Chan", "Nguyen", "Kim", "Prak", "Lim", "Heng", "Ouch",
        "Sam", "Ly", "Kong", "Meas", "Pich", "Sean", "Tan", "Yim"]


def seed_tenants(db: Session, count: int) -> int:
    vacant = db.scalars(select(Room).where(Room.is_available.is_(True)).order_by(Room.id)).all()
    wanted = min(count, len(vacant))
    if wanted < count:
        color.warn(f"only {len(vacant)} vacant room(s); seeding {wanted} tenant(s)")

    for i, room in enumerate(vacant[:wanted]):
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        create_tenant(db, TenantCreate(
            name=name,
            room_id=room.id,
            email=f"tenant{i + 1}@rental.com",
            password="tenant123",
            phone=f"0{random.randrange(10, 100)}{random.randrange(100000, 1000000)}",
            id_card=f"ID{random.randrange(100000, 999999)}",
            # meters do not start at zero on a building that has been let before
            electricity_start=Decimal(random.randrange(1000, 9000)),
            water_start=Decimal(random.randrange(50, 400)),
        ))
    color.ok(f"{wanted} tenants (login: tenant1@rental.com … password: tenant123)")
    return wanted
