import asyncio
import json
import os

import asyncpg


def register_and_login(client, username: str = "support_user") -> dict:
    payload = {"username": username, "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_support_session(client, headers, product_id: int):
    return client.post(
        "/api/chat/sessions",
        json={"type": "support", "product_id": product_id},
        headers=headers,
    )


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.split("\n\n"):
        event = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if event is not None:
            events.append((event, data or {}))
    return events


def send_message(client, headers, session_id: int, text: str):
    with client.stream(
        "POST",
        f"/api/chat/sessions/{session_id}/messages",
        json={"content_type": "text", "content": {"text": text}},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        return parse_sse("".join(response.iter_text()))


def fetch_int(query: str, *params) -> int:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def _run():
        connection = await asyncpg.connect(dsn)
        try:
            return int(await connection.fetchval(query, *params))
        finally:
            await connection.close()

    return asyncio.run(_run())


def test_create_session_reuses_active_support_and_allows_guide(
    client, sample_knowledge
):
    headers = register_and_login(client)
    product_id = sample_knowledge["product_a_id"]

    first = create_support_session(client, headers, product_id)
    assert first.status_code == 201
    session = first.json()
    assert session["type"] == "support"
    assert session["status"] == "active"
    assert session["product"]["title"] == "测试衬衫"

    messages = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers
    ).json()
    assert len(messages["items"]) == 1
    assert messages["items"][0]["sender_type"] == "ai"
    assert "AI 客服" in messages["items"][0]["content"]["text"]

    second = create_support_session(client, headers, product_id)
    assert second.status_code == 200
    assert second.json()["id"] == session["id"]

    guide = client.post(
        "/api/chat/sessions",
        json={"type": "guide"},
        headers=headers,
    )
    assert guide.status_code == 201
    guide_session = guide.json()
    assert guide_session["type"] == "guide"
    assert guide_session["product"] is None
    assert (
        client.get(
            f"/api/chat/sessions/{guide_session['id']}/messages",
            headers=headers,
        ).json()["items"]
        == []
    )
    guide_again = client.post(
        "/api/chat/sessions",
        json={"type": "guide"},
        headers=headers,
    )
    assert guide_again.status_code == 200
    assert guide_again.json()["id"] == guide_session["id"]

    missing_product = client.post(
        "/api/chat/sessions",
        json={"type": "support"},
        headers=headers,
    )
    assert missing_product.status_code == 400

    unknown_product = create_support_session(client, headers, 999999)
    assert unknown_product.status_code == 404


def test_sessions_and_messages_are_isolated_by_user(client, sample_knowledge):
    headers_a = register_and_login(client, "support_user_a")
    headers_b = register_and_login(client, "support_user_b")
    session = create_support_session(
        client, headers_a, sample_knowledge["product_a_id"]
    ).json()

    assert client.get("/api/chat/sessions", headers=headers_b).json() == []
    assert (
        client.get(
            f"/api/chat/sessions/{session['id']}/messages", headers=headers_b
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/chat/sessions/{session['id']}/escalate", headers=headers_b
        ).status_code
        == 404
    )

    greeting = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers_a
    ).json()["items"][0]
    assert (
        client.post(
            f"/api/chat/messages/{greeting['id']}/feedback",
            json={"helpful": True},
            headers=headers_b,
        ).status_code
        == 404
    )


def test_message_pagination_title_and_content_validation(client, sample_knowledge):
    headers = register_and_login(client)
    session = create_support_session(
        client, headers, sample_knowledge["product_a_id"]
    ).json()
    long_text = "这是一条超过五十个字的用户消息用来验证会话标题截断逻辑是否正确。"

    events = send_message(client, headers, session["id"], long_text)
    assert events[-1][0] == "done"

    listed = client.get(
        f"/api/chat/sessions/{session['id']}/messages?limit=1",
        headers=headers,
    ).json()
    assert len(listed["items"]) == 1
    assert listed["has_more"] is True
    latest_id = listed["items"][0]["id"]

    older = client.get(
        f"/api/chat/sessions/{session['id']}/messages"
        f"?before_id={latest_id}&limit=10",
        headers=headers,
    ).json()
    assert older["items"][-1]["id"] < latest_id
    assert older["items"] == sorted(older["items"], key=lambda item: item["id"])

    sessions = client.get("/api/chat/sessions?type=support", headers=headers).json()
    assert sessions[0]["title"] == long_text[:50]

    image = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"content_type": "image", "content": {"image_url": "x"}},
        headers=headers,
    )
    assert image.status_code == 400
    empty = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"content_type": "text", "content": {"text": "   "}},
        headers=headers,
    )
    assert empty.status_code == 400
    assert (
        client.get("/api/chat/sessions?type=guide", headers=headers).status_code
        == 200
    )


def test_escalate_creates_waiting_ticket_and_is_idempotent(
    client, sample_knowledge
):
    headers = register_and_login(client)
    session = create_support_session(
        client, headers, sample_knowledge["product_a_id"]
    ).json()
    send_message(client, headers, session["id"], "我想转人工确认一下")

    first = client.post(
        f"/api/chat/sessions/{session['id']}/escalate", headers=headers
    )
    assert first.status_code == 200
    body = first.json()
    assert body["ticket_status"] == "waiting"
    assert body["session_status"] == "waiting_human"
    assert (
        fetch_int(
            "SELECT count(*) FROM support_tickets WHERE session_id = $1",
            session["id"],
        )
        == 1
    )
    assert (
        fetch_int(
            "SELECT count(*) FROM support_tickets "
            "WHERE session_id = $1 AND status = 'waiting'",
            session["id"],
        )
        == 1
    )

    second = client.post(
        f"/api/chat/sessions/{session['id']}/escalate", headers=headers
    )
    assert second.status_code == 200
    assert second.json()["ticket_id"] == body["ticket_id"]
    assert (
        fetch_int("SELECT count(*) FROM support_tickets") == 1
    )

    blocked = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"content_type": "text", "content": {"text": "还在吗"}},
        headers=headers,
    )
    assert blocked.status_code == 409


def test_feedback_only_accepts_own_ai_message(client, sample_knowledge):
    headers = register_and_login(client)
    session = create_support_session(
        client, headers, sample_knowledge["product_a_id"]
    ).json()
    greeting = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers
    ).json()["items"][0]

    response = client.post(
        f"/api/chat/messages/{greeting['id']}/feedback",
        json={"helpful": False, "comment": "不太准确"},
        headers=headers,
    )
    assert response.status_code == 200
    messages = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers
    ).json()["items"]
    assert messages[0]["meta"]["feedback"]["helpful"] is False
    assert messages[0]["meta"]["feedback"]["comment"] == "不太准确"

    headers_other = register_and_login(client, "support_user_other")
    assert (
        client.post(
            f"/api/chat/messages/{greeting['id']}/feedback",
            json={"helpful": True},
            headers=headers_other,
        ).status_code
        == 404
    )

    send_message(client, headers, session["id"], "你好")
    messages = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers
    ).json()["items"]
    user_message = next(item for item in messages if item["sender_type"] == "user")
    assert (
        client.post(
            f"/api/chat/messages/{user_message['id']}/feedback",
            json={"helpful": True},
            headers=headers,
        ).status_code
        == 404
    )
