import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(func.lower(User.email) == email.casefold()))

    def get_by_username(self, username: str) -> User | None:
        return self.session.scalar(
            select(User).where(func.lower(User.username) == username.casefold())
        )

    def get_by_identifier(self, identifier: str) -> User | None:
        normalized = identifier.casefold()
        return self.session.scalar(
            select(User).where(
                or_(func.lower(User.email) == normalized, func.lower(User.username) == normalized)
            )
        )

    def create(
        self, *, email: str, username: str, password_hash: str, first_name: str, last_name: str
    ) -> User:
        user = User(
            email=email,
            username=username,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
        )
        self.session.add(user)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.session.delete(user)
        self.session.commit()

    def update(self, user: User, values: dict[str, Any]) -> User:
        for field, value in values.items():
            setattr(user, field, value)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(user)
        return user
