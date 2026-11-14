import json

import pytest
from sqlalchemy import text

from app.ai.deps import get_embedding_client, get_guide_llm
from app.ai.embeddings import FakeEmbeddingClient
from app.ai.fake import FakeGuideLLM
from app.ai.guide_slots import extract_local_guide_query
from app.main import app


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def register_and_login(
    client, execute_sql, username: str = "cart_user", profile: dict | None = None
) -> dict:
    payload = {"username": username, "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    if profile:
        execute_sql(
            "UPDATE users SET height_cm = :height, weight_kg = :weight "
            "WHERE username = :username",
            {
                "height": profile.get("height_cm"),
                "weight": profile.get("weight_kg"),
                "username": username,
            },
        )
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_session(client, headers, new: bool = False):
    response = client.post(
        "/api/chat/sessions",
        json={"type": "guide", "new": new},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


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


def send(client, headers, session_id: int, text: str):
    with client.stream(
        "POST",
        f"/api/chat/sessions/{session_id}/messages",
        json={"content_type": "text", "content": {"text": text}},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        return parse_sse("".join(response.iter_text()))


def event_names(events) -> list[str]:
    return [name for name, _ in events]


def payload_of(events, name):
    return next(payload for event, payload in events if event == name)


def answer_text(events) -> str:
    return "".join(
        payload["text"] for event, payload in events if event == "token"
    )


def use_guide_llm(llm: FakeGuideLLM) -> None:
    app.dependency_overrides[get_guide_llm] = lambda: llm
    app.dependency_overrides[get_embedding_client] = lambda: FakeEmbeddingClient()


def test_chat_actions_schema_rejects_invalid_status(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(client, execute_sql, "cart_schema")
    session_id = create_session(client, headers)
    send(client, headers, session_id, "衬衫")
    message_id = client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=headers
    ).json()["items"][-1]["id"]

    with pytest.raises(Exception):
        execute_sql(
            "INSERT INTO chat_actions "
            "(session_id, message_id, action_type, payload, status) "
            "VALUES (:session_id, :message_id, 'add_to_cart', "
            "'{}'::jsonb, 'bogus')",
            {"session_id": session_id, "message_id": message_id},
        )


def test_local_cart_slot_parsing():
    query = extract_local_guide_query(
        "把第二件加入购物车", {"last_products": [{"title": "a"}]}
    )
    assert query.intent == "add_to_cart"
    assert query.cart is not None
    assert query.cart.reference == "ordinal"
    assert query.cart.ordinal == 2
    assert query.cart.quantity == 1

    sized = extract_local_guide_query(
        "把第二件 L 码加入购物车，要两件"
    )
    assert sized.cart is not None
    assert sized.cart.size == "L"
    assert sized.cart.quantity == 2

    named = extract_local_guide_query(
        "把蓝色纯棉薄款衬衫加入购物车，M码"
    )
    assert named.cart is not None
    assert named.cart.reference == "name"
    assert named.cart.product_name == "蓝色纯棉薄款衬衫"
    assert named.cart.size == "M"

    deictic = extract_local_guide_query("把这个加入购物车")
    assert deictic.cart is not None
    assert deictic.cart.reference == "deictic"

    assert extract_local_guide_query("推荐几件衬衫").intent == "search"


def test_cart_requires_login_and_owned_action(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(
        client,
        execute_sql,
        "cart_owner",
        profile={"height_cm": 172, "weight_kg": 75},
    )
    session_id = create_session(client, headers)
    send(client, headers, session_id, "衬衫")
    events = send(client, headers, session_id, "把第二件加入购物车")
    action = payload_of(events, "action")
    action_id = action["action_id"]

    other = register_and_login(client, execute_sql, "cart_other")
    assert (
        client.post(
            f"/api/chat/actions/{action_id}/confirm", headers=other
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/chat/actions/{action_id}/cancel", headers=other
        ).status_code
        == 404
    )
    assert (
        client.post(f"/api/chat/actions/{action_id}/confirm").status_code == 401
    )


def test_second_item_action_card_confirm_is_idempotent(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(
        client,
        execute_sql,
        "cart_second",
        profile={"height_cm": 172, "weight_kg": 75},
    )
    session_id = create_session(client, headers)

    listed = send(client, headers, session_id, "衬衫")
    products = payload_of(listed, "products")["items"]
    assert len(products) == 8

    events = send(client, headers, session_id, "把第二件加入购物车")

    assert event_names(events)[0] == "meta"
    assert "token" not in event_names(events)
    assert "products" not in event_names(events)
    assert event_names(events)[-1] == "done"
    meta = payload_of(events, "meta")
    assert meta["intent"] == "add_to_cart"
    action = payload_of(events, "action")
    assert action["action_type"] == "add_to_cart"
    assert action["status"] == "pending"
    assert action["payload"]["title"] == products[1]["title"]
    assert action["payload"]["size"] == products[1]["recommended_size"] == "L"
    assert action["payload"]["quantity"] == 1

    messages = client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=headers
    ).json()["items"]
    card = messages[-1]
    assert card["content_type"] == "action_card"
    assert card["content"]["action_id"] == action["action_id"]
    assert card["content"]["status"] == "pending"

    first = client.post(
        f"/api/chat/actions/{action['action_id']}/confirm", headers=headers
    )
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "executed"
    assert body["quantity"] == 1
    assert body["cart_item_id"]

    second = client.post(
        f"/api/chat/actions/{action['action_id']}/confirm", headers=headers
    )
    assert second.status_code == 200
    assert second.json()["status"] == "executed"
    assert second.json()["cart_item_id"] == body["cart_item_id"]

    cart = client.get("/api/cart", headers=headers).json()
    assert cart["total_quantity"] == 1
    assert cart["items"][0]["sku_id"] == action["payload"]["sku_id"]

    messages = client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=headers
    ).json()["items"]
    assert messages[-1]["content"]["status"] == "executed"


def test_cart_missing_size_asks_instead_of_creating_action(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(client, execute_sql, "cart_no_size")
    session_id = create_session(client, headers)
    send(client, headers, session_id, "衬衫")

    events = send(client, headers, session_id, "把第一件加入购物车")

    assert event_names(events)[0] == "meta"
    assert "action" not in event_names(events)
    assert "尺码" in answer_text(events)
    messages = client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=headers
    ).json()["items"]
    assert messages[-1]["content_type"] == "text"


def test_deictic_with_multiple_products_asks_which_one(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(client, execute_sql, "cart_deictic")
    session_id = create_session(client, headers)
    send(client, headers, session_id, "衬衫")

    events = send(client, headers, session_id, "把这个加入购物车")

    assert "action" not in event_names(events)
    assert "哪一件" in answer_text(events)


def test_single_result_deictic_and_unique_size_create_action(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(
        client,
        execute_sql,
        "cart_single",
        profile={"height_cm": 172, "weight_kg": 75},
    )
    session_id = create_session(client, headers)
    # 只有一个精确结果时“这个”可直接解析；双肩包只有均码，无需尺码
    send(client, headers, session_id, "蓝色纯棉薄款衬衫")
    events = send(client, headers, session_id, "把这个加入购物车")
    assert "action" in event_names(events)
    action = payload_of(events, "action")
    assert action["payload"]["size"] in ("S", "M", "L", "XL")

    new_session = create_session(client, headers, new=True)
    send(client, headers, new_session, "双肩包")
    unique = send(client, headers, new_session, "把第一件加入购物车")
    assert "action" in event_names(unique)
    payload = payload_of(unique, "action")["payload"]
    assert payload["size"] == "均码"


def test_explicit_name_size_and_quantity(client, guide_catalog, execute_sql):
    headers = register_and_login(client, execute_sql, "cart_explicit")
    session_id = create_session(client, headers)

    events = send(
        client,
        headers,
        session_id,
        "把蓝色纯棉薄款衬衫加入购物车，M码，两件",
    )

    action = payload_of(events, "action")
    assert action["payload"]["title"] == "蓝色纯棉薄款衬衫"
    assert action["payload"]["size"] == "M"
    assert action["payload"]["quantity"] == 2
    confirm = client.post(
        f"/api/chat/actions/{action['action_id']}/confirm", headers=headers
    ).json()
    assert confirm["status"] == "executed"
    assert confirm["quantity"] == 2
    cart = client.get("/api/cart", headers=headers).json()
    assert cart["total_quantity"] == 2


def test_cart_cancel_is_idempotent(client, guide_catalog, execute_sql):
    headers = register_and_login(
        client,
        execute_sql,
        "cart_cancel",
        profile={"height_cm": 172, "weight_kg": 75},
    )
    session_id = create_session(client, headers)
    send(client, headers, session_id, "衬衫")
    action = payload_of(
        send(client, headers, session_id, "把第二件加入购物车"), "action"
    )

    first = client.post(
        f"/api/chat/actions/{action['action_id']}/cancel", headers=headers
    )
    second = client.post(
        f"/api/chat/actions/{action['action_id']}/cancel", headers=headers
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == "cancelled"
    assert second.json()["status"] == "cancelled"

    confirm = client.post(
        f"/api/chat/actions/{action['action_id']}/confirm", headers=headers
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "cancelled"
    assert client.get("/api/cart", headers=headers).json()["total_quantity"] == 0


def test_confirm_stock_shortage_returns_failed_card(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(
        client,
        execute_sql,
        "cart_stock",
        profile={"height_cm": 172, "weight_kg": 75},
    )
    session_id = create_session(client, headers)
    send(client, headers, session_id, "衬衫")
    action = payload_of(
        send(client, headers, session_id, "把第二件加入购物车"), "action"
    )
    execute_sql(
        "UPDATE product_skus SET stock = 0 WHERE id = :sku_id",
        {"sku_id": action["payload"]["sku_id"]},
    )

    response = client.post(
        f"/api/chat/actions/{action['action_id']}/confirm", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "库存不足" in body["result"]["reason"]
    assert body["available_sizes"]
    assert client.get("/api/cart", headers=headers).json()["total_quantity"] == 0
    messages = client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=headers
    ).json()["items"]
    assert messages[-1]["content"]["status"] == "failed"
    assert messages[-1]["content"]["result"]["available_sizes"]


def test_confirm_off_sale_returns_failed_card(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(
        client,
        execute_sql,
        "cart_off_sale",
        profile={"height_cm": 172, "weight_kg": 75},
    )
    session_id = create_session(client, headers)
    send(client, headers, session_id, "衬衫")
    action = payload_of(
        send(client, headers, session_id, "把第二件加入购物车"), "action"
    )
    execute_sql(
        "UPDATE products SET status = 'off_sale' WHERE id = :product_id",
        {"product_id": action["payload"]["product_id"]},
    )

    response = client.post(
        f"/api/chat/actions/{action['action_id']}/confirm", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "下架" in response.json()["result"]["reason"]


def test_cart_llm_parse_can_force_add_to_cart(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(
        client,
        execute_sql,
        "cart_forced",
        profile={"height_cm": 172, "weight_kg": 75},
    )
    session_id = create_session(client, headers)
    send(client, headers, session_id, "衬衫")
    use_guide_llm(
        FakeGuideLLM(
            query={
                "intent": "add_to_cart",
                "cart": {"reference": "ordinal", "ordinal": 1, "quantity": 1},
            }
        )
    )

    events = send(client, headers, session_id, "我要第一件")

    assert "action" in event_names(events)
    assert payload_of(events, "action")["payload"]["title"]
