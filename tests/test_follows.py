import uuid

import pytest
from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_follow import UserFollow
from tests.conftest import test_engine
from tests.test_discover import account, journey


def test_follow_counts_idempotency_and_unfollow(client):
    a, auth_a = account(client, "alice@example.com")
    b, auth_b = account(client, "bravo@example.com")
    url = f"/users/{a['id']}/follow"
    for _ in range(2):
        assert client.post(url, headers=auth_b).status_code == 204
    profile = client.get(f"/users/{a['id']}/public-profile", headers=auth_b).json()
    assert profile["is_following"] is True
    assert client.get("/users/me/follow-stats", headers=auth_a).json()["followers_count"] == 1
    assert "following_count" not in profile
    mine = client.get(f"/users/{b['id']}/public-profile", headers=auth_b).json()
    assert client.get("/users/me/follow-stats", headers=auth_b).json()["following_count"] == 1
    assert mine["is_following"] is False
    with Session(test_engine) as session:
        assert session.scalar(select(func.count(UserFollow.id))) == 1
    assert client.post(f"/users/{a['id']}/follow", headers=auth_a).status_code == 422
    assert client.post(f"/users/{uuid.uuid4()}/follow", headers=auth_a).status_code == 404
    for _ in range(2):
        assert client.delete(url, headers=auth_b).status_code == 204
    profile = client.get(f"/users/{a['id']}/public-profile", headers=auth_b).json()
    assert client.get("/users/me/follow-stats", headers=auth_a).json()["followers_count"] == 0
    assert profile["is_following"] is False


def test_private_graph_five_followers_three_following(client):
    owner, auth = account(client, "owner@example.com")
    peers = [account(client, f"peer{i}@example.com") for i in range(5)]
    for index, (peer, peer_auth) in enumerate(peers):
        assert client.post(f"/users/{owner['id']}/follow", headers=peer_auth).status_code == 204
        if index < 3:
            assert client.post(f"/users/{peer['id']}/follow", headers=auth).status_code == 204
    stats = client.get("/users/me/follow-stats", headers=auth)
    assert stats.json() == {"followers_count": 5, "following_count": 3}
    assert stats.headers["cache-control"] == "private, no-store"
    for kind, count in (("followers", 5), ("following", 3)):
        assert len(client.get(f"/users/me/{kind}", headers=auth).json()["items"]) == count
        assert (
            len(client.get(f"/users/{owner['id']}/{kind}", headers=auth).json()["items"]) == count
        )
        for params in ({}, {"limit": 1}, {"cursor": "invalid"}):
            assert (
                client.get(
                    f"/users/{owner['id']}/{kind}", headers=peers[0][1], params=params
                ).status_code
                == 404
            )
        first = client.get(f"/users/me/{kind}?limit=1", headers=auth).json()
        second = client.get(
            f"/users/me/{kind}", headers=auth, params={"limit": 1, "cursor": first["next_cursor"]}
        ).json()
        assert first["items"][0]["id"] != second["items"][0]["id"]
    for viewer in (auth, peers[0][1]):
        profile = client.get(f"/users/{owner['id']}/public-profile", headers=viewer).json()
        assert not {"followers_count", "following_count", "followers", "following"} & profile.keys()
    assert (
        client.get(f"/users/{owner['id']}/public-profile", headers=peers[0][1]).json()[
            "is_following"
        ]
        is True
    )
    assert client.get("/users/me/follow-stats", headers=peers[0][1]).json() == {
        "followers_count": 1,
        "following_count": 1,
    }


@pytest.mark.parametrize("path", ["follow-stats", "followers", "following"])
def test_private_graph_requires_auth(client, path):
    assert client.get(f"/users/me/{path}").status_code == 401


