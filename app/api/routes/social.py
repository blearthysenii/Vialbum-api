import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.repositories.social import SocialRepository
from app.schemas.discover import DiscoverPage, PublicProfile
from app.services.social import SocialService

router = APIRouter(tags=["social"])
PageLimit = Annotated[int, Query(ge=1, le=50)]
PageCursor = Annotated[str | None, Query(max_length=256)]


@router.get("/users/{user_id}/public-profile", response_model=PublicProfile)
def public_profile(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
) -> PublicProfile:
    response.headers["Cache-Control"] = "private, no-store"
    return SocialService(session, storage).profile(user_id, current_user.id)


@router.get("/users/{user_id}/public-journeys", response_model=DiscoverPage)
def public_journeys(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    limit: PageLimit = 20,
    cursor: PageCursor = None,
) -> DiscoverPage:
    response.headers["Cache-Control"] = "private, no-store"
    return SocialService(session, storage).public_journeys(current_user, user_id, limit, cursor)


@router.post("/journeys/{journey_id}/save", status_code=204)
def save_journey(
    journey_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> Response:
    SocialService(session, storage).save(current_user, journey_id)
    return Response(status_code=204)


@router.delete("/journeys/{journey_id}/save", status_code=204)
def unsave_journey(
    journey_id: uuid.UUID, current_user: CurrentUser, session: DatabaseSession
) -> Response:
    SocialRepository(session).remove(current_user.id, journey_id)
    return Response(status_code=204)


@router.get("/saved/journeys", response_model=DiscoverPage)
def saved_journeys(
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    limit: PageLimit = 20,
    cursor: PageCursor = None,
) -> DiscoverPage:
    response.headers["Cache-Control"] = "private, no-store"
    return SocialService(session, storage).saved(current_user, limit, cursor)
