from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConfigurationError, UnauthorizedError
from app.core.security import verify_password
from app.models.user import User
from app.repositories.media import MediaRepository
from app.repositories.users import UserRepository
from app.schemas.user import AccountDeletionRequest
from app.storage.service import StorageOperationError, StorageService


class AccountService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self.media = MediaRepository(session)
        self.users = UserRepository(session)
        self.storage = storage

    def delete(self, user: User, payload: AccountDeletionRequest) -> None:
        if not verify_password(payload.password, user.password_hash):
            raise UnauthorizedError("The password is incorrect")

        media = self.media.list_for_user(user.id)
        self.media.mark_deletion_pending(media, datetime.now(UTC))
        keys = {
            key
            for item in media
            for key in (item.storage_key, item.display_storage_key, item.thumbnail_storage_key)
            if key
        }
        try:
            for key in sorted(keys):
                self.storage.delete(key=key)
        except StorageOperationError as exc:
            raise ConfigurationError(
                "Your account could not be deleted because private media cleanup is unavailable. "
                "Your account remains active; please try again."
            ) from exc
        self.users.delete(user)
