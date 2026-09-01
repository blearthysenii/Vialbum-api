import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.place import Place
from tests.conftest import test_engine
from tests.helpers import auth_headers, journey_payload, login_user, register_user


def authenticated_headers(client: TestClient) -> dict[str, str]:
    register_user(client)
    return auth_headers(login_user(client))


def create_journey(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    response = client.post("/journeys", json=journey_payload(), headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_journey(client: TestClient) -> None:
    journey = create_journey(client, authenticated_headers(client))
    assert journey["title"] == "Medina 2025"
    assert "user_id" not in journey


def test_list_own_journeys_newest_first(client: TestClient) -> None:
    headers = authenticated_headers(client)
    create_journey(client, headers)
    second = client.post("/journeys", json=journey_payload("Milan 2026"), headers=headers)
    assert second.status_code == 201
    response = client.get("/journeys", headers=headers)
    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Milan 2026", "Medina 2025"]


def test_get_own_journey(client: TestClient) -> None:
    headers = authenticated_headers(client)
    journey = create_journey(client, headers)
    response = client.get(f"/journeys/{journey['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == journey["id"]


def test_update_own_journey(client: TestClient) -> None:
    headers = authenticated_headers(client)
    journey = create_journey(client, headers)
    response = client.patch(
        f"/journeys/{journey['id']}", json={"title": "Medina Memories"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Medina Memories"


def test_partial_update_preserves_other_fields(client: TestClient) -> None:
    headers = authenticated_headers(client)
    journey = create_journey(client, headers)
    response = client.patch(
        f"/journeys/{journey['id']}", json={"description": "Updated notes."}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated notes."
    assert response.json()["title"] == journey["title"]


def test_rejects_invalid_date_range(client: TestClient) -> None:
    response = client.post(
        "/journeys",
        json={**journey_payload(), "start_date": "2025-03-20", "end_date": "2025-03-19"},
        headers=authenticated_headers(client),
    )
    assert response.status_code == 422


def test_journeys_require_authentication(client: TestClient) -> None:
    assert client.get("/journeys").status_code == 401


def test_delete_own_journey(client: TestClient) -> None:
    headers = authenticated_headers(client)
    journey = create_journey(client, headers)
    response = client.delete(f"/journeys/{journey['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/journeys/{journey['id']}", headers=headers).status_code == 404


def another_user_scenario(client: TestClient) -> tuple[str, dict[str, str]]:
    owner_headers = authenticated_headers(client)
    journey = create_journey(client, owner_headers)
    register_user(client, email="other@example.com", password="other-strong-password")
    other_headers = auth_headers(
        login_user(client, email="other@example.com", password="other-strong-password")
    )
    return f"/journeys/{journey['id']}", other_headers


def test_cannot_read_another_users_journey(client: TestClient) -> None:
    journey_url, headers = another_user_scenario(client)
    assert client.get(journey_url, headers=headers).status_code == 404


def test_cannot_update_another_users_journey(client: TestClient) -> None:
    journey_url, headers = another_user_scenario(client)
    assert client.patch(journey_url, json={"title": "Stolen"}, headers=headers).status_code == 404


def test_cannot_delete_another_users_journey(client: TestClient) -> None:
    journey_url, headers = another_user_scenario(client)
    assert client.delete(journey_url, headers=headers).status_code == 404


PLACE = {
    "provider": "geoapify",
    "provider_place_id": "medina-1",
    "display_name": "Medina, Al Madinah, Saudi Arabia",
    "name": "Medina",
    "locality": "Medina",
    "region": "Al Madinah",
    "country": "Saudi Arabia",
    "country_code": "SA",
    "latitude": "24.468600",
    "longitude": "39.614200",
}


def test_create_assigns_normalized_place_and_coordinates(client: TestClient) -> None:
    response = client.post(
        "/journeys",
        json={**journey_payload(), "destination": "old", "country": "old", "place": PLACE},
        headers=authenticated_headers(client),
    )
    assert response.status_code == 201
    journey = response.json()
    assert journey["place_id"] == journey["place"]["id"]
    assert journey["destination"] == "Medina"
    assert journey["country"] == "Saudi Arabia"
    assert journey["latitude"] == "24.468600"
    assert journey["longitude"] == "39.614200"


def test_place_assignment_deduplicates_provider_identity(client: TestClient) -> None:
    headers = authenticated_headers(client)
    for title in ("One", "Two"):
        response = client.post(
            "/journeys", json={**journey_payload(title), "place": PLACE}, headers=headers
        )
        assert response.status_code == 201
    with Session(test_engine) as session:
        assert session.scalar(select(func.count()).select_from(Place)) == 1


def test_provider_identity_has_database_uniqueness(client: TestClient) -> None:
    headers = authenticated_headers(client)
    response = client.post("/journeys", json={**journey_payload(), "place": PLACE}, headers=headers)
    assert response.status_code == 201
    with Session(test_engine) as session:
        duplicate = Place(
            **{
                **PLACE,
                "latitude": PLACE["latitude"],
                "longitude": PLACE["longitude"],
            }
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()


def test_manual_coordinates_override_normalized_place(client: TestClient) -> None:
    response = client.post(
        "/journeys",
        json={
            **journey_payload(),
            "place": PLACE,
            "latitude": "24.500000",
            "longitude": "39.700000",
        },
        headers=authenticated_headers(client),
    )
    assert response.status_code == 201
    assert response.json()["latitude"] == "24.500000"
    assert response.json()["place"]["latitude"] == "24.468600"


def test_update_assigns_and_clears_place_without_erasing_labels(client: TestClient) -> None:
    headers = authenticated_headers(client)
    journey = create_journey(client, headers)
    assigned = client.patch(f"/journeys/{journey['id']}", json={"place": PLACE}, headers=headers)
    assert assigned.status_code == 200
    cleared = client.patch(f"/journeys/{journey['id']}", json={"place": None}, headers=headers)
    assert cleared.status_code == 200
    payload = cleared.json()
    assert payload["place_id"] is None
    assert payload["place"] is None
    assert payload["latitude"] is None
    assert payload["longitude"] is None
    assert payload["destination"] == "Medina"
    assert payload["country"] == "Saudi Arabia"


def test_cannot_assign_place_to_another_users_journey(client: TestClient) -> None:
    journey_url, headers = another_user_scenario(client)
    assert client.patch(journey_url, json={"place": PLACE}, headers=headers).status_code == 404
