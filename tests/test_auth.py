from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from tests.helpers import auth_headers, login_user, register_user


def test_register_successfully(client: TestClient) -> None:
    user = register_user(client, email=" Traveler@Example.COM ")
    assert user["email"] == "traveler@example.com"
    assert user["username"] == "traveler"
    assert "password" not in user
    assert "password_hash" not in user


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    register_user(client)
    response = client.post(
        "/auth/register",
        json={
            "email": "TRAVELER@example.com",
            "username": "other_traveler",
            "password": "another-strong-password",
            "first_name": "Other",
            "last_name": "Traveler",
        },
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "This email is already registered with Vialbum.",
        "code": "EMAIL_ALREADY_REGISTERED",
    }


def test_login_successfully(client: TestClient) -> None:
    register_user(client)
    response = client.post(
        "/auth/login",
        json={"email": "traveler@example.com", "password": "a-strong-test-password"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_successfully_with_username(client: TestClient) -> None:
    register_user(client, username="Travel_Log")
    response = client.post(
        "/auth/login",
        json={"identifier": " travel_log ", "password": "a-strong-test-password"},
    )
    assert response.status_code == 200


def test_register_rejects_case_insensitive_duplicate_username(client: TestClient) -> None:
    register_user(client, username="travel_log")
    response = client.post(
        "/auth/register",
        json={
            "email": "other@example.com",
            "username": "TRAVEL_LOG",
            "password": "another-strong-password",
            "first_name": "Other",
            "last_name": "Traveler",
        },
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "This username is already taken.",
        "code": "USERNAME_TAKEN",
    }


def test_login_rejects_invalid_password(client: TestClient) -> None:
    register_user(client)
    response = client.post(
        "/auth/login",
        json={"email": "traveler@example.com", "password": "incorrect-password"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "The email, username, or password is incorrect"}


def test_email_exists_returns_true_for_normalized_existing_email(client: TestClient) -> None:
    register_user(client)

    response = client.post("/auth/email-exists", json={"email": " TRAVELER@example.com "})

    assert response.status_code == 200
    assert response.json() == {"exists": True}


def test_email_exists_returns_false_for_unknown_email(client: TestClient) -> None:
    response = client.post("/auth/email-exists", json={"email": "unknown@example.com"})

    assert response.status_code == 200
    assert response.json() == {"exists": False}


def test_username_and_account_availability_are_case_insensitive(client: TestClient) -> None:
    register_user(client, username="travel_log")
    username_response = client.post("/auth/username-exists", json={"username": "TRAVEL_LOG"})
    account_response = client.post("/auth/account-exists", json={"identifier": " Travel_Log "})
    assert username_response.json() == {"exists": True}
    assert account_response.json() == {"exists": True}


def test_parallel_registration_cannot_duplicate_username(client: TestClient) -> None:
    def register(index: int):
        return client.post(
            "/auth/register",
            json={
                "email": f"parallel-{index}@example.com",
                "username": "same_username",
                "password": "a-strong-test-password",
                "first_name": "Parallel",
                "last_name": "Traveler",
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(register, range(2)))

    assert sorted(response.status_code for response in responses) == [201, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["code"] == "USERNAME_TAKEN"


def test_me_returns_authenticated_user(client: TestClient) -> None:
    registered = register_user(client)
    token = login_user(client)
    response = client.get("/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["id"] == registered["id"]
    assert response.json()["bio"] is None
    assert response.json()["location"] is None
    assert response.json()["profile_photo_url"] is None


def test_user_can_update_own_profile(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)
    response = client.patch(
        "/users/me",
        headers=auth_headers(token),
        json={
            "first_name": "  New  ",
            "last_name": " Name ",
            "username": "NEW_TRAVELER",
            "bio": "  Places and stories. ",
            "location": "  Prishtina  ",
        },
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "New"
    assert response.json()["last_name"] == "Name"
    assert response.json()["username"] == "new_traveler"
    assert response.json()["bio"] == "Places and stories."
    assert response.json()["location"] == "Prishtina"


def test_profile_update_rejects_another_users_username(client: TestClient) -> None:
    register_user(client, email="first@example.com", username="first_user")
    register_user(client, email="second@example.com", username="second_user")
    token = login_user(client, email="second@example.com")
    response = client.patch(
        "/users/me",
        headers=auth_headers(token),
        json={
            "first_name": "Second",
            "last_name": "User",
            "username": "FIRST_USER",
            "bio": None,
            "location": None,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "USERNAME_TAKEN"


def test_profile_photo_upload_replaces_and_remove_deletes_private_objects(
    client: TestClient, fake_storage: object
) -> None:
    register_user(client)
    token = login_user(client)
    headers = auth_headers(token)
    first = client.post(
        "/users/me/profile-photo",
        headers=headers,
        files={"file": ("first.jpg", b"\xff\xd8\xfffirst", "image/jpeg")},
    )
    assert first.status_code == 200
    assert first.json()["profile_photo_url"].startswith("https://private-storage.test/")
    first_key = next(iter(fake_storage.objects))  # type: ignore[attr-defined]

    second = client.post(
        "/users/me/profile-photo",
        headers=headers,
        files={"file": ("second.jpg", b"\xff\xd8\xffsecond", "image/jpeg")},
    )
    assert second.status_code == 200
    assert first_key in fake_storage.deleted_keys  # type: ignore[attr-defined]

    removed = client.delete("/users/me/profile-photo", headers=headers)
    assert removed.status_code == 204
    me = client.get("/auth/me", headers=headers)
    assert me.json()["profile_photo_url"] is None


def test_me_requires_token(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/auth/me", headers=auth_headers("not-a-valid-jwt"))
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}
