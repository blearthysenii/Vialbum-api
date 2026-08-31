import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.memory import Memory
from app.models.user import User
from app.repositories.memories import MemoryRepository
from app.schemas.memory import MemoryBase, MemoryCreate, MemoryUpdate
from app.services.journeys import JourneyService


class MemoryService:
    def __init__(self, session: Session) -> None:
        self.memories = MemoryRepository(session)
        self.journeys = JourneyService(session)

    def create(self, user: User, journey_id: uuid.UUID, payload: MemoryBase) -> Memory:
        self.journeys.get(user, journey_id)
        values = MemoryCreate(**payload.model_dump(), journey_id=journey_id)
        return self.memories.create(values.model_dump(mode="python"))

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
        return self.memories.update(memory, payload.model_dump(exclude_unset=True, mode="python"))

    def delete(self, user: User, journey_id: uuid.UUID, memory_id: uuid.UUID) -> None:
        self.memories.delete(self.get(user, journey_id, memory_id))
