from fastapi.testclient import TestClient

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
