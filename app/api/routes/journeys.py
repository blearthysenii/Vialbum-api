import uuid

from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.journey import JourneyCreate, JourneyRead, JourneyUpdate
from app.services.journeys import JourneyService

router = APIRouter(prefix="/journeys", tags=["journeys"])


@router.post("", response_model=JourneyRead, status_code=status.HTTP_201_CREATED)
def create_journey(
    payload: JourneyCreate, current_user: CurrentUser, session: DatabaseSession
) -> JourneyRead:
    return JourneyRead.model_validate(JourneyService(session).create(current_user, payload))


@router.get("", response_model=list[JourneyRead])
def list_journeys(current_user: CurrentUser, session: DatabaseSession) -> list[JourneyRead]:
    return [
        JourneyRead.model_validate(journey)
        for journey in JourneyService(session).list(current_user)
    ]


@router.get("/{journey_id}", response_model=JourneyRead)
def get_journey(
    journey_id: uuid.UUID, current_user: CurrentUser, session: DatabaseSession
) -> JourneyRead:
    return JourneyRead.model_validate(JourneyService(session).get(current_user, journey_id))


@router.patch("/{journey_id}", response_model=JourneyRead)
def update_journey(
    journey_id: uuid.UUID,
    payload: JourneyUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> JourneyRead:
    journey = JourneyService(session).update(current_user, journey_id, payload)
    return JourneyRead.model_validate(journey)


@router.delete("/{journey_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journey(
    journey_id: uuid.UUID, current_user: CurrentUser, session: DatabaseSession
) -> Response:
    JourneyService(session).delete(current_user, journey_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
