import uuid

from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.memory import MemoryCreate, MemoryRead, MemoryUpdate
from app.services.memories import MemoryService

router = APIRouter(prefix="/journeys/{journey_id}/memories", tags=["memories"])


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(
    journey_id: uuid.UUID,
    payload: MemoryCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> MemoryRead:
    return MemoryRead.model_validate(
        MemoryService(session).create(current_user, journey_id, payload)
    )


@router.get("", response_model=list[MemoryRead])
def list_memories(
    journey_id: uuid.UUID, current_user: CurrentUser, session: DatabaseSession
) -> list[MemoryRead]:
    return [
        MemoryRead.model_validate(memory)
        for memory in MemoryService(session).list(current_user, journey_id)
    ]


@router.get("/{memory_id}", response_model=MemoryRead)
def get_memory(
    journey_id: uuid.UUID, memory_id: uuid.UUID, current_user: CurrentUser, session: DatabaseSession
) -> MemoryRead:
    return MemoryRead.model_validate(
        MemoryService(session).get(current_user, journey_id, memory_id)
    )


@router.patch("/{memory_id}", response_model=MemoryRead)
def update_memory(
    journey_id: uuid.UUID,
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> MemoryRead:
    return MemoryRead.model_validate(
        MemoryService(session).update(current_user, journey_id, memory_id, payload)
    )


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    journey_id: uuid.UUID, memory_id: uuid.UUID, current_user: CurrentUser, session: DatabaseSession
) -> Response:
    MemoryService(session).delete(current_user, journey_id, memory_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
