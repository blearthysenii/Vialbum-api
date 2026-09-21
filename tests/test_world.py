import uuid

import pytest
from sqlalchemy import event

from tests.conftest import test_engine
from tests.helpers import journey_payload
from tests.test_discover import account
from tests.test_media import PLACE_SELECTION

WORLD = {"north": 90, "south": -90, "west": -180, "east": 180, "zoom": 12}


def visit(
    client,
    auth,
    name,
    lat,
    lon,
    visibility="private",
    code="IT",
    country="Italy",
    city=None,
    identity=None,
):
    response = client.post(
        "/journeys",
        headers=auth,
        json={
            **journey_payload(name),
            "visibility": visibility,
            "place": {
                **PLACE_SELECTION,
                "provider_place_id": identity or name,
                "name": name,
                "display_name": name,
                "locality": city or name,
                "region": None,
                "country": country,
                "country_code": code,
                "latitude": f"{lat:.6f}",
                "longitude": f"{lon:.6f}",
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def get_map(client, auth, own=False, **params):
    response = client.get(
        "/users/me/world" if own else "/explore/map", headers=auth, params={**WORLD, **params}
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    return response.json()


def test_required_public_private_and_own_exclusion(client):
    _, a = account(client, "alice@example.com")
    _, b = account(client, "bravo@example.com")
    milan = visit(client, a, "Milan", 45.46, 9.19, "public")
    como = visit(client, a, "Lake Como", 46, 9.3)
    medina = visit(client, a, "Medina", 24.47, 39.61, code="SA", country="Saudi Arabia")
    visit(client, b, "Tokyo", 35.67, 139.65, "public", "JP", "Japan")
    public = get_map(client, b)
    assert [x["place_id"] for x in public["items"]] == [milan["place"]["id"]]
    assert not {"stats", "countries", "followers_count", "following_count"} & public.keys()
    assert set(public["items"][0]) == {
        "id",
        "type",
        "place_id",
        "name",
        "country",
        "latitude",
        "longitude",
        "place_count",
        "journey_count",
        "bounds",
    }
    own = get_map(client, a, True)
    assert {x["place_id"] for x in own["items"]} == {
        x["place"]["id"] for x in (milan, como, medina)
    }
    assert own["stats"] == {"journeys": 3, "countries": 2, "cities": 3, "places": 3}
    client.patch(f"/journeys/{milan['id']}", headers=a, json={"visibility": "private"})
    assert get_map(client, b)["items"] == []
    assert len(get_map(client, a, True)["items"]) == 3


def test_aggregation_normalized_dedup_and_city_country_codes(client):
    _, a = account(client, "alice@example.com")
    _, b = account(client, "bravo@example.com")
    first = visit(client, a, "Milan", 45.46, 9.19, "public", city="Milan")
    visit(client, a, "Milano", 45.46, 9.19, "private", identity="Milan", city="Milano")
    visit(client, a, "Museum", 45.47, 9.20, city="Milan", country="Italia")
    own = get_map(client, a, True)
    assert own["stats"] == {"journeys": 3, "countries": 1, "cities": 1, "places": 2}
    assert len(own["countries"]) == 1
    public = get_map(client, b)
    assert public["items"][0]["journey_count"] == 1
    personal = client.get(f"/users/me/world/places/{first['place']['id']}", headers=a).json()
    assert personal["journey_count"] == 2
    assert len(personal["journeys"]) == 2
    assert (
        client.get(f"/users/me/world/places/{first['place']['id']}", headers=b).status_code == 404
    )


def test_viewport_and_antimeridian(client):
    _, a = account(client, "alice@example.com")
    _, b = account(client, "bravo@example.com")
    visit(client, a, "East", 10, 179, "public")
    visit(client, a, "West", 10, -179, "public")
    visit(client, a, "Center", 10, 0, "public")
    result = get_map(client, b, west=170, east=-170, north=20, south=0)
    assert {x["name"] for x in result["items"]} == {"East", "West"}
    assert get_map(client, b, north=5, south=-5)["items"] == []
    assert len(get_map(client, b, west=-1, east=1)["items"]) == 1


def test_clusters_and_bounded_raw_pagination(client):
    _, a = account(client, "alice@example.com")
    _, b = account(client, "bravo@example.com")
    for i in range(5):
        visit(client, a, f"Place {i}", 45.1 + i / 10000, 9.1, "public")
    grouped = get_map(client, b, zoom=2)
    assert len(grouped["items"]) == 1
    cluster = grouped["items"][0]
    assert cluster["type"] == "cluster"
    assert cluster["place_count"] == cluster["journey_count"] == 5
    assert cluster["place_id"] is None and cluster["name"] is None
    ids, cursor = [], None
    while True:
        page = get_map(client, b, grouped=False, limit=2, **({"cursor": cursor} if cursor else {}))
        assert len(page["items"]) <= 2
        ids.extend(item["place_id"] for item in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(ids) == len(set(ids)) == 5
    assert ids == sorted(ids)
    assert len(get_map(client, b, zoom=20)["items"]) == 5


def test_own_place_pagination_and_account_scoping(client):
    a_user, a = account(client, "alice@example.com")
    _, b = account(client, "bravo@example.com")
    journeys = [visit(client, a, "Milan", 45, 9) for _ in range(4)]
    url = f"/users/me/world/places/{journeys[0]['place']['id']}"
    first = client.get(url, headers=a, params={"limit": 2}).json()
    second = client.get(url, headers=a, params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert [x["id"] for x in first["journeys"] + second["journeys"]] == [
        x["id"] for x in reversed(journeys)
    ]
    assert get_map(client, b, True)["stats"]["places"] == 0
    assert get_map(client, b, True)["bounds"] is None
    assert client.get(url, headers=b).status_code == 404
    assert client.get(f"/users/{a_user['id']}/world", headers=b, params=WORLD).status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/explore/map",
        "/users/me/world",
        "/users/me/world/places/00000000-0000-0000-0000-000000000000",
    ],
)
def test_world_auth(client, path):
    assert client.get(path, params=WORLD).status_code == 401


@pytest.mark.parametrize(
    "params",
    [
        {"north": 91},
        {"south": 20, "north": 10},
        {"zoom": -1},
        {"zoom": 21},
        {"limit": 501},
        {"west": "NaN"},
        {"cursor": str(uuid.uuid4())},
    ],
)
def test_viewport_validation(client, params):
    _, a = account(client, "alice@example.com")
    assert client.get("/explore/map", headers=a, params={**WORLD, **params}).status_code == 422


@pytest.mark.parametrize("size", [1, 8])
def test_world_query_count_constant(client, size):
    _, a = account(client, "alice@example.com")
    _, b = account(client, "bravo@example.com")
    for i in range(size):
        visit(client, a, f"Place {i}", 45 + i / 10, 9, "public")
    statements = []

    def capture(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(test_engine, "before_cursor_execute", capture)
    try:
        get_map(client, b)
        assert len(statements) == 2
        statements.clear()
        get_map(client, a, True)
        assert len(statements) == 4
    finally:
        event.remove(test_engine, "before_cursor_execute", capture)
