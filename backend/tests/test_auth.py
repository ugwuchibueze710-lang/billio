def test_signup_requires_no_email(client):
    resp = client.post(
        "/api/auth/signup",
        json={
            "first_name": "Israel",
            "username": "israel1",
            "password": "Str0ngPass!1",
            "confirm_password": "Str0ngPass!1",
        },
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["user"]["email"] is None
    assert "access_token" in body and "refresh_token" in body


def test_signup_rejects_weak_password(client):
    resp = client.post(
        "/api/auth/signup",
        json={"first_name": "A", "username": "weakpw", "password": "password", "confirm_password": "password"},
    )
    assert resp.status_code == 422


def test_signup_rejects_mismatched_confirmation(client):
    resp = client.post(
        "/api/auth/signup",
        json={"first_name": "A", "username": "mismatch1", "password": "Str0ngPass!1", "confirm_password": "Different!1"},
    )
    assert resp.status_code == 422


def test_signup_rejects_duplicate_username_case_insensitive(client):
    payload = {"first_name": "A", "username": "dupeuser", "password": "Str0ngPass!1", "confirm_password": "Str0ngPass!1"}
    r1 = client.post("/api/auth/signup", json=payload)
    assert r1.status_code == 201
    payload2 = dict(payload, username="DupeUser")
    r2 = client.post("/api/auth/signup", json=payload2)
    assert r2.status_code == 409


def test_password_hash_never_returned(client, auth_headers):
    headers, _ = auth_headers(username="hashcheck")
    resp = client.get("/api/auth/me", headers=headers)
    body = resp.get_json()
    assert "password_hash" not in body["user"]
    assert "password" not in body["user"]


def test_login_wrong_password_rejected(client, make_user):
    make_user(username="loginfail", password="Str0ngPass!1")
    resp = client.post("/api/auth/login", json={"username": "loginfail", "password": "WrongPass!1"})
    assert resp.status_code == 401


def test_login_nonexistent_user_same_error_as_wrong_password(client):
    resp = client.post("/api/auth/login", json={"username": "doesnotexist", "password": "whatever123"})
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "authentication_error"


def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 401


def test_invalid_token_rejected(client):
    resp = client.get("/api/dashboard", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_change_password_invalidates_old_tokens(client, auth_headers):
    headers, _ = auth_headers(username="changepw", password="Str0ngPass!1")

    resp = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "Str0ngPass!1", "new_password": "NewStr0ngPass!2", "confirm_new_password": "NewStr0ngPass!2"},
    )
    assert resp.status_code == 200

    # The OLD access token must now be rejected even though it hasn't expired.
    stale_resp = client.get("/api/auth/me", headers=headers)
    assert stale_resp.status_code == 401

    # New token from the change-password response works.
    new_token = resp.get_json()["access_token"]
    fresh_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert fresh_resp.status_code == 200


def test_logout_revokes_token(client, auth_headers):
    headers, _ = auth_headers(username="logouttest")
    resp = client.post("/api/auth/logout", headers=headers)
    assert resp.status_code == 200

    after = client.get("/api/auth/me", headers=headers)
    assert after.status_code == 401


def test_forgot_password_generic_response_for_unknown_user(client):
    resp = client.post("/api/auth/forgot-password", json={"username_or_email": "nobody"})
    assert resp.status_code == 200
    assert "message" in resp.get_json()


def test_forgot_password_generic_response_when_no_email_on_file(client, make_user):
    make_user(username="noemailuser")
    resp = client.post("/api/auth/forgot-password", json={"username_or_email": "noemailuser"})
    # Same generic message whether or not the account/email exists -- must
    # not leak account existence or email-on-file status.
    assert resp.status_code == 200
    assert "message" in resp.get_json()
