import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidInputError, NotFoundError
from app.models.memory import Memory
from app.models.user import User
from app.repositories.memories import MemoryRepository
from app.repositories.places import PlaceRepository
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.services.journeys import JourneyService


class MemoryService:
    def __init__(self, session: Session) -> None:
        self.memories = MemoryRepository(session)
        self.places = PlaceRepository(session)
        self.journeys = JourneyService(session)

    def create(self, user: User, journey_id: uuid.UUID, payload: MemoryCreate) -> Memory:
        self.journeys.get(user, journey_id)
        values = payload.model_dump(mode="python", exclude={"place"})
        values["journey_id"] = journey_id
        if payload.place is not None:
            place = self.places.get_or_create(payload.place)
            values.update(
                place_id=place.id,
                latitude=payload.latitude if payload.latitude is not None else place.latitude,
                longitude=payload.longitude if payload.longitude is not None else place.longitude,
            )
        return self.memories.create(values)

    def list(self, user: User, journey_id: uuid.UUID) -> list[Memory]:
        self.journeys.get(user, journey_id)
        return self.memories.list_for_journey(journey_id)

    def get(self, user: User, journey_id: uuid.UUID, memory_id: uuid.UUID) -> Memory:
        self.journeys.get(user, journey_id)
        memory = self.memories.get_for_journey(journey_id, memory_id)
        if memory is None:
            raise NotFoundError("Memory not found")
        return memory

    def update(
        self, user: User, journey_id: uuid.UUID, memory_id: uuid.UUID, payload: MemoryUpdate
    ) -> Memory:
        memory = self.get(user, journey_id, memory_id)
        values = payload.model_dump(exclude_unset=True, mode="python", exclude={"place"})
        if "place" in payload.model_fields_set:
            if payload.place is None:
                values.update(place_id=None, latitude=None, longitude=None)
            else:
                place = self.places.get_or_create(payload.place)
                values.update(
                    place_id=place.id,
                    latitude=values.get("latitude", place.latitude),
                    longitude=values.get("longitude", place.longitude),
                )
        latitude = values.get("latitude", memory.latitude)
        longitude = values.get("longitude", memory.longitude)
        if (latitude is None) != (longitude is None):
            raise InvalidInputError("latitude and longitude must be provided together")
        return self.memories.update(memory, values)

    def delete(self, user: User, journey_id: uuid.UUID, memory_id: uuid.UUID) -> None:
        self.memories.delete(self.get(user, journey_id, memory_id))
