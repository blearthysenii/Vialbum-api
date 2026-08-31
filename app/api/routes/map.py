from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.schemas.map import MapItem
from app.services.map import MapService

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/items", response_model=list[MapItem])
def list_map_items(
    current_user: CurrentUser, session: DatabaseSession, storage: MediaStorage
) -> list[MapItem]:
    return MapService(session, storage).list(current_user)
