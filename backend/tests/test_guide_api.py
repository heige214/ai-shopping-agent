import json

import pytest

from app.ai.deps import get_embedding_client, get_guide_llm
from app.ai.embeddings import FakeEmbeddingClient
from app.ai.fake import FakeGuideLLM
from app.main import app


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def register_and_login(
    client,
    execute_sql,
    username: str = "guide_user",
    profile: dict | None = None,
) -> dict:
    payload = {"username": username, "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    if profile:
        execute_sql(
            "UPDATE users SET height_cm = :height, weight_kg = :weight, "
            "usual_size = :size WHERE username = :username",
            {
                "height": profile.get("height_cm"),
                "weight": profile.get("weight_kg"),
                "size": profile.get("usual_size"),
                "username": username,
            },
        )
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_guide_session(client, headers, new: bool = False):
    return client.post(
        "/api/chat/sessions",
        json={"type": "guide", "new": new},
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


def send_guide(client, headers, session_id: int, text: str):
    with client.stream(
        "POST",
        f"/api/chat/sessions/{session_id}/messages",
        json={"content_type": "text", "content": {"text": text}},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        return parse_sse("".join(response.iter_text()))


def event_names(events: list[tuple[str, dict]]) -> list[str]:
    return [name for name, _ in events]


def payload_of(events: list[tuple[str, dict]], name: str) -> dict:
    return next(payload for event, payload in events if event == name)


def answer_text(events: list[tuple[str, dict]]) -> str:
    return "".join(
        payload["text"] for name, payload in events if name == "token"
    )


def use_guide_llm(llm: FakeGuideLLM) -> None:
    app.dependency_overrides[get_guide_llm] = lambda: llm
    app.dependency_overrides[get_embedding_client] = lambda: FakeEmbeddingClient()


def test_guide_session_reuse_new_and_escalate(client, guide_catalog, execute_sql):
    headers = register_and_login(client, execute_sql)

    first = create_guide_session(client, headers)
    assert first.status_code == 201
    session = first.json()
    assert session["type"] == "guide"
    assert session["product"] is None
    messages = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers
    ).json()
    assert messages["items"] == []

    reused = create_guide_session(client, headers)
    assert reused.status_code == 200
    assert reused.json()["id"] == session["id"]

    created = create_guide_session(client, headers, new=True)
    assert created.status_code == 201
    assert created.json()["id"] != session["id"]

    listed = client.get("/api/chat/sessions?type=guide", headers=headers)
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {
        session["id"],
        created.json()["id"],
    }

    escalated = client.post(
        f"/api/chat/sessions/{session['id']}/escalate", headers=headers
    )
    assert escalated.status_code == 400

    support = client.post(
        "/api/chat/sessions",
        json={
            "type": "support",
            "product_id": guide_catalog["product_ids"]["G01"],
        },
        headers=headers,
    )
    assert support.status_code == 201

    unknown = client.post(
        "/api/chat/sessions", json={"type": "unknown"}, headers=headers
    )
    assert unknown.status_code == 400
    assert (
        client.get("/api/chat/sessions?type=unknown", headers=headers).status_code
        == 400
    )


def test_guide_sse_order_cards_and_persisted_meta(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(
        client,
        execute_sql,
        profile={"height_cm": 172, "weight_kg": 75, "usual_size": "M"},
    )
    session = create_guide_session(client, headers).json()

    events = send_guide(client, headers, session["id"], "衬衫")
    names = event_names(events)

    assert names[0] == "meta"
    assert names.index("token") < names.index("products")
    assert names.index("products") < names.index("done")
    assert names[-1] == "done"

    meta = payload_of(events, "meta")
    assert meta["intent"] == "search"
    assert meta["query"]["category_path"] == ["服装", "衬衫"]
    assert meta["need_clarify"] is False

    products = payload_of(events, "products")
    assert len(products["items"]) == 8
    card = products["items"][0]
    assert card["id"] > 0
    assert card["title"]
    assert card["price"] > 0
    assert card["recommended_size"] == "L"
    assert card["size_reason"]

    messages = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers
    ).json()["items"]
    ai_message = messages[-1]
    assert ai_message["sender_type"] == "ai"
    assert len(ai_message["meta"]["products"]) == 8
    assert ai_message["meta"]["query"]["category_path"] == ["服装", "衬衫"]
    assert ai_message["meta"]["relaxed"] == []
    assert ai_message["content"]["text"]


def test_guide_refine_merges_color_and_price(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(
        client, execute_sql, username="guide_refine"
    )
    session = create_guide_session(client, headers).json()

    first = send_guide(client, headers, session["id"], "蓝色衬衫")
    first_products = payload_of(first, "products")
    assert len(first_products["items"]) == 3
    assert all(
        "蓝色" in item["title"] for item in first_products["items"]
    )

    second = send_guide(client, headers, session["id"], "要150元以内的")
    meta = payload_of(second, "meta")
    assert meta["query"]["filters"]["color"] == ["蓝色"]
    assert meta["query"]["price"]["max"] == 150
    products = payload_of(second, "products")
    assert products["items"]
    assert all(item["price"] <= 150 for item in products["items"])
    assert all("蓝色" in item["title"] for item in products["items"])


def test_guide_relaxes_then_clarifies_once(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(
        client, execute_sql, username="guide_relax"
    )
    session = create_guide_session(client, headers).json()

    relaxed = send_guide(
        client, headers, session["id"], "蓝色真丝薄款衬衫"
    )
    meta = payload_of(relaxed, "meta")
    assert meta["relaxed"] == ["厚薄", "材质"]
    assert "放宽" in answer_text(relaxed)
    assert len(payload_of(relaxed, "products")["items"]) == 3

    empty_session = create_guide_session(client, headers, new=True).json()
    first = send_guide(
        client, headers, empty_session["id"], "紫色衬衫10元以内"
    )
    assert payload_of(first, "meta")["need_clarify"] is True
    assert "没有找到完全匹配" in answer_text(first)
    assert "products" not in event_names(first)

    second = send_guide(
        client, headers, empty_session["id"], "紫色衬衫10元以内"
    )
    assert payload_of(second, "meta")["need_clarify"] is False
    assert "暂时没有找到" in answer_text(second)
    assert "products" not in event_names(second)


def test_guide_failures_degrade_but_still_return_cards(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(
        client, execute_sql, username="guide_fail"
    )
    session = create_guide_session(client, headers).json()

    use_guide_llm(FakeGuideLLM(fail_rerank=True))
    rerank_failed = send_guide(client, headers, session["id"], "衬衫")
    assert "error" in event_names(rerank_failed)
    assert len(payload_of(rerank_failed, "products")["items"]) == 8
    assert event_names(rerank_failed)[-1] == "done"

    use_guide_llm(FakeGuideLLM(fail_stream=True))
    stream_failed = send_guide(client, headers, session["id"], "衬衫")
    assert "error" in event_names(stream_failed)
    assert "服务繁忙" in answer_text(stream_failed)
    assert len(payload_of(stream_failed, "products")["items"]) == 8

    use_guide_llm(FakeGuideLLM(fail_parse=True))
    parse_failed = send_guide(client, headers, session["id"], "衬衫")
    assert payload_of(parse_failed, "meta")["degraded"] is True
    assert "error" in event_names(parse_failed)
    assert "products" in event_names(parse_failed)


def test_guide_chitchat_has_no_products(client, guide_catalog, execute_sql):
    headers = register_and_login(
        client, execute_sql, username="guide_chitchat"
    )
    session = create_guide_session(client, headers).json()

    events = send_guide(client, headers, session["id"], "你好")

    assert payload_of(events, "meta")["intent"] == "chitchat"
    assert "AI 导购" in answer_text(events)
    assert "products" not in event_names(events)
    assert event_names(events)[-1] == "done"


def test_guide_sessions_are_isolated_by_user(
    client, guide_catalog, execute_sql
):
    headers_a = register_and_login(
        client, execute_sql, username="guide_owner"
    )
    headers_b = register_and_login(
        client, execute_sql, username="guide_other"
    )
    session = create_guide_session(client, headers_a).json()

    assert (
        client.get(
            f"/api/chat/sessions/{session['id']}/messages", headers=headers_b
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/chat/sessions/{session['id']}/messages",
            json={"content_type": "text", "content": {"text": "你好"}},
            headers=headers_b,
        ).status_code
        == 404
    )


def test_size_recommendation_endpoint(client, guide_catalog, execute_sql):
    headers = register_and_login(
        client,
        execute_sql,
        username="guide_size",
        profile={"height_cm": 172, "weight_kg": 75, "usual_size": "M"},
    )
    product_id = guide_catalog["product_ids"]["G01"]

    response = client.get(
        f"/api/products/{product_id}/size-recommendation", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_size"] == "L"
    assert "L 码" in body["size_reason"]
    assert body["source"] == "profile"

    missing_profile_headers = register_and_login(
        client, execute_sql, username="guide_size_empty"
    )
    empty = client.get(
        f"/api/products/{product_id}/size-recommendation",
        headers=missing_profile_headers,
    ).json()
    assert empty["recommended_size"] is None
    assert "身高体重" in empty["size_reason"]

    assert (
        client.get(
            f"/api/products/{product_id}/size-recommendation"
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/products/999999/size-recommendation", headers=headers
        ).status_code
        == 404
    )
