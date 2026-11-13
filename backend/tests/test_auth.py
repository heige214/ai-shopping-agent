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
