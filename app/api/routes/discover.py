import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.schemas.discover import DiscoverPage, PublicJourneyDetail
from app.services.discover import DiscoverService

router = APIRouter(prefix="/discover/journeys", tags=["discover"])


@router.get("", response_model=DiscoverPage)
def discover_journeys(
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
) -> DiscoverPage:
    response.headers["Cache-Control"] = "private, no-store"
    return DiscoverService(session, storage).page(current_user, limit=limit, cursor=cursor)


@router.get("/{journey_id}", response_model=PublicJourneyDetail)
def public_journey(
    journey_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
) -> PublicJourneyDetail:
    response.headers["Cache-Control"] = "private, no-store"
    return DiscoverService(session, storage).detail(current_user, journey_id)
