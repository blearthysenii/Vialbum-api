import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile, status

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.core.config import get_settings
from app.schemas.journey import JourneyCreate, JourneyRead, JourneyUpdate
from app.schemas.media import MediaRead
from app.services.journeys import JourneyService
from app.services.media import MediaService

router = APIRouter(prefix="/journeys", tags=["journeys"])


@router.post("", response_model=JourneyRead, status_code=status.HTTP_201_CREATED)
def create_journey(
    payload: JourneyCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> JourneyRead:
    journey = JourneyService(session).create(current_user, payload)
    return MediaService(session, storage).serialize_journey(journey)


@router.get("", response_model=list[JourneyRead])
def list_journeys(
    current_user: CurrentUser, session: DatabaseSession, storage: MediaStorage
) -> list[JourneyRead]:
    media_service = MediaService(session, storage)
    return [
        media_service.serialize_journey(journey)
        for journey in JourneyService(session).list(current_user)
    ]


@router.get("/{journey_id}", response_model=JourneyRead)
def get_journey(
    journey_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> JourneyRead:
    journey = JourneyService(session).get(current_user, journey_id)
    return MediaService(session, storage).serialize_journey(journey)


@router.patch("/{journey_id}", response_model=JourneyRead)
def update_journey(
    journey_id: uuid.UUID,
    payload: JourneyUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> JourneyRead:
    journey = JourneyService(session).update(current_user, journey_id, payload)
    return MediaService(session, storage).serialize_journey(journey)


@router.delete("/{journey_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journey(
    journey_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> Response:
    media_service = MediaService(session, storage)
    for media in media_service.list(current_user, journey_id):
        media_service.delete(current_user, journey_id, media.id)
    JourneyService(session).delete(current_user, journey_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{journey_id}/media", response_model=MediaRead, status_code=status.HTTP_201_CREATED)
async def upload_journey_photo(
    journey_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    file: Annotated[UploadFile, File()],
    captured_at: Annotated[datetime | None, Form()] = None,
    width: Annotated[int | None, Form(ge=1)] = None,
    height: Annotated[int | None, Form(ge=1)] = None,
    latitude: Annotated[Decimal | None, Form(ge=-90, le=90)] = None,
    longitude: Annotated[Decimal | None, Form(ge=-180, le=180)] = None,
) -> MediaRead:
    maximum = get_settings().media_max_upload_bytes
    body = await file.read(maximum + 1)
    media_service = MediaService(session, storage)
    media = media_service.upload_photo(
        user=current_user,
        journey_id=journey_id,
        filename=file.filename,
        body=body,
        captured_at=captured_at,
        width=width,
        height=height,
        latitude=latitude,
        longitude=longitude,
    )
    return media_service.serialize(media)


@router.get("/{journey_id}/media", response_model=list[MediaRead])
def list_journey_media(
    journey_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> list[MediaRead]:
    media_service = MediaService(session, storage)
    return [
        media_service.serialize(media) for media in media_service.list(current_user, journey_id)
    ]


@router.delete("/{journey_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journey_media(
    journey_id: uuid.UUID,
    media_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> Response:
    MediaService(session, storage).delete(current_user, journey_id, media_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{journey_id}/cover/{media_id}", response_model=JourneyRead)
def set_journey_cover(
    journey_id: uuid.UUID,
    media_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> JourneyRead:
    media_service = MediaService(session, storage)
    journey = media_service.set_cover(current_user, journey_id, media_id)
    return media_service.serialize_journey(journey)
