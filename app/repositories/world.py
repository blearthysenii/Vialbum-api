import math

from sqlalchemy import String, and_, case, cast, func, or_, select, union
from sqlalchemy.orm import aliased

from app.models.journey import Journey
from app.models.media import Media, MediaType
from app.models.memory import Memory
from app.models.place import Place
from app.repositories.explore import ExploreRepository


class WorldRepository(ExploreRepository):
    def photo_points(self, user_id):
        memory_place, photo_place, journey_place = aliased(Place), aliased(Place), aliased(Place)
        place_id = func.coalesce(Memory.place_id, Media.place_id, Journey.place_id)
        return (
            select(
                Media.id,
                Media.journey_id,
                Media.memory_id,
                Media.caption,
                Media.original_filename,
                Media.storage_key,
                Media.thumbnail_storage_key,
                Media.display_storage_key,
                Memory.title.label("memory_title"),
                Memory.caption.label("memory_caption"),
                place_id.label("place_id"),
                func.coalesce(
                    memory_place.name,
                    photo_place.name,
                    journey_place.name,
                    Journey.destination,
                    Journey.country,
                ).label("place_name"),
                func.coalesce(
                    Memory.latitude,
                    memory_place.latitude,
                    Media.latitude,
                    photo_place.latitude,
                    journey_place.latitude,
                    Journey.latitude,
                ).label("latitude"),
                func.coalesce(
                    Memory.longitude,
                    memory_place.longitude,
                    Media.longitude,
                    photo_place.longitude,
                    journey_place.longitude,
                    Journey.longitude,
                ).label("longitude"),
                func.row_number()
                .over(
                    partition_by=func.coalesce(cast(place_id, String), Journey.destination),
                    order_by=(
                        func.coalesce(Media.captured_at, Media.created_at),
                        Media.created_at,
                        Media.id,
                    ),
                )
                .label("number"),
            )
            .select_from(Media)
            .join(Journey, Journey.id == Media.journey_id)
            .outerjoin(Memory, and_(Memory.id == Media.memory_id, Memory.journey_id == Journey.id))
            .outerjoin(memory_place, memory_place.id == Memory.place_id)
            .outerjoin(photo_place, photo_place.id == Media.place_id)
            .outerjoin(journey_place, journey_place.id == Journey.place_id)
            .where(
                Journey.user_id == user_id,
                Media.type == MediaType.photo,
                Media.deletion_pending_at.is_(None),
            )
            .subquery()
        )

    def photos(self, user_id, viewport):
        points = self.photo_points(user_id)
        longitude = and_(points.c.longitude >= viewport.west, points.c.longitude <= viewport.east)
        if viewport.west > viewport.east:
            longitude = or_(
                points.c.longitude >= viewport.west, points.c.longitude <= viewport.east
            )
        statement = (
            select(points)
            .where(
                points.c.latitude >= viewport.south, points.c.latitude <= viewport.north, longitude
            )
            .order_by(points.c.place_name, points.c.number, points.c.id)
            .limit(viewport.limit + 1)
        )
        return list(self.session.execute(statement).mappings())

    def photo_count(self, user_id, place_id):
        points = self.photo_points(user_id)
        return self.session.scalar(
            select(func.count()).select_from(points).where(points.c.place_id == place_id)
        )

    def own_associations(self, user_id):
        return union(
            select(Journey.place_id, Journey.id.label("journey_id")).where(
                Journey.user_id == user_id, Journey.place_id.is_not(None)
            ),
            select(Memory.place_id, Memory.journey_id)
            .join(Journey)
            .where(Journey.user_id == user_id, Memory.place_id.is_not(None)),
            select(Media.place_id, Media.journey_id)
            .join(Journey, Journey.id == Media.journey_id)
            .where(
                Journey.user_id == user_id,
                Media.place_id.is_not(None),
                Media.type == MediaType.photo,
                Media.deletion_pending_at.is_(None),
            ),
        ).subquery()

    def places_query(self, user_id, own):
        if own:
            associations = self.own_associations(user_id)
            photos = self.photo_points(user_id)
            return (
                select(
                    Place.id,
                    Place.name,
                    Place.country,
                    Place.country_code,
                    Place.locality,
                    Place.latitude,
                    Place.longitude,
                    func.count(associations.c.journey_id).label("journey_count"),
                    select(func.count())
                    .select_from(photos)
                    .where(photos.c.place_id == Place.id)
                    .correlate(Place)
                    .scalar_subquery()
                    .label("photo_count"),
                )
                .join(associations, associations.c.place_id == Place.id)
                .group_by(Place.id)
            )
        condition = Journey.user_id == user_id if own else self.visible(user_id)
        return (
            select(
                Place.id,
                Place.name,
                Place.country,
                Place.country_code,
                Place.locality,
                Place.latitude,
                Place.longitude,
                func.count(Journey.id).label("journey_count"),
            )
            .join(Journey, Journey.place_id == Place.id)
            .where(condition)
            .group_by(Place.id)
        )

    def markers(self, user_id, own, viewport):
        longitude = and_(Place.longitude >= viewport.west, Place.longitude <= viewport.east)
        if viewport.west > viewport.east:
            longitude = or_(Place.longitude >= viewport.west, Place.longitude <= viewport.east)
        points = (
            self.places_query(user_id, own)
            .where(Place.latitude >= viewport.south, Place.latitude <= viewport.north, longitude)
            .subquery()
        )
        if not viewport.grouped:
            statement = select(points)
            if viewport.cursor:
                statement = statement.where(points.c.id > viewport.cursor)
            return list(
                self.session.execute(
                    statement.order_by(points.c.id).limit(viewport.limit + 1)
                ).mappings()
            )
        cell = 360 / (2 ** (math.floor(viewport.zoom) + 3))
        x = func.floor((points.c.longitude + 180) / cell)
        y = func.floor((points.c.latitude + 90) / cell)
        statement = (
            select(
                x.label("x"),
                y.label("y"),
                func.count().label("place_count"),
                func.sum(points.c.journey_count).label("journey_count"),
                (func.sum(points.c.photo_count) if own else func.count()).label("photo_count"),
                func.avg(points.c.latitude).label("latitude"),
                func.avg(points.c.longitude).label("longitude"),
                func.min(cast(points.c.id, String)).label("place_id"),
                func.min(points.c.name).label("name"),
                func.min(points.c.country).label("country"),
                func.min(points.c.latitude).label("south"),
                func.max(points.c.latitude).label("north"),
                func.min(points.c.longitude).label("west"),
                func.max(points.c.longitude).label("east"),
            )
            .group_by(x, y)
            .order_by(x, y)
            .limit(viewport.limit + 1)
        )
        return list(self.session.execute(statement).mappings())

    def summary(self, user_id):
        points = self.places_query(user_id, True).subquery()
        # Place identity is normalized by provider+provider_place_id. Cities use stored
        # locality within ISO country code; no guessing from captions or raw country names.
        city = case(
            (
                func.length(func.trim(points.c.locality)) > 0,
                func.upper(points.c.country_code) + ":" + func.lower(func.trim(points.c.locality)),
            ),
            else_=None,
        )
        row = (
            self.session.execute(
                select(
                    func.count().label("places"),
                    func.count(func.distinct(func.upper(points.c.country_code))).label("countries"),
                    func.count(func.distinct(city)).label("cities"),
                    select(func.count(Journey.id))
                    .where(Journey.user_id == user_id)
                    .scalar_subquery()
                    .label("journeys"),
                    func.min(points.c.latitude).label("south"),
                    func.max(points.c.latitude).label("north"),
                    func.min(points.c.longitude).label("west"),
                    func.max(points.c.longitude).label("east"),
                ).select_from(points)
            )
            .mappings()
            .one()
        )
        countries = (
            self.session.execute(
                select(
                    func.upper(points.c.country_code).label("code"),
                    func.min(points.c.country).label("name"),
                    func.count().label("places"),
                )
                .group_by(func.upper(points.c.country_code))
                .order_by(func.upper(points.c.country_code))
            )
            .mappings()
            .all()
        )
        return row, countries

    def own_place(self, user_id, place_id):
        return (
            self.session.execute(self.places_query(user_id, True).where(Place.id == place_id))
            .mappings()
            .first()
        )

    def own_journeys(self, user_id, place_id, limit, after):
        associations = self.own_associations(user_id)
        statement = self._query().where(
            Journey.user_id == user_id,
            Journey.id.in_(
                select(associations.c.journey_id).where(associations.c.place_id == place_id)
            ),
        )
        if after:
            stamp, identifier = after
            statement = statement.where(
                or_(
                    Journey.created_at < stamp,
                    and_(Journey.created_at == stamp, Journey.id < identifier),
                )
            )
        return list(
            self.session.scalars(
                statement.order_by(Journey.created_at.desc(), Journey.id.desc()).limit(limit + 1)
            )
        )
