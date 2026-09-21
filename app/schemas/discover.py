import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, HttpUrl

from app.schemas.common import OrmSchema
from app.schemas.journey import JourneyRead
from app.schemas.memory import MemoryRead
from app.schemas.place import PlaceRead


class PublicCreator(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    avatar_url: HttpUrl | None = None


class DiscoverJourney(JourneyRead):
    is_saved: bool = False
    creator: PublicCreator
    photo_count: int
    memory_count: int
    cover_width: int | None = None
    cover_height: int | None = None


class DiscoverPage(BaseModel):
    items: list[DiscoverJourney]
    next_cursor: str | None = None


class PublicProfile(PublicCreator):
    cover_url: HttpUrl | None = None
    is_following: bool = False
    first_name: str
    last_name: str
    bio: str | None
    location: str | None
    public_journeys_count: int


class FollowStats(BaseModel):
    followers_count: int
    following_count: int


class FollowUser(PublicCreator):
    is_following: bool


class FollowPage(BaseModel):
    items: list[FollowUser]
    next_cursor: str | None = None


class FollowingPage(DiscoverPage):
    following_count: int


class PublicPhoto(OrmSchema):
    id: uuid.UUID
    memory_id: uuid.UUID | None
    caption: str | None
    url: HttpUrl
    thumbnail_url: HttpUrl | None
    width: int | None
    height: int | None
    captured_at: datetime | None
    created_at: datetime
    latitude: Decimal | None
    longitude: Decimal | None
    place: PlaceRead | None


class PublicJourneyDetail(DiscoverJourney):
    memories: list[MemoryRead]
    photos: list[PublicPhoto]
