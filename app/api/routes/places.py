from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.exceptions import InvalidInputError
from app.schemas.place import PlaceSearchResult
from app.services.place_search import (
    PlaceSearchProvider,
    PlaceSearchService,
    get_place_search_provider,
)

router = APIRouter(prefix="/places", tags=["places"])


@router.get("/search", response_model=list[PlaceSearchResult])
def search_places(
    _current_user: CurrentUser,
    provider: Annotated[PlaceSearchProvider, Depends(get_place_search_provider)],
    q: Annotated[str, Query(min_length=2, max_length=100)],
) -> list[PlaceSearchResult]:
    query = q.strip()
    if len(query) < 2:
        raise InvalidInputError("Place search requires at least 2 characters")
    return PlaceSearchService(provider).search(query, get_settings().place_search_result_limit)
