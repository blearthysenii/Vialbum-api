from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.schemas.common import IdentifiedSchema, OrmSchema


class PlaceSelection(OrmSchema):
    provider: str = Field(min_length=1, max_length=32)
    provider_place_id: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=500)
    name: str = Field(min_length=1, max_length=160)
    locality: str | None = Field(default=None, max_length=160)
    region: str | None = Field(default=None, max_length=160)
    country: str = Field(min_length=1, max_length=100)
    country_code: str = Field(min_length=2, max_length=2)
    latitude: Decimal = Field(ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal = Field(ge=-180, le=180, max_digits=9, decimal_places=6)

    @field_validator(
        "provider", "provider_place_id", "display_name", "name", "locality", "region", "country"
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        return value.strip().upper()


class PlaceRead(PlaceSelection, IdentifiedSchema):
    updated_at: datetime


class PlaceSearchResult(PlaceSelection):
    pass
