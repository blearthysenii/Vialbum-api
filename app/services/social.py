import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.user import User
from app.repositories.follows import FollowRepository
from app.repositories.social import SocialRepository
from app.repositories.users import UserRepository
from app.schemas.discover import DiscoverPage, PublicProfile
from app.services.discover import DiscoverService, decode_cursor, encode_cursor
from app.storage.service import StorageService


class SocialService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self.users = UserRepository(session)
        self.repository = SocialRepository(session)
        self.discover = DiscoverService(session, storage)

    def profile(self, owner_id: uuid.UUID, viewer_id: uuid.UUID) -> PublicProfile:
        owner = self.users.get_by_id(owner_id)
        if owner is None:
            raise NotFoundError("User not found")
        follows = FollowRepository(self.users.session)
        return PublicProfile(
            cover_url=self.discover._url(owner.profile_cover_storage_key),
            is_following=owner_id in follows.followed_ids(viewer_id, [owner_id]),
            id=owner.id,
            username=owner.username,
            first_name=owner.first_name,
            last_name=owner.last_name,
            display_name=" ".join(filter(None, [owner.first_name, owner.last_name]))
            or owner.username,
            bio=owner.bio,
            location=owner.location,
            avatar_url=self.discover._url(owner.profile_photo_storage_key),
            public_journeys_count=self.repository.public_count(owner.id),
        )

    def public_journeys(
        self, user: User, owner_id: uuid.UUID, limit: int, cursor: str | None
    ) -> DiscoverPage:
        if self.users.get_by_id(owner_id) is None:
            raise NotFoundError("User not found")
        return self.discover.page(user, limit=limit, cursor=cursor, owner_id=owner_id)

    def save(self, user: User, journey_id: uuid.UUID) -> None:
        journey = self.discover.repository.viewable(journey_id, user.id)
        if journey is None or journey.user_id == user.id or journey.visibility != "public":
            raise NotFoundError("Public journey not found")
        self.repository.save(user.id, journey_id)

    def saved(self, user: User, limit: int, cursor: str | None) -> DiscoverPage:
        # Keep relationships on privacy changes, but always filter at query time.
        rows = self.repository.page(user.id, limit, decode_cursor(cursor))
        page = rows[:limit]
        return DiscoverPage(
            items=self.discover.cards(user, [row[0] for row in page]),
            next_cursor=encode_cursor(page[-1][1]) if len(rows) > limit else None,
        )
