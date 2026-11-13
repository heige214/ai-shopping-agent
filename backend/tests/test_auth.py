import asyncio
import os

import asyncpg

from app.core.security import verify_password


def register(
    client,
    username: str = "alice",
    password: str = "secret123",
    nickname: str | None = "Alice",
):
    payload = {"username": username, "password": password}
    if nickname is not None:
        payload["nickname"] = nickname
    return client.post("/api/auth/register", json=payload)


def test_register_returns_user_without_password_hash(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert body["nickname"] == "Alice"
    assert body["role"] == "user"
    assert "password_hash" not in body


def test_register_duplicate_username_returns_409(client):
    register(client)
    response = register(client)
    assert response.status_code == 409
    assert response.json()["detail"] == "用户名已被注册"


def test_register_rejects_short_password(client):
    response = register(client, password="12345")
    assert response.status_code == 422


def test_register_rejects_password_over_72_bytes(client):
    response = register(client, password="密" * 30)
    assert response.status_code == 422


def test_register_without_nickname_uses_username(client):
    response = register(client, nickname=None)
    assert response.status_code == 201
    assert response.json()["nickname"] == "alice"


def fetch_password_hash(username: str) -> str:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def _fetch() -> str:
        connection = await asyncpg.connect(dsn)
        try:
            return await connection.fetchval(
                "SELECT password_hash FROM users WHERE username = $1", username
            )
        finally:
            await connection.close()

    return asyncio.run(_fetch())


def test_register_strips_username(client):
    response = register(client, username="  alice  ")
    assert response.status_code == 201
    assert response.json()["username"] == "alice"


def test_register_blank_nickname_uses_username(client):
    response = register(client, username="bob", nickname="   ")
    assert response.status_code == 201
    assert response.json()["nickname"] == "bob"


def test_register_accepts_exactly_72_byte_password(client):
    response = register(client, password="a" * 72)
    assert response.status_code == 201


def test_register_rejects_73_byte_password(client):
    response = register(client, password="a" * 73)
    assert response.status_code == 422


def test_register_rejects_nickname_with_nul(client):
    response = register(client, username="nulnick", nickname="a\u0000b")
    assert response.status_code == 422


def test_register_validation_error_does_not_echo_password(client):
    response = register(client, password="12345")
    assert response.status_code == 422
    assert "12345" not in response.text


def test_register_missing_username_does_not_echo_password(client):
    response = client.post("/api/auth/register", json={"password": "secret123"})
    assert response.status_code == 422
    assert "secret123" not in response.text


def test_register_lone_surrogate_returns_422(client):
    response = client.post(
        "/api/auth/register",
        content=b'{"username":"\\ud800","password":"secret123"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_register_stores_bcrypt_hash(client):
    response = register(client, password="secret123")
    assert response.status_code == 201
    password_hash = fetch_password_hash("alice")
    assert password_hash.startswith("$2b$")
    assert verify_password("secret123", password_hash)


def test_register_username_is_case_sensitive(client):
    assert register(client, username="alice").status_code == 201
    assert register(client, username="Alice").status_code == 201


def login(client, username: str = "alice", password: str = "secret123"):
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


def test_login_returns_token_and_user(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "alice"


def test_login_with_wrong_password_returns_401(client):
    register(client)
    response = login(client, password="wrong-password")
    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码错误"


def test_login_with_unknown_user_returns_same_message(client):
    response = login(client, username="nobody", password="wrong-password")
    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码错误"


def test_me_requires_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "未登录或登录已过期"


def test_me_returns_current_user(client):
    register(client)
    token = login(client).json()["access_token"]
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_me_with_invalid_token_returns_401(client):
    response = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401
