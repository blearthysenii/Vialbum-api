import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.api.routes.social import PageCursor, PageLimit
from app.schemas.world import OwnWorld, OwnWorldPlace, WorldMapPage, WorldPhotoPage, WorldViewport
from app.services.world import WorldService

router = APIRouter(tags=["world"])


@router.get("/users/me/world/photos", response_model=WorldPhotoPage)
def own_photos(
    viewport: Annotated[WorldViewport, Query()],
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
):
    response.headers["Cache-Control"] = "private, no-store"
    return WorldService(session, storage).photos(current_user, viewport)


@router.get("/explore/map", response_model=WorldMapPage)
def explore_map(
    viewport: Annotated[WorldViewport, Query()],
    current_user: CurrentUser,
    session: DatabaseSession,
    response: Response,
):
    response.headers["Cache-Control"] = "private, no-store"
    return WorldService(session).map(current_user, viewport)


@router.get("/users/me/world", response_model=OwnWorld)
def own_world(
    viewport: Annotated[WorldViewport, Query()],
    current_user: CurrentUser,
    session: DatabaseSession,
    response: Response,
):
    response.headers["Cache-Control"] = "private, no-store"
    return WorldService(session).map(current_user, viewport, own=True)


@router.get("/users/me/world/places/{place_id}", response_model=OwnWorldPlace)
def own_place(
    place_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    limit: PageLimit = 10,
    cursor: PageCursor = None,
):
    response.headers["Cache-Control"] = "private, no-store"
    return WorldService(session, storage).own_place(current_user, place_id, limit, cursor)
