"""Authentication: registration, login, JWT-protected routes."""


def _payload(**overrides):
    base = {"email": "carol@example.com", "password": "long-enough-pass", "full_name": "Carol"}
    base.update(overrides)
    return base


def test_register_creates_user_without_exposing_password_hash(client):
    response = client.post("/api/v1/auth/register", json=_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "carol@example.com"
    assert body["role"] == "user"
    assert "password" not in body and "password_hash" not in body


def test_register_rejects_duplicate_email_with_409(client):
    assert client.post("/api/v1/auth/register", json=_payload()).status_code == 201
    response = client.post("/api/v1/auth/register", json=_payload(email="CAROL@example.com"))
    assert response.status_code == 409


def test_register_rejects_malformed_email(client):
    response = client.post("/api/v1/auth/register", json=_payload(email="not-an-email"))
    assert response.status_code == 422


def test_register_rejects_short_password(client):
    response = client.post("/api/v1/auth/register", json=_payload(password="short"))
    assert response.status_code == 422


def test_login_returns_bearer_token(client):
    client.post("/api/v1/auth/register", json=_payload())
    response = client.post(
        "/api/v1/auth/login", json={"email": "carol@example.com", "password": "long-enough-pass"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_error_is_identical_for_wrong_password_and_unknown_email(client):
    client.post("/api/v1/auth/register", json=_payload())
    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": "carol@example.com", "password": "wrong-password-here"}
    )
    unknown_email = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-here"}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_me_requires_a_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_rejects_a_garbage_token(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == 401


def test_me_returns_the_logged_in_user(client, user_a):
    response = client.get("/api/v1/auth/me", headers={"Authorization": user_a["Authorization"]})
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"
