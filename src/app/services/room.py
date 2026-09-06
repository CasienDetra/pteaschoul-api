from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.config.config import settings
from src.app.model import Invoice, Payment, Room, Tenant
from src.app.schema.room import MonthlyReport, RoomCreate, RoomUpdate, TenderLine

ZERO = Decimal("0.00")


def create_room(db: Session, payload: RoomCreate) -> Room:
    if db.scalars(select(Room.id).where(func.lower(Room.name) == payload.name.lower())).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"Room {payload.name} already exists")
    room = Room(**payload.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def list_rooms(db: Session, page: int, limit: int, is_available: bool | None = None,
               min_price: Decimal | None = None, max_price: Decimal | None = None, q: str | None = None):
    stmt = select(Room)
    if is_available is not None:
        stmt = stmt.where(Room.is_available.is_(is_available))
    if min_price is not None:
        stmt = stmt.where(Room.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Room.price <= max_price)
    if q:
        stmt = stmt.where(func.lower(Room.name).like(f"%{q.lower()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Room.name).offset((page - 1) * limit).limit(limit)).all()
    return items, total


def get_room_or_404(db: Session, room_id: int) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found")
    return room


def update_room(db: Session, room: Room, payload: RoomUpdate) -> Room:
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        clash = db.scalars(
            select(Room.id).where(func.lower(Room.name) == data["name"].lower(), Room.id != room.id)
        ).first()
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Room {data['name']} already exists")
    for field, value in data.items():
        setattr(room, field, value)
    db.commit()
    db.refresh(room)
    return room


def delete_room(db: Session, room: Room) -> None:
    occupied = db.scalars(
        select(Tenant.id).where(Tenant.room_id == room.id, Tenant.is_active.is_(True))
    ).first()
    if occupied:
        raise HTTPException(status.HTTP_409_CONFLICT, "Room has an active tenant; check them out first")
    # invoices cascade with the room, so refuse while any bill is unsettled
    unpaid = db.scalars(
        select(Invoice.id).where(Invoice.room_id == room.id, Invoice.amount_paid < Invoice.amount)
    ).first()
    if unpaid:
        raise HTTPException(status.HTTP_409_CONFLICT, "Room has unsettled invoices; they would be deleted too")
    db.delete(room)
    db.commit()


def monthly_report(db: Session, month: int, year: int) -> MonthlyReport:
    rooms_total = db.scalar(select(func.count()).select_from(Room)) or 0
    rooms_occupied = db.scalar(
        select(func.count()).select_from(Room).where(Room.is_available.is_(False))
    ) or 0
    row = db.execute(
        select(
            func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.amount), 0),
            func.coalesce(func.sum(Invoice.amount_paid), 0),
            func.coalesce(func.sum(Invoice.electricity_curr - Invoice.electricity_prev), 0),
            func.coalesce(func.sum(Invoice.water_curr - Invoice.water_prev), 0),
        ).where(Invoice.month == month, Invoice.year == year)
    ).one()
    count, billed, collected, elec, water = row
    return MonthlyReport(
        month=month, year=year, base_currency=settings.BASE_CURRENCY,
        rooms_total=rooms_total, rooms_occupied=rooms_occupied, invoices=count,
        billed=billed, collected=collected, outstanding=Decimal(billed) - Decimal(collected),
        electricity_units=elec, water_units=water,
        tendered=tender_breakdown(db, month, year),
    )


def tender_breakdown(db: Session, month: int, year: int) -> list[TenderLine]:
    """Cash actually taken this period, split by the currency it came in as.

    Joined through the invoice so the split covers the same period as `collected`, which
    it therefore sums to — that equality is what makes the cash box reconcilable.
    """
    rows = db.execute(
        select(
            Payment.tendered_currency,
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.tendered_amount), 0),
            func.coalesce(func.sum(Payment.amount), 0),
        )
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Invoice.month == month, Invoice.year == year)
        .group_by(Payment.tendered_currency)
        .order_by(Payment.tendered_currency)
    ).all()
    return [
        TenderLine(currency=code, payments=count, tendered=tendered, settled=settled)
        for code, count, tendered, settled in rows
    ]
