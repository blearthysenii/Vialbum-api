from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.schemas.search import SearchResponse
from app.services.search import SearchService

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def global_search(
    q: Annotated[str, Query(min_length=2, max_length=100)],
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> SearchResponse:
    return SearchService(session, storage).run(current_user, q)
