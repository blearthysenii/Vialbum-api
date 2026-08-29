import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.journey import Journey


class JourneyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, user_id: uuid.UUID, values: dict[str, Any]) -> Journey:
        journey = Journey(user_id=user_id, **values)
        self.session.add(journey)
        self.session.commit()
        self.session.refresh(journey)
        return journey

    def list_for_user(self, user_id: uuid.UUID) -> list[Journey]:
        statement = (
            select(Journey)
            .where(Journey.user_id == user_id)
            .order_by(Journey.created_at.desc(), Journey.id.desc())
        )
        return list(self.session.scalars(statement))

    def get_for_user(self, journey_id: uuid.UUID, user_id: uuid.UUID) -> Journey | None:
        statement = select(Journey).where(Journey.id == journey_id, Journey.user_id == user_id)
        return self.session.scalar(statement)

    def update(self, journey: Journey, values: dict[str, Any]) -> Journey:
        for field, value in values.items():
            setattr(journey, field, value)
        self.session.commit()
        self.session.refresh(journey)
        return journey

    def delete(self, journey: Journey) -> None:
        self.session.delete(journey)
        self.session.commit()
