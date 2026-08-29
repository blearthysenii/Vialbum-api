from fastapi.testclient import TestClient


def register_user(
    client: TestClient,
    *,
    email: str = "traveler@example.com",
    password: str = "a-strong-test-password",
) -> dict[str, object]:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Vialbum",
            "last_name": "Traveler",
        },
    )
    assert response.status_code == 201
    return response.json()


def login_user(
    client: TestClient,
    *,
    email: str = "traveler@example.com",
    password: str = "a-strong-test-password",
) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def journey_payload(title: str = "Medina 2025") -> dict[str, object]:
    return {
        "title": title,
        "destination": "Medina",
        "country": "Saudi Arabia",
        "start_date": "2025-03-12",
        "end_date": "2025-03-19",
        "description": "A journey to remember.",
    }
