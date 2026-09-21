import uuid

from sqlalchemy import and_, case, func, or_, select

from app.models.journey import Journey
from app.models.place import Place
from app.models.user import User
from app.repositories.discover import DiscoverRepository


def pattern(query: str) -> str:
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def relevance(query, primary, secondary):
    prefix, partial = pattern(query) + "%", "%" + pattern(query) + "%"
    return case(
        (func.lower(primary) == query, 0),
        (primary.ilike(prefix, escape="\\"), 1),
        (or_(*(field.ilike(prefix, escape="\\") for field in secondary)), 2),
        else_=3,
    ), or_(*(field.ilike(partial, escape="\\") for field in [primary, *secondary]))


class ExploreRepository(DiscoverRepository):
    @staticmethod
    def visible(viewer_id):
        return and_(Journey.visibility == "public", Journey.user_id != viewer_id)

    def place_counts(self, viewer_id):
        # Only top-level journey places are public Explore destinations in V1.
        return (
            select(Journey.place_id, func.count(Journey.id).label("total"))
            .where(self.visible(viewer_id), Journey.place_id.is_not(None))
            .group_by(Journey.place_id)
            .subquery()
        )

    def search(self, viewer_id, kind, query, limit, after):
        if kind == "users":
            model = User
            rank, matches = relevance(
                query,
                User.username,
                [User.first_name, User.last_name, User.first_name + " " + User.last_name],
            )
            statement = select(User, rank.label("rank")).where(matches)
        elif kind == "journeys":
            model = Journey
            rank, matches = relevance(
                query,
                Journey.title,
                [
                    Journey.country,
                    Journey.destination,
                    Place.name,
                    Place.display_name,
                    Place.locality,
                    Place.region,
                    Place.country,
                ],
            )
            statement = (
                self._query()
                .add_columns(rank.label("rank"))
                .outerjoin(Place, Place.id == Journey.place_id)
                .where(self.visible(viewer_id), matches)
            )
        else:
            model = Place
            counts = self.place_counts(viewer_id)
            rank, matches = relevance(
                query, Place.name, [Place.display_name, Place.locality, Place.region, Place.country]
            )
            statement = (
                select(Place, rank.label("rank"), counts.c.total)
                .join(counts, counts.c.place_id == Place.id)
                .where(matches)
            )
        if after:
            score, identifier = after
            statement = statement.where(
                or_(rank > score, and_(rank == score, model.id > identifier))
            )
        return list(
            self.session.execute(statement.order_by(rank, model.id).limit(limit + 1)).unique()
        )

    def place(self, viewer_id: uuid.UUID, place_id: uuid.UUID):
        counts = self.place_counts(viewer_id)
        return self.session.execute(
            select(Place, counts.c.total)
            .join(counts, counts.c.place_id == Place.id)
            .where(Place.id == place_id)
        ).first()

    def place_journeys(self, viewer_id, place_id, limit, after):
        statement = self._query().where(self.visible(viewer_id), Journey.place_id == place_id)
        if after:
            timestamp, identifier = after
            statement = statement.where(
                or_(
                    Journey.created_at < timestamp,
                    and_(Journey.created_at == timestamp, Journey.id < identifier),
                )
            )
        return list(
            self.session.scalars(
                statement.order_by(Journey.created_at.desc(), Journey.id.desc()).limit(limit + 1)
            )
        )
