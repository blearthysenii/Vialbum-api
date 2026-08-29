from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import IdentifiedSchema, OrmSchema


class UserBase(OrmSchema):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRead(UserBase, IdentifiedSchema):
    updated_at: datetime


class LoginRequest(OrmSchema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AccessToken(OrmSchema):
    access_token: str
    token_type: str = "bearer"