def test_following_two_account_privacy_and_discover_independence(client):
    a, auth_a = account(client, "alice@example.com")
    _, auth_b = account(client, "bravo@example.com")
    _, other = account(client, "other@example.com")
    public = journey(client, auth_a, "public")
    journey(client, auth_a, "private")
    journey(client, auth_b, "public")
    unrelated = journey(client, other, "public")
    assert client.get("/following/journeys", headers=auth_b).json()["following_count"] == 0
    client.post(f"/users/{a['id']}/follow", headers=auth_b)
    result = client.get("/following/journeys", headers=auth_b)
    assert result.headers["cache-control"] == "private, no-store"
    assert [x["id"] for x in result.json()["items"]] == [public["id"]]
    assert result.json()["following_count"] == 1
    client.post(f"/journeys/{public['id']}/save", headers=auth_b)
    assert client.get("/following/journeys", headers=auth_b).json()["items"][0]["is_saved"]
    client.patch(f"/journeys/{public['id']}", headers=auth_a, json={"visibility": "private"})
    for url in ("/following/journeys", "/saved/journeys", f"/users/{a['id']}/public-journeys"):
        assert client.get(url, headers=auth_b).json()["items"] == []
    assert client.get(f"/discover/journeys/{public['id']}", headers=auth_b).status_code == 404
    client.patch(f"/journeys/{public['id']}", headers=auth_a, json={"visibility": "public"})
    client.delete(f"/users/{a['id']}/follow", headers=auth_b)
    assert client.get("/following/journeys", headers=auth_b).json()["items"] == []
    assert {x["id"] for x in client.get("/discover/journeys", headers=auth_b).json()["items"]} == {
        public["id"],
        unrelated["id"],
    }


@pytest.mark.parametrize("kind", ["followers", "following", "feed"])
def test_follow_pagination_safe_fields_and_validation(client, kind):
    owner, auth = account(client, "owner@example.com")
    expected = []
    for index in range(5):
        person, person_auth = account(client, f"person{index}@example.com")
        if kind == "followers":
            client.post(f"/users/{owner['id']}/follow", headers=person_auth)
        else:
            client.post(f"/users/{person['id']}/follow", headers=auth)
        expected.append(
            journey(client, person_auth, "public")["id"] if kind == "feed" else person["id"]
        )
    url = "/following/journeys" if kind == "feed" else f"/users/{owner['id']}/{kind}"
    cursor, seen = None, []
    while True:
        result = client.get(
            url, headers=auth, params={"limit": 2, **({"cursor": cursor} if cursor else {})}
        )
        assert result.status_code == 200
        page = result.json()
        assert len(page["items"]) <= 2
        for item in page["items"]:
            if kind != "feed":
                assert set(item) == {"id", "username", "display_name", "avatar_url", "is_following"}
                assert item["is_following"] == (kind == "following")
            seen.append(item["id"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == list(reversed(expected))
    for params in ({"limit": 0}, {"limit": 51}, {"cursor": "bad"}):
        assert client.get(url, headers=auth, params=params).status_code == 422


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/users/{id}/follow"),
        ("delete", "/users/{id}/follow"),
        ("get", "/users/{id}/followers"),
        ("get", "/users/{id}/following"),
        ("get", "/following/journeys"),
    ],
)
def test_follow_auth(client, method, path):
    assert getattr(client, method)(path.format(id=uuid.uuid4())).status_code == 401


@pytest.mark.parametrize("delete_follower", [True, False])
def test_follow_delete_cascades(client, delete_follower):
    a, auth_a = account(client, "alice@example.com")
    b, _ = account(client, "bravo@example.com")
    client.post(f"/users/{b['id']}/follow", headers=auth_a)
    with Session(test_engine) as session:
        session.execute(
            delete(User).where(User.id == uuid.UUID((a if delete_follower else b)["id"]))
        )
        session.commit()
        assert session.scalar(select(func.count(UserFollow.id))) == 0


@pytest.mark.parametrize("size", [1, 8])
def test_follow_queries_constant(client, size):
    viewer, auth = account(client, "viewer@example.com")
    for index in range(size):
        person, person_auth = account(client, f"person{index}@example.com")
        client.post(f"/users/{person['id']}/follow", headers=auth)
        journey(client, person_auth, "public")
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(test_engine, "before_cursor_execute", capture)
    try:
        # The authenticated owner is already in SQLAlchemy's identity map.
        for url, count in (("/following/journeys", 6), (f"/users/{viewer['id']}/following", 3)):
            statements.clear()
            response = client.get(url, headers=auth)
            assert response.status_code == 200
            assert len(response.json()["items"]) == size
            assert len(statements) == count
    finally:
        event.remove(test_engine, "before_cursor_execute", capture)
