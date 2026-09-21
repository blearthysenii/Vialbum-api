import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Bounds(BaseModel):
    north: float = Field(ge=-90, le=90, allow_inf_nan=False)
    south: float = Field(ge=-90, le=90, allow_inf_nan=False)
    east: float = Field(ge=-180, le=180, allow_inf_nan=False)
    west: float = Field(ge=-180, le=180, allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered_latitude(self):
        if self.north < self.south:
            raise ValueError("north must be greater than or equal to south")
        return self


class WorldViewport(Bounds):
    zoom: float = Field(default=2, ge=0, le=20, allow_inf_nan=False)
    limit: int = Field(default=200, ge=1, le=500)
    grouped: bool = True
    cursor: uuid.UUID | None = None

    @model_validator(mode="after")
    def raw_cursor_only(self):
        if self.grouped and self.cursor:
            raise ValueError("cursor requires grouped=false")
        return self


class WorldMarker(BaseModel):
    id: str
    type: Literal["place", "cluster"]
    place_id: uuid.UUID | None = None
    name: str | None = None
    country: str | None = None
    latitude: float
    longitude: float
    place_count: int
    journey_count: int
    bounds: Bounds


class WorldMapPage(BaseModel):
    items: list[WorldMarker]
    truncated: bool
    next_cursor: uuid.UUID | None = None


class WorldStats(BaseModel):
    journeys: int
    countries: int
    cities: int
    places: int


class WorldCountry(BaseModel):
    code: str
    name: str
    places: int


class OwnWorldMarker(WorldMarker):
    photo_count: int


class OwnWorld(WorldMapPage):
    items: list[OwnWorldMarker]
    stats: WorldStats
    countries: list[WorldCountry]
    bounds: Bounds | None


class OwnPlaceJourney(BaseModel):
    id: uuid.UUID
    title: str
    start_date: date
    end_date: date
    cover_url: str | None


class OwnWorldPlace(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    locality: str | None
    journey_count: int
    photo_count: int = 0
    journeys: list[OwnPlaceJourney]
    next_cursor: str | None = None


class WorldPhoto(BaseModel):
    id: uuid.UUID
    journey_id: uuid.UUID
    memory_id: uuid.UUID | None
    latitude: float
    longitude: float
    thumbnail_url: str | None
    display_name: str
    place_name: str


class WorldPhotoPage(BaseModel):
    items: list[WorldPhoto]
    truncated: bool
