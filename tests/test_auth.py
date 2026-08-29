from fastapi.testclient import TestClient

from tests.helpers import auth_headers, login_user, register_user


def test_register_successfully(client: TestClient) -> None:
    user = register_user(client, email=" Traveler@Example.COM ")
    assert user["email"] == "traveler@example.com"
    assert "password" not in user
    assert "password_hash" not in user


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    register_user(client)
    response = client.post(
        "/auth/register",
        json={
            "email": "TRAVELER@example.com",
            "password": "another-strong-password",
            "first_name": "Other",
            "last_name": "Traveler",
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "An account with this email already exists"}


def test_login_successfully(client: TestClient) -> None:
    register_user(client)
    response = client.post(
        "/auth/login",
        json={"email": "traveler@example.com", "password": "a-strong-test-password"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_rejects_invalid_password(client: TestClient) -> None:
    register_user(client)
    response = client.post(
        "/auth/login",
        json={"email": "traveler@example.com", "password": "incorrect-password"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_me_returns_authenticated_user(client: TestClient) -> None:
    registered = register_user(client)
    token = login_user(client)
    response = client.get("/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["id"] == registered["id"]


def test_me_requires_token(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/auth/me", headers=auth_headers("not-a-valid-jwt"))
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}
