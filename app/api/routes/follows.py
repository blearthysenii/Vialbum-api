import uuid

from fastapi import APIRouter, Response

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.api.routes.social import PageCursor, PageLimit
from app.repositories.follows import FollowRepository
from app.schemas.discover import FollowingPage, FollowPage, FollowStats
from app.services.follows import FollowService

router = APIRouter(tags=["follows"])


@router.get("/users/me/follow-stats", response_model=FollowStats)
def my_follow_stats(current_user: CurrentUser, session: DatabaseSession, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    followers_count, following_count = FollowRepository(session).counts(current_user.id)
    return FollowStats(followers_count=followers_count, following_count=following_count)


@router.get("/users/me/followers", response_model=FollowPage)
def my_followers(
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    limit: PageLimit = 20,
    cursor: PageCursor = None,
) -> FollowPage:
    response.headers["Cache-Control"] = "private, no-store"
    return FollowService(session, storage).people(
        current_user, current_user.id, True, limit, cursor
    )


@router.get("/users/me/following", response_model=FollowPage)
def my_following(
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    limit: PageLimit = 20,
    cursor: PageCursor = None,
) -> FollowPage:
    response.headers["Cache-Control"] = "private, no-store"
    return FollowService(session, storage).people(
        current_user, current_user.id, False, limit, cursor
    )


@router.post("/users/{user_id}/follow", status_code=204)
def follow(
    user_id: uuid.UUID, current_user: CurrentUser, session: DatabaseSession, storage: MediaStorage
) -> Response:
    FollowService(session, storage).follow(current_user, user_id)
    return Response(status_code=204)


@router.delete("/users/{user_id}/follow", status_code=204)
def unfollow(user_id: uuid.UUID, current_user: CurrentUser, session: DatabaseSession) -> Response:
    FollowRepository(session).unfollow(current_user.id, user_id)
    return Response(status_code=204)


@router.get("/users/{user_id}/followers", response_model=FollowPage)
def followers(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    limit: PageLimit = 20,
    cursor: PageCursor = None,
) -> FollowPage:
    response.headers["Cache-Control"] = "private, no-store"
    return FollowService(session, storage).people(current_user, user_id, True, limit, cursor)


@router.get("/users/{user_id}/following", response_model=FollowPage)
def following(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    limit: PageLimit = 20,
    cursor: PageCursor = None,
) -> FollowPage:
    response.headers["Cache-Control"] = "private, no-store"
    return FollowService(session, storage).people(current_user, user_id, False, limit, cursor)


@router.get("/following/journeys", response_model=FollowingPage)
def following_journeys(
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    response: Response,
    limit: PageLimit = 20,
    cursor: PageCursor = None,
) -> FollowingPage:
    response.headers["Cache-Control"] = "private, no-store"
    return FollowService(session, storage).feed(current_user, limit, cursor)
