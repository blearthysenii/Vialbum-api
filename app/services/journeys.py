import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidInputError, NotFoundError
from app.models.journey import Journey
from app.models.user import User
from app.repositories.journeys import JourneyRepository
from app.repositories.places import PlaceRepository
from app.schemas.journey import JourneyCreate, JourneyUpdate


class JourneyService:
    def __init__(self, session: Session) -> None:
        self.journeys = JourneyRepository(session)
        self.places = PlaceRepository(session)

    def create(self, user: User, payload: JourneyCreate) -> Journey:
        values = payload.model_dump(mode="python", exclude={"place"})
        if payload.place is not None:
            place = self.places.get_or_create(payload.place)
            values.update(
                place_id=place.id,
                destination=place.name,
                country=place.country,
                latitude=payload.latitude if payload.latitude is not None else place.latitude,
                longitude=payload.longitude if payload.longitude is not None else place.longitude,
            )
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
        values = payload.model_dump(exclude_unset=True, mode="python", exclude={"place"})
        if "place" in payload.model_fields_set:
            if payload.place is None:
                values.update(place_id=None, latitude=None, longitude=None)
            else:
                place = self.places.get_or_create(payload.place)
                values.update(
                    place_id=place.id,
                    destination=place.name,
                    country=place.country,
                    latitude=values.get("latitude", place.latitude),
                    longitude=values.get("longitude", place.longitude),
                )
        start_date = values.get("start_date", journey.start_date)
        end_date = values.get("end_date", journey.end_date)
        if end_date < start_date:
            raise InvalidInputError("end_date must be on or after start_date")
        latitude = values.get("latitude", journey.latitude)
        longitude = values.get("longitude", journey.longitude)
        if (latitude is None) != (longitude is None):
            raise InvalidInputError("latitude and longitude must be provided together")
        return self.journeys.update(journey, values)

    def delete(self, user: User, journey_id: uuid.UUID) -> None:
        self.journeys.delete(self.get(user, journey_id))
