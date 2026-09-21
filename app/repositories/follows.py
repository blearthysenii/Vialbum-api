import uuid
from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_follow import UserFollow


class FollowRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def followed_ids(self, viewer_id: uuid.UUID, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        return (
            set(
                self.session.scalars(
                    select(UserFollow.following_id).where(
                        UserFollow.follower_id == viewer_id, UserFollow.following_id.in_(ids)
                    )
                )
            )
            if ids
            else set()
        )

    def counts(self, user_id: uuid.UUID) -> tuple[int, int]:
        return tuple(
            self.session.execute(
                select(
                    select(func.count(UserFollow.id))
                    .where(UserFollow.following_id == user_id)
                    .scalar_subquery(),
                    select(func.count(UserFollow.id))
                    .where(UserFollow.follower_id == user_id)
                    .scalar_subquery(),
                )
            ).one()
        )

    def follow(self, viewer_id: uuid.UUID, target_id: uuid.UUID) -> None:
        try:
            with self.session.begin_nested():
                self.session.add(UserFollow(follower_id=viewer_id, following_id=target_id))
                self.session.flush()
        except IntegrityError:
            if target_id not in self.followed_ids(viewer_id, [target_id]):
                raise
        self.session.commit()

    def unfollow(self, viewer_id: uuid.UUID, target_id: uuid.UUID) -> None:
        self.session.execute(
            delete(UserFollow).where(
                UserFollow.follower_id == viewer_id, UserFollow.following_id == target_id
            )
        )
        self.session.commit()

    def page(
        self,
        owner_id: uuid.UUID,
        followers: bool,
        limit: int,
        after: tuple[datetime, uuid.UUID] | None,
    ):
        subject = UserFollow.follower_id if followers else UserFollow.following_id
        owner = UserFollow.following_id if followers else UserFollow.follower_id
        query = (
            select(User, UserFollow).join(UserFollow, User.id == subject).where(owner == owner_id)
        )
        if after:
            timestamp, identifier = after
            query = query.where(
                or_(
                    UserFollow.created_at < timestamp,
                    and_(UserFollow.created_at == timestamp, UserFollow.id < identifier),
                )
            )
        return list(
            self.session.execute(
                query.order_by(UserFollow.created_at.desc(), UserFollow.id.desc()).limit(limit + 1)
            )
        )
