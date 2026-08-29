import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidInputError, NotFoundError
from app.models.journey import Journey
from app.models.user import User
from app.repositories.journeys import JourneyRepository
from app.schemas.journey import JourneyCreate, JourneyUpdate


class JourneyService:
    def __init__(self, session: Session) -> None:
        self.journeys = JourneyRepository(session)

    def create(self, user: User, payload: JourneyCreate) -> Journey:
        values = payload.model_dump(mode="python")
        return self.journeys.create(user_id=user.id, values=values)

    def list(self, user: User) -> list[Journey]:
        return self.journeys.list_for_user(user.id)

    def get(self, user: User, journey_id: uuid.UUID) -> Journey:
        journey = self.journeys.get_for_user(journey_id, user.id)
        if journey is None:
            raise NotFoundError("Journey not found")
        return journey

    def update(self, user: User, journey_id: uuid.UUID, payload: JourneyUpdate) -> Journey:
        journey = self.get(user, journey_id)
        values = payload.model_dump(exclude_unset=True, mode="python")
        start_date = values.get("start_date", journey.start_date)
        end_date = values.get("end_date", journey.end_date)
        if end_date < start_date:
            raise InvalidInputError("end_date must be on or after start_date")
        return self.journeys.update(journey, values)

    def delete(self, user: User, journey_id: uuid.UUID) -> None:
        self.journeys.delete(self.get(user, journey_id))
