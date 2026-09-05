from fastapi import APIRouter

from src.app.routes import auth, invoice, room, tenant, user

api_router = APIRouter()
for _router in (auth.router, user.router, room.router, tenant.router, invoice.router):
    api_router.include_router(_router)

__all__ = ["api_router"]
