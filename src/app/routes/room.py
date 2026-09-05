from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.app.config.session import get_db
from src.app.middleware.guard.permission import AdminUser, CurrentUser, StaffUser
from src.app.schema import Message, Page
from src.app.schema.room import MonthlyReport, RoomCreate, RoomOut, RoomUpdate
from src.app.services import room as room_service

router = APIRouter(prefix="/rooms", tags=["rooms"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
def create_room(_staff: StaffUser, db: DbSession, payload: RoomCreate) -> RoomOut:
    return room_service.create_room(db, payload)


@router.get("", response_model=Page[RoomOut], summary="List rooms with filters")
def list_rooms(
    _user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    is_available: Annotated[bool | None, Query(description="true = vacant")] = None,
    min_price: Annotated[Decimal | None, Query(ge=0)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    q: str | None = None,
) -> Page[RoomOut]:
    items, total = room_service.list_rooms(db, page, limit, is_available, min_price, max_price, q)
    return Page(items=items, total=total, page=page, limit=limit)


# declared before /{room_id} so the literal path wins
@router.get("/reports/monthly", response_model=MonthlyReport, summary="Billed vs collected for a month")
def monthly_report(
    _staff: StaffUser,
    db: DbSession,
    month: Annotated[int | None, Query(ge=1, le=12, description="defaults to the current month")] = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> MonthlyReport:
    # resolved per request, not at import: a long-running process must not report a stale month
    today = date.today()
    return room_service.monthly_report(db, month or today.month, year or today.year)


@router.get("/{room_id}", response_model=RoomOut)
def get_room(room_id: int, _user: CurrentUser, db: DbSession) -> RoomOut:
    return room_service.get_room_or_404(db, room_id)


@router.put("/{room_id}", response_model=RoomOut)
def update_room(room_id: int, _staff: StaffUser, db: DbSession, payload: RoomUpdate) -> RoomOut:
    return room_service.update_room(db, room_service.get_room_or_404(db, room_id), payload)


@router.delete("/{room_id}", response_model=Message, summary="Delete a room — admin only")
def delete_room(room_id: int, _admin: AdminUser, db: DbSession) -> Message:
    room_service.delete_room(db, room_service.get_room_or_404(db, room_id))
    return Message(message=f"Room {room_id} deleted")
