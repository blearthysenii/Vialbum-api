from sqlalchemy.exc import IntegrityError
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
from app.schemas.user import (
    AccessToken,
    AccountExistsRequest,
    EmailExistsRequest,
    LoginRequest,
    UserCreate,
    UsernameExistsRequest,
)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def normalize_identifier(identifier: str) -> str:
    return identifier.strip().casefold()


def normalize_username(username: str) -> str:
    return username.strip().casefold()


class AuthService:
    def __init__(self, session: Session) -> None:
        self.users = UserRepository(session)

    def register(self, payload: UserCreate) -> User:
        require_jwt_secret()
        email = normalize_email(str(payload.email))
        username = normalize_username(payload.username)
        if self.users.get_by_email(email):
            raise ConflictError(
                "This email is already registered with Vialbum.",
                code="EMAIL_ALREADY_REGISTERED",
            )
        if self.users.get_by_username(username):
            raise ConflictError(
                "This username is already taken.",
                code="USERNAME_TAKEN",
            )
        try:
            user = self.users.create(
                email=email,
                username=username,
                password_hash=hash_password(payload.password),
                first_name=payload.first_name.strip(),
                last_name=payload.last_name.strip(),
            )
        except IntegrityError:
            if self.users.get_by_email(email):
                raise ConflictError(
                    "This email is already registered with Vialbum.",
                    code="EMAIL_ALREADY_REGISTERED",
                ) from None
            if self.users.get_by_username(username):
                raise ConflictError(
                    "This username is already taken.", code="USERNAME_TAKEN"
                ) from None
            raise
        return user

    def email_exists(self, payload: EmailExistsRequest) -> bool:
        return self.users.get_by_email(normalize_email(str(payload.email))) is not None

    def username_exists(self, payload: UsernameExistsRequest) -> bool:
        return self.users.get_by_username(normalize_username(payload.username)) is not None

    def account_exists(self, payload: AccountExistsRequest) -> bool:
        return self.users.get_by_identifier(normalize_identifier(payload.identifier)) is not None

    def login(self, payload: LoginRequest) -> AccessToken:
        raw_identifier = payload.identifier or str(payload.email)
        user = self.users.get_by_identifier(normalize_identifier(raw_identifier))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise UnauthorizedError("The email, username, or password is incorrect")
        return AccessToken(access_token=create_access_token(user.id))
