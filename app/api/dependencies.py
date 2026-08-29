from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.users import UserRepository

DatabaseSession = Annotated[Session, Depends(get_db)]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: DatabaseSession
) -> User:
    user = UserRepository(session).get_by_id(decode_access_token(token))
    if user is None:
        raise UnauthorizedError("Invalid or expired access token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
