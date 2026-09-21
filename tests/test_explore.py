import uuid

import pytest
from sqlalchemy import event

from tests.conftest import test_engine
from tests.helpers import journey_payload
from tests.test_discover import account
from tests.test_media import PLACE_SELECTION


def trip(client, auth, title="Lake Como", visibility="public", place_id="lake-como"):
    response = client.post(
        "/journeys",
        headers=auth,
        json={
            **journey_payload(title),
            "country": "Italy",
            "destination": "Lombardy",
            "visibility": visibility,
            "place": {
                **PLACE_SELECTION,
                "provider_place_id": place_id,
                "name": title,
                "display_name": title + ", Italy",
                "locality": "Como",
                "region": "Lombardy",
                "country": "Italy",
                "country_code": "IT",
                "latitude": "45.990000",
                "longitude": "9.260000",
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def search(client, auth, q, **params):
    result = client.get("/explore/search", headers=auth, params={"q": q, **params})
    assert result.status_code == 200, result.text
    return result.json()


def test_explore_required_privacy_scenario(client):
    anna, a = account(client, "anna@example.com")
    _, b = account(client, "viewer@example.com")
    public = trip(client, a)
    trip(client, a, "Private lake", "private", "private-lake")
    trip(client, b, "Own lake", "public", "own-lake")
    for q in ("italy", "lake como", "lombardy", "como"):
        results = search(client, b, q)
        assert [item["id"] for item in results["journeys"]["items"]] == [public["id"]]
        assert [item["id"] for item in results["places"]["items"]] == [public["place"]["id"]]
    people = search(client, b, "@anna")["users"]["items"]
    assert people[0]["id"] == anna["id"]
    assert set(people[0]) == {"id", "username", "display_name", "avatar_url", "is_following"}
    client.post(f"/users/{anna['id']}/follow", headers=b)
    assert search(client, b, "@anna")["users"]["items"][0]["is_following"]
    client.post(f"/journeys/{public['id']}/save", headers=b)
    assert search(client, b, "italy")["journeys"]["items"][0]["is_saved"]
    place_url = f"/explore/places/{public['place']['id']}"
    result = client.get(place_url, headers=b)
    assert result.headers["cache-control"] == "private, no-store"
    assert result.json()["place"]["public_journeys_count"] == 1
    assert result.json()["journeys"]["items"][0]["id"] == public["id"]
    client.patch(f"/journeys/{public['id']}", headers=a, json={"visibility": "private"})
    assert search(client, b, "italy")["journeys"]["items"] == []
    assert search(client, b, "italy")["places"]["items"] == []
    assert client.get(place_url, headers=b).status_code == 404


def test_user_ranking_name_prefix_partial_and_private_fields(client):
    _, viewer = account(client, "viewer@example.com")
    expected = []
    for username, first in (
        ("anna", "Other"),
        ("annabelle", "Other"),
        ("traveler", "Anna"),
        ("joanna", "Other"),
    ):
        response = client.post(
            "/auth/register",
            json={
                "username": username,
                "email": username + "@example.com",
                "password": "a-strong-test-password",
                "first_name": first,
                "last_name": "Traveler",
            },
        )
        assert response.status_code == 201
        expected.append(response.json()["id"])
    results = search(client, viewer, "anna", type="users")
    assert [item["id"] for item in results["users"]["items"]] == expected
    assert search(client, viewer, "Anna Traveler")["users"]["items"][0]["id"] == expected[2]
    payload = str(results)
    for secret in ("email", "password", "followers_count", "following_count", "storage_key"):
        assert secret not in payload


@pytest.mark.parametrize("kind", ["users", "journeys", "places"])
def test_search_keyset_pagination(client, kind):
    _, viewer = account(client, "viewer@example.com")
    _, owner = account(client, "owner@example.com")
    for i in range(5):
        if kind == "users":
            account(client, f"zztraveler{i}@example.com")
        else:
            trip(client, owner, f"Zztraveler {i}", place_id=f"place-{i}")
    seen, cursor = [], None
    while True:
        page = search(
            client,
            viewer,
            "zztraveler",
            type=kind,
            limit=2,
            **({"cursor": cursor} if cursor else {}),
        )[kind]
        assert len(page["items"]) <= 2
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 5
    assert seen == sorted(seen)
    first = search(client, viewer, "zztraveler", type=kind, limit=1)[kind]
    assert (
        client.get(
            "/explore/search",
            headers=viewer,
            params={"q": "different", "type": kind, "cursor": first["next_cursor"]},
        ).status_code
        == 422
    )


def test_place_pagination_and_private_place_not_accessible(client):
    _, viewer = account(client, "viewer@example.com")
    _, owner = account(client, "owner@example.com")
    items = [trip(client, owner) for _ in range(5)]
    private = trip(client, owner, "Hidden", "private", "hidden")
    own = trip(client, viewer, "Own", "public", "own")
    cursor, seen = None, []
    while True:
        result = client.get(
            f"/explore/places/{items[0]['place']['id']}",
            headers=viewer,
            params={"limit": 2, **({"cursor": cursor} if cursor else {})},
        )
        assert result.status_code == 200
        page = result.json()["journeys"]
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == [item["id"] for item in reversed(items)]
    for identifier in (private["place"]["id"], own["place"]["id"], str(uuid.uuid4())):
        assert client.get(f"/explore/places/{identifier}", headers=viewer).status_code == 404


def test_explore_auth_validation_and_literal_wildcards(client):
    _, viewer = account(client, "viewer@example.com")
    assert client.get("/explore/search?q=italy").status_code == 401
    assert client.get(f"/explore/places/{uuid.uuid4()}").status_code == 401
    for params in (
        {"q": "x"},
        {"q": "  "},
        {"q": "@a"},
        {"q": "a" * 101},
        {"q": "italy", "limit": 51},
        {"q": "italy", "limit": 0},
        {"q": "italy", "type": "photos"},
        {"q": "italy", "cursor": "bad", "type": "users"},
    ):
        assert client.get("/explore/search", headers=viewer, params=params).status_code == 422
    assert search(client, viewer, "%%")["users"]["items"] == []
    assert search(client, viewer, "__")["users"]["items"] == []


@pytest.mark.parametrize("size", [1, 8])
def test_search_constant_query_count(client, size):
    _, viewer = account(client, "viewer@example.com")
    for i in range(size):
        _, owner = account(client, f"italy{i}@example.com")
        trip(client, owner, f"Italy {i}", place_id=f"italy-{i}")
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(test_engine, "before_cursor_execute", capture)
    try:
        response = search(client, viewer, "italy")
        assert len(response["journeys"]["items"]) == size
        assert len(statements) == 8  # Auth + 3 groups + followed IDs + grouped card counts/saves.
    finally:
        event.remove(test_engine, "before_cursor_execute", capture)
