from unittest.mock import patch

from fastapi.testclient import TestClient


def test_api_info(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "Vialbum API"


def test_health(client: TestClient) -> None:
    with patch("app.api.routes.system.database_is_available", return_value=True):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected"}


def test_health_when_database_is_unavailable(client: TestClient) -> None:
    with patch("app.api.routes.system.database_is_available", return_value=False):
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "unavailable"}
