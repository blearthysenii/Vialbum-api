from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.common import IdentifiedSchema, OrmSchema

USERNAME_PATTERN = r"^[a-z0-9_]{3,30}$"


class UserBase(OrmSchema):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=USERNAME_PATTERN)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRead(UserBase, IdentifiedSchema):
    bio: str | None = None
    location: str | None = None
    profile_photo_url: str | None = None
    updated_at: datetime


class UserUpdate(OrmSchema):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    username: str = Field(min_length=3, max_length=30, pattern=USERNAME_PATTERN)
    bio: str | None = Field(default=None, max_length=150)
    location: str | None = Field(default=None, max_length=100)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("username", mode="before")
    @classmethod
    def normalize_update_username(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value

    @field_validator("bio", "location", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None


class LoginRequest(OrmSchema):
    identifier: str | None = Field(default=None, min_length=1, max_length=320)
    email: EmailStr | None = None
    password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_identifier(self) -> "LoginRequest":
        if not (self.identifier or self.email):
            raise ValueError("Email or username is required")
        return self


class EmailExistsRequest(OrmSchema):
    email: EmailStr


class EmailExistsResponse(OrmSchema):
    exists: bool


class UsernameExistsRequest(OrmSchema):
    username: str = Field(min_length=3, max_length=30, pattern=USERNAME_PATTERN)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value


class UsernameExistsResponse(OrmSchema):
    exists: bool


class AccountExistsRequest(OrmSchema):
    identifier: str = Field(min_length=1, max_length=320)


class AccountExistsResponse(OrmSchema):
    exists: bool


class AccessToken(OrmSchema):
    access_token: str
    token_type: str = "bearer"


class AccountDeletionRequest(OrmSchema):
    confirmation: Literal["DELETE"]
    password: str = Field(min_length=1, max_length=128)
