import math
import re

from app.core.exceptions import NotFoundError
from app.models.media import MediaType
from app.repositories.world import WorldRepository
from app.schemas.world import (
    Bounds,
    OwnPlaceJourney,
    OwnWorld,
    OwnWorldMarker,
    OwnWorldPlace,
    WorldCountry,
    WorldMapPage,
    WorldMarker,
    WorldPhoto,
    WorldPhotoPage,
    WorldStats,
)
from app.services.discover import DiscoverService, decode_cursor, encode_cursor


def photo_display_name(row):
    for candidate in (row["caption"], row["memory_title"], row["memory_caption"]):
        value = (candidate or "").strip()
        if not value or value == row["original_filename"]:
            continue
        if re.match(r"^(?:img|dsc|dscn|pxl|photo)[_\-\d]", value, re.I):
            continue
        if re.search(r"\.(?:jpe?g|png|heic|webp|gif)$", value, re.I):
            continue
        return value[:160]
    return f"{row['place_name']} Photo {row['number']}"


class WorldService:
    def __init__(self, session, storage=None):
        self.repository = WorldRepository(session)
        self.discover = DiscoverService(session, storage) if storage else None

    def photos(self, user, viewport):
        rows = self.repository.photos(user.id, viewport)
        return WorldPhotoPage(
            items=[
                WorldPhoto(
                    id=row["id"],
                    journey_id=row["journey_id"],
                    memory_id=row["memory_id"],
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    place_name=row["place_name"],
                    display_name=photo_display_name(row),
                    thumbnail_url=self.discover._url(
                        row["thumbnail_storage_key"]
                        or row["display_storage_key"]
                        or row["storage_key"]
                    ),
                )
                for row in rows[: viewport.limit]
            ],
            truncated=len(rows) > viewport.limit,
        )

    def map(self, user, viewport, own=False):
        rows = self.repository.markers(user.id, own, viewport)
        markers = []
        for row in rows[: viewport.limit]:
            count = row["place_count"] if viewport.grouped else 1
            identifier = row["place_id"] if viewport.grouped else row["id"]
            bounds = (
                Bounds(**{key: float(row[key]) for key in ("north", "south", "east", "west")})
                if viewport.grouped
                else Bounds(
                    north=row["latitude"],
                    south=row["latitude"],
                    east=row["longitude"],
                    west=row["longitude"],
                )
            )
            markers.append(
                (OwnWorldMarker if own else WorldMarker)(
                    **({"photo_count": row["photo_count"]} if own else {}),
                    id=str(identifier)
                    if count == 1
                    else f"cluster:{math.floor(viewport.zoom)}:{row['x']}:{row['y']}",
                    type="place" if count == 1 else "cluster",
                    place_id=identifier if count == 1 else None,
                    name=row["name"] if count == 1 else None,
                    country=row["country"] if count == 1 else None,
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    place_count=count,
                    journey_count=row["journey_count"],
                    bounds=bounds,
                )
            )
        data = dict(
            items=markers,
            truncated=len(rows) > viewport.limit,
            next_cursor=rows[viewport.limit - 1]["id"]
            if not viewport.grouped and len(rows) > viewport.limit
            else None,
        )
        if not own:
            return WorldMapPage(**data)
        stats, countries = self.repository.summary(user.id)
        return OwnWorld(
            **data,
            stats=WorldStats(
                **{key: stats[key] for key in ("journeys", "places", "cities", "countries")}
            ),
            countries=[WorldCountry(**row) for row in countries],
            bounds=Bounds(**{key: stats[key] for key in ("north", "south", "east", "west")})
            if stats["places"]
            else None,
        )

    def own_place(self, user, place_id, limit, cursor):
        place = self.repository.own_place(user.id, place_id)
        if place is None:
            raise NotFoundError("Personal place not found")
        rows = self.repository.own_journeys(user.id, place_id, limit, decode_cursor(cursor))
        journeys = []
        for journey in rows[:limit]:
            cover = journey.cover_media
            valid = (
                cover
                and cover.journey_id == journey.id
                and cover.type == MediaType.photo
                and cover.deletion_pending_at is None
            )
            journeys.append(
                OwnPlaceJourney(
                    id=journey.id,
                    title=journey.title,
                    start_date=journey.start_date,
                    end_date=journey.end_date,
                    cover_url=self.discover._url(
                        (
                            cover.thumbnail_storage_key
                            or cover.display_storage_key
                            or cover.storage_key
                        )
                        if valid
                        else None
                    ),
                )
            )
        return OwnWorldPlace(
            id=place["id"],
            name=place["name"],
            country=place["country"],
            locality=place["locality"],
            journey_count=place["journey_count"],
            photo_count=self.repository.photo_count(user.id, place_id),
            journeys=journeys,
            next_cursor=encode_cursor(rows[limit - 1]) if len(rows) > limit else None,
        )
