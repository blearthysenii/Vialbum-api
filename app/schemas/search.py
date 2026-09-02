import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, HttpUrl


class JourneySearchResult(BaseModel):
    type: Literal["journey"] = "journey"
    id: uuid.UUID
    title: str
    destination: str
    country: str
    start_date: date
    end_date: date
    location: str | None = None
    thumbnail_url: HttpUrl | None = None


class MemorySearchResult(BaseModel):
    type: Literal["memory"] = "memory"
    id: uuid.UUID
    journey_id: uuid.UUID
    journey_title: str
    journey_start_date: date
    title: str
    date: date
    location: str | None = None
    context: str | None = None


class PhotoSearchResult(BaseModel):
    type: Literal["photo"] = "photo"
    id: uuid.UUID
    journey_id: uuid.UUID
    journey_title: str
    date: date
    caption: str | None = None
    location: str | None = None
    memory_title: str | None = None
    thumbnail_url: HttpUrl | None = None


class SearchResponse(BaseModel):
    query: str
    journeys: list[JourneySearchResult]
    memories: list[MemorySearchResult]
    photos: list[PhotoSearchResult]
