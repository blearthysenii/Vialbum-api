import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.discover import DiscoverPage, FollowUser


class PublicPlace(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    locality: str | None
    region: str | None
    country: str
    country_code: str
    latitude: Decimal
    longitude: Decimal
    public_journeys_count: int


class UserSearchPage(BaseModel):
    items: list[FollowUser] = Field(default_factory=list)
    next_cursor: str | None = None


class PlaceSearchPage(BaseModel):
    items: list[PublicPlace] = Field(default_factory=list)
    next_cursor: str | None = None


class ExploreSearchResponse(BaseModel):
    query: str
    users: UserSearchPage
    journeys: DiscoverPage
    places: PlaceSearchPage


class PlaceExploreResponse(BaseModel):
    place: PublicPlace
    journeys: DiscoverPage
