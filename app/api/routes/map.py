import uuid
from typing import Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.schemas.map import MapItem, MapThumbnail
from app.services.map import MapService

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/items", response_model=list[MapItem])
def list_map_items(
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    include_thumbnails: bool = Query(default=True),
) -> list[MapItem]:
    return MapService(session, storage).list(current_user, include_thumbnails=include_thumbnails)


@router.get("/items/{item_type}/{item_id}/thumbnail", response_model=MapThumbnail)
def get_map_item_thumbnail(
    item_type: Literal["journey", "memory", "photo"],
    item_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> MapThumbnail:
    return MapService(session, storage).thumbnail(current_user, item_type, item_id)
