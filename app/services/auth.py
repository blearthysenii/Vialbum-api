from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    hash_password,
    require_jwt_secret,
    verify_password,
)
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.user import AccessToken, LoginRequest, UserCreate


def normalize_email(email: str) -> str:
    return email.strip().casefold()


class AuthService:
    def __init__(self, session: Session) -> None:
        self.users = UserRepository(session)

    def register(self, payload: UserCreate) -> User:
        require_jwt_secret()
        email = normalize_email(str(payload.email))
        if self.users.get_by_email(email):
            raise ConflictError("An account with this email already exists")
        user = self.users.create(
            email=email,
            password_hash=hash_password(payload.password),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
        )
        if user is None:
            raise ConflictError("An account with this email already exists")
        return user

    def login(self, payload: LoginRequest) -> AccessToken:
        user = self.users.get_by_email(normalize_email(str(payload.email)))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        return AccessToken(access_token=create_access_token(user.id))
