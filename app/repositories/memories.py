import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.memory import Memory


class MemoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, values: dict[str, Any]) -> Memory:
        memory = Memory(**values)
        self.session.add(memory)
        self.session.commit()
        self.session.refresh(memory)
        return memory

    def list_for_journey(self, journey_id: uuid.UUID) -> list[Memory]:
        statement = (
            select(Memory)
            .options(selectinload(Memory.place))
            .where(Memory.journey_id == journey_id)
            .order_by(Memory.memory_date.asc(), Memory.created_at.asc(), Memory.id.asc())
        )
        return list(self.session.scalars(statement))

    def get_for_journey(self, journey_id: uuid.UUID, memory_id: uuid.UUID) -> Memory | None:
        return self.session.scalar(
            select(Memory)
            .options(selectinload(Memory.place))
            .where(Memory.journey_id == journey_id, Memory.id == memory_id)
        )

    def update(self, memory: Memory, values: dict[str, Any]) -> Memory:
        for field, value in values.items():
            setattr(memory, field, value)
        self.session.commit()
        self.session.refresh(memory)
        return memory

    def delete(self, memory: Memory) -> None:
        self.session.delete(memory)
        self.session.commit()
