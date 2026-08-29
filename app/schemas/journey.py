import uuid
from datetime import date, datetime

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.schemas.common import IdentifiedSchema, OrmSchema


class JourneyBase(OrmSchema):
    title: str = Field(min_length=1, max_length=160)
    destination: str = Field(min_length=1, max_length=160)
    country: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
    description: str | None = None

    @field_validator("title", "destination", "country")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be empty")
        return stripped

    @model_validator(mode="after")
    def validate_date_order(self) -> "JourneyBase":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class JourneyCreate(JourneyBase):
    pass


class JourneyUpdate(OrmSchema):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    destination: str | None = Field(default=None, min_length=1, max_length=160)
    country: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None

    @field_validator("title", "destination", "country")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be empty")
        return stripped

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "JourneyUpdate":
        required_fields = {"title", "destination", "country", "start_date", "end_date"}
        has_null = any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required_fields
        )
        if has_null:
            raise ValueError("required journey fields cannot be null")
        return self


class JourneyRead(JourneyBase, IdentifiedSchema):
    cover_media_id: uuid.UUID | None
    cover_media_url: HttpUrl | None = None
    updated_at: datetime
