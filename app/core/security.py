import uuid
from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError, UnauthorizedError

password_hash = PasswordHash.recommended()


def require_jwt_secret() -> str:
    secret = get_settings().jwt_secret
    if not secret:
        raise ConfigurationError("Authentication is not configured")
    return secret.get_secret_value()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return password_hash.verify(password, encoded_hash)


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    jwt_secret = require_jwt_secret()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": str(user_id), "exp": expires_at, "iat": datetime.now(UTC)},
        jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> uuid.UUID:
    settings = get_settings()
    jwt_secret = require_jwt_secret()
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=[settings.jwt_algorithm])
        return uuid.UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid or expired access token") from exc
