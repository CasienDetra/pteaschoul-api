"""Admin + staff logins."""

from sqlalchemy.orm import Session

from src.app.model import Role
from src.app.schema.user import UserCreate
from src.app.services.user import create_user
from src.app.utils import color

ACCOUNTS = [
    ("Admin", "admin@example.com", "admin123", Role.ADMIN),
    ("John Doe", "john@rental.com", "staff123", Role.STAFF),
    ("Emma Stone", "emma@rental.com", "staff123", Role.STAFF),
    ("Mike Ross", "mike@rental.com", "staff123", Role.STAFF),
]


def seed_users(db: Session) -> None:
    for name, email, password, role in ACCOUNTS:
        create_user(db, UserCreate(name=name, email=email, password=password, role=role))
        color.ok(f"{role.value:<6} {email}  (password: {password})")
