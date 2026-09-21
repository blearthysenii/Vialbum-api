import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.api.routes.social import PageCursor, PageLimit
from app.schemas.explore import ExploreSearchResponse, PlaceExploreResponse
from app.services.explore import ExploreService

router = APIRouter(prefix="/explore", tags=["explore"])


@router.get("/search", response_model=ExploreSearchResponse)
def search(
    q: Annotated[str, Query(min_length=2, max_length=100)],
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    type: Literal["all", "users", "journeys", "places"] = "all",
    limit: PageLimit = 10,
    cursor: PageCursor = None,
):
    response.headers["Cache-Control"] = "private, no-store"
    return ExploreService(session, storage).search(current_user, q, type, limit, cursor)


@router.get("/places/{place_id}", response_model=PlaceExploreResponse)
def place(
    place_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    limit: PageLimit = 20,
    cursor: PageCursor = None,
):
    response.headers["Cache-Control"] = "private, no-store"
    return ExploreService(session, storage).place(current_user, place_id, limit, cursor)
