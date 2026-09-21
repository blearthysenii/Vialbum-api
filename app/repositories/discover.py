import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.journey import Journey
from app.models.media import Media, MediaType
from app.models.memory import Memory
from app.models.user_follow import UserFollow


class DiscoverRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _query():
        return select(Journey).options(
            joinedload(Journey.user), joinedload(Journey.place), joinedload(Journey.cover_media)
        )

    def page(
        self,
        viewer_id: uuid.UUID,
        limit: int,
        after: tuple[datetime, uuid.UUID] | None,
        owner_id: uuid.UUID | None = None,
        following_only: bool = False,
    ) -> list[Journey]:
        query = self._query().where(Journey.visibility == "public")
        query = query.where(
            Journey.user_id == owner_id if owner_id else Journey.user_id != viewer_id
        )
        if following_only:
            query = query.where(
                select(UserFollow.id)
                .where(
                    UserFollow.follower_id == viewer_id,
                    UserFollow.following_id == Journey.user_id,
                )
                .exists()
            )
        if after is not None:
            created_at, journey_id = after
            query = query.where(
                or_(
                    Journey.created_at < created_at,
                    and_(Journey.created_at == created_at, Journey.id < journey_id),
                )
            )
        return list(
            self.session.scalars(
                query.order_by(Journey.created_at.desc(), Journey.id.desc()).limit(limit + 1)
            )
        )

    def viewable(self, journey_id: uuid.UUID, viewer_id: uuid.UUID) -> Journey | None:
        return self.session.scalar(
            self._query().where(
                Journey.id == journey_id,
                or_(Journey.user_id == viewer_id, Journey.visibility == "public"),
            )
        )

    def counts(self, ids: list[uuid.UUID]) -> tuple[dict, dict]:
        if not ids:
            return {}, {}
        photos = dict(
            self.session.execute(
                select(Media.journey_id, func.count(Media.id))
                .where(
                    Media.journey_id.in_(ids),
                    Media.type == MediaType.photo,
                    Media.deletion_pending_at.is_(None),
                )
                .group_by(Media.journey_id)
            ).all()
        )
        memories = dict(
            self.session.execute(
                select(Memory.journey_id, func.count(Memory.id))
                .where(Memory.journey_id.in_(ids))
                .group_by(Memory.journey_id)
            ).all()
        )
        return photos, memories
