"""Importing this package registers every table on Base.metadata (alembic autogenerate)."""

from src.app.config.base import Base
from src.app.model.invoice import Invoice, InvoiceStatus, money
from src.app.model.payment import Payment
from src.app.model.room import Room
from src.app.model.tenant import Tenant
from src.app.model.user import Role, User

__all__ = ["Base", "Invoice", "InvoiceStatus", "money", "Payment", "Role", "Room", "Tenant", "User"]
