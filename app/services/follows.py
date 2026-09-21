import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidInputError, NotFoundError
from app.models.user import User
from app.repositories.follows import FollowRepository
from app.repositories.users import UserRepository
from app.schemas.discover import FollowingPage, FollowPage, FollowUser
from app.services.discover import DiscoverService, decode_cursor, encode_cursor
from app.storage.service import StorageService


class FollowService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self.repository = FollowRepository(session)
        self.users = UserRepository(session)
        self.discover = DiscoverService(session, storage)

    def follow(self, viewer: User, target: uuid.UUID) -> None:
        if target == viewer.id:
            raise InvalidInputError("You cannot follow yourself")
        if self.users.get_by_id(target) is None:
            raise NotFoundError("User not found")
        self.repository.follow(viewer.id, target)

    def people(
        self, viewer: User, target: uuid.UUID, followers: bool, limit: int, cursor: str | None
    ) -> FollowPage:
        if target != viewer.id:
            raise NotFoundError("User not found")
        rows = self.repository.page(target, followers, limit, decode_cursor(cursor))
        page = rows[:limit]
        followed = self.repository.followed_ids(viewer.id, [row[0].id for row in page])
        return FollowPage(
            items=[
                FollowUser(
                    id=user.id,
                    username=user.username,
                    display_name=" ".join(filter(None, [user.first_name, user.last_name]))
                    or user.username,
                    avatar_url=self.discover._url(user.profile_photo_storage_key),
                    is_following=user.id in followed,
                )
                for user, _ in page
            ],
            next_cursor=encode_cursor(page[-1][1]) if len(rows) > limit else None,
        )

    def feed(self, viewer: User, limit: int, cursor: str | None) -> FollowingPage:
        page = self.discover.page(viewer, limit=limit, cursor=cursor, following_only=True)
        return FollowingPage(
            **page.model_dump(), following_count=self.repository.counts(viewer.id)[1]
        )
