import base64
import binascii
import json
import uuid

from app.core.exceptions import InvalidInputError, NotFoundError
from app.repositories.explore import ExploreRepository
from app.repositories.follows import FollowRepository
from app.schemas.discover import DiscoverPage, FollowUser
from app.schemas.explore import (
    ExploreSearchResponse,
    PlaceExploreResponse,
    PlaceSearchPage,
    PublicPlace,
    UserSearchPage,
)
from app.services.discover import DiscoverService, decode_cursor, encode_cursor


def search_cursor(query, kind, row):
    return base64.urlsafe_b64encode(
        json.dumps([query, kind, row[1], str(row[0].id)]).encode()
    ).decode()


def read_cursor(value, query, kind):
    if value is None:
        return None
    try:
        q, category, rank, identifier = json.loads(
            base64.b64decode(value, altchars=b"-_", validate=True)
        )
        if q != query or category != kind or type(rank) is not int or rank not in range(4):
            raise ValueError()
        return rank, uuid.UUID(identifier)
    except (ValueError, TypeError, UnicodeError, binascii.Error) as exc:
        raise InvalidInputError("Invalid search cursor") from exc


class ExploreService:
    def __init__(self, session, storage):
        self.repository = ExploreRepository(session)
        self.discover = DiscoverService(session, storage)
        self.follows = FollowRepository(session)

    @staticmethod
    def public_place(place, count):
        return PublicPlace(
            **{
                field: getattr(place, field)
                for field in PublicPlace.model_fields
                if field != "public_journeys_count"
            },
            public_journeys_count=count,
        )

    def search(self, viewer, query, kind, limit, cursor):
        query = " ".join(query.split()).lower()
        term = query.removeprefix("@")
        if len(term) < 2:
            raise InvalidInputError("Search requires at least 2 characters")
        if cursor and kind == "all":
            raise InvalidInputError("Choose a result type to continue pagination")
        groups = {
            "users": UserSearchPage(),
            "journeys": DiscoverPage(items=[]),
            "places": PlaceSearchPage(),
        }
        for category in groups:
            if kind not in ("all", category):
                continue
            rows = self.repository.search(
                viewer.id, category, term, limit, read_cursor(cursor, query, category)
            )
            page = rows[:limit]
            next_cursor = search_cursor(query, category, page[-1]) if len(rows) > limit else None
            if category == "journeys":
                groups[category] = DiscoverPage(
                    items=self.discover.cards(viewer, [row[0] for row in page]),
                    next_cursor=next_cursor,
                )
            elif category == "users":
                followed = self.follows.followed_ids(viewer.id, [row[0].id for row in page])
                groups[category] = UserSearchPage(
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
                    next_cursor=next_cursor,
                )
            else:
                groups[category] = PlaceSearchPage(
                    items=[self.public_place(row[0], row[2]) for row in page],
                    next_cursor=next_cursor,
                )
        return ExploreSearchResponse(query=query, **groups)

    def place(self, viewer, identifier, limit, cursor):
        row = self.repository.place(viewer.id, identifier)
        if row is None:
            raise NotFoundError("Public place not found")
        journeys = self.repository.place_journeys(
            viewer.id, identifier, limit, decode_cursor(cursor)
        )
        return PlaceExploreResponse(
            place=self.public_place(*row),
            journeys=DiscoverPage(
                items=self.discover.cards(viewer, journeys[:limit]),
                next_cursor=encode_cursor(journeys[limit - 1]) if len(journeys) > limit else None,
            ),
        )
