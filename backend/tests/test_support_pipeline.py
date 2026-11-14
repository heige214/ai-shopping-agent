import asyncio
import json
import time

import pytest

from app.ai.deps import get_embedding_client, get_support_llm
from app.ai.embeddings import FakeEmbeddingClient
from app.ai.fake import FakeSupportLLM
from app.main import app
from app.modules.support import pipeline


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def register_and_login(client, username: str = "pipeline_user") -> dict:
    payload = {"username": username, "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_session(client, headers, product_id: int) -> dict:
    response = client.post(
        "/api/chat/sessions",
        json={"type": "support", "product_id": product_id},
        headers=headers,
    )
    assert response.status_code in (200, 201)
    return response.json()


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


def send(client, headers, session_id: int, text: str) -> list[tuple[str, dict]]:
    with client.stream(
        "POST",
        f"/api/chat/sessions/{session_id}/messages",
        json={"content_type": "text", "content": {"text": text}},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        return parse_sse("".join(response.iter_text()))


def use_llm(llm: FakeSupportLLM) -> None:
    app.dependency_overrides[get_support_llm] = lambda: llm
    app.dependency_overrides[get_embedding_client] = lambda: FakeEmbeddingClient()


def event_names(events: list[tuple[str, dict]]) -> list[str]:
    return [name for name, _ in events]


def answer_meta(events: list[tuple[str, dict]]) -> dict:
    return next(payload for name, payload in events if name == "answer_meta")


def answer_text(events: list[tuple[str, dict]]) -> str:
    return "".join(
        payload["text"] for name, payload in events if name == "token"
    )


def test_answerable_rag_emits_ordered_sse_and_persists_meta(
    client, sample_knowledge
):
    use_llm(
        FakeSupportLLM(
            intent="product_qa",
            answerability={
                "can_answer": True,
                "confidence": 0.85,
                "partial": False,
            },
            answer_text="测试衬衫的材质是纯棉，建议冷水洗涤。",
        )
    )
    headers = register_and_login(client)
    session = create_session(client, headers, sample_knowledge["product_a_id"])
    events = send(client, headers, session["id"], "这件衬衫是什么材质？")

    names = event_names(events)
    assert names[0] == "meta"
    assert "token" in names
    assert names.index("citations") < names.index("answer_meta")
    assert names.index("answer_meta") < names.index("done")
    assert names[-1] == "done"
    meta = answer_meta(events)
    assert meta["intent"] == "product_qa"
    assert meta["can_answer"] is True
    assert meta["handoff_required"] is False
    citations = next(payload for name, payload in events if name == "citations")
    assert citations["items"]
    assert "纯棉" in answer_text(events)

    messages = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers
    ).json()["items"]
    ai_message = messages[-1]
    assert ai_message["sender_type"] == "ai"
    assert ai_message["meta"]["citations"]
    assert ai_message["meta"]["intent"] == "product_qa"
    assert ai_message["meta"]["retrieval"]["chunks"] > 0


@pytest.mark.parametrize(
    ("intent", "expected_phrase"),
    [("order_qa", "订单"), ("complaint", "抱歉")],
)
def test_fixed_handoff_intents(
    client, sample_knowledge, intent, expected_phrase
):
    use_llm(FakeSupportLLM(intent=intent))
    headers = register_and_login(client, f"pipeline_{intent}")
    session = create_session(client, headers, sample_knowledge["product_a_id"])
    events = send(client, headers, session["id"], "帮我处理一下")
    assert expected_phrase in answer_text(events)
    meta = answer_meta(events)
    assert meta["handoff_required"] is True
    assert "citations" not in event_names(events)


def test_chitchat_guides_back_without_handoff(client, sample_knowledge):
    use_llm(FakeSupportLLM(intent="chitchat"))
    headers = register_and_login(client, "pipeline_chitchat")
    session = create_session(client, headers, sample_knowledge["product_a_id"])
    events = send(client, headers, session["id"], "你好")
    assert "AI 客服" in answer_text(events)
    assert answer_meta(events)["handoff_required"] is False


def test_unknown_clarifies_once_then_falls_back(client, sample_knowledge):
    use_llm(FakeSupportLLM(intent="unknown"))
    headers = register_and_login(client, "pipeline_unknown")
    session = create_session(client, headers, sample_knowledge["product_a_id"])

    first = send(client, headers, session["id"], "这个问题你懂吗")
    assert "不太确定" in answer_text(first)
    assert answer_meta(first)["handoff_required"] is False

    second = send(client, headers, session["id"], "那这个呢")
    assert "暂未检索到" in answer_text(second)
    assert answer_meta(second)["handoff_required"] is True


def test_confidence_below_threshold_clarifies_once(client, sample_knowledge):
    use_llm(
        FakeSupportLLM(
            intent="product_qa",
            answerability={
                "can_answer": True,
                "confidence": 0.4,
                "partial": False,
            },
        )
    )
    headers = register_and_login(client, "pipeline_low_confidence")
    session = create_session(client, headers, sample_knowledge["product_a_id"])

    first = send(client, headers, session["id"], "这件衬衫是什么材质？")
    assert "不太确定" in answer_text(first)
    assert answer_meta(first)["handoff_required"] is False

    second = send(client, headers, session["id"], "那洗护呢？")
    assert "暂未检索到" in answer_text(second)
    assert answer_meta(second)["handoff_required"] is True


def test_partial_answer_suggests_handoff(client, sample_knowledge):
    use_llm(
        FakeSupportLLM(
            intent="product_qa",
            answerability={
                "can_answer": True,
                "confidence": 0.8,
                "partial": True,
            },
            answer_text="资料确认材质是纯棉。",
        )
    )
    headers = register_and_login(client, "pipeline_partial")
    session = create_session(client, headers, sample_knowledge["product_a_id"])
    events = send(client, headers, session["id"], "材质和产地是什么？")
    text = answer_text(events)
    assert "资料确认材质" in text
    assert "其余部分建议转人工" in text
    meta = answer_meta(events)
    assert meta["partial"] is True
    assert meta["handoff_required"] is True
    assert "citations" in event_names(events)


def test_low_similarity_short_circuits_without_answerability_llm(
    client, sample_knowledge
):
    use_llm(
        FakeSupportLLM(
            intent="product_qa",
            fail_answerability=True,
        )
    )
    headers = register_and_login(client, "pipeline_short_circuit")
    session = create_session(client, headers, sample_knowledge["product_a_id"])
    events = send(client, headers, session["id"], "这件衣服能防弹吗")
    assert "error" not in event_names(events)
    assert "不太确定" in answer_text(events)

    second = send(client, headers, session["id"], "能当雨衣吗")
    assert "暂未检索到" in answer_text(second)
    assert answer_meta(second)["handoff_required"] is True


def test_intent_llm_failure_emits_error_and_fallback(client, sample_knowledge):
    use_llm(FakeSupportLLM(fail_intent=True))
    headers = register_and_login(client, "pipeline_intent_fail")
    session = create_session(client, headers, sample_knowledge["product_a_id"])
    events = send(client, headers, session["id"], "这件衬衫是什么材质？")
    names = event_names(events)
    assert names[0] == "meta"
    assert "error" in names
    assert names.index("error") < names.index("token")
    assert names[-1] == "done"
    error = next(payload for name, payload in events if name == "error")
    assert error["code"] == "LLM_ERROR"
    assert answer_meta(events)["handoff_required"] is True


def test_answer_stream_failure_emits_error_and_fallback(
    client, sample_knowledge
):
    use_llm(
        FakeSupportLLM(
            intent="product_qa",
            answerability={
                "can_answer": True,
                "confidence": 0.8,
                "partial": False,
            },
            fail_stream=True,
        )
    )
    headers = register_and_login(client, "pipeline_stream_fail")
    session = create_session(client, headers, sample_knowledge["product_a_id"])
    events = send(client, headers, session["id"], "这件衬衫是什么材质？")
    assert "error" in event_names(events)
    assert "服务繁忙" in answer_text(events)
    meta = answer_meta(events)
    assert meta["handoff_required"] is True
    assert meta["degraded"] is True


def test_llm_timeout_emits_error_without_hanging(
    client, sample_knowledge, monkeypatch
):
    class SlowLLM(FakeSupportLLM):
        async def route_intent(self, question: str, product_title: str):
            await asyncio.sleep(0.2)
            return await super().route_intent(question, product_title)

    monkeypatch.setattr(pipeline.settings, "llm_timeout_seconds", 0.01)
    use_llm(SlowLLM())
    headers = register_and_login(client, "pipeline_timeout")
    session = create_session(client, headers, sample_knowledge["product_a_id"])
    started = time.monotonic()
    events = send(client, headers, session["id"], "这件衬衫是什么材质？")
    elapsed = time.monotonic() - started
    assert elapsed < 2.0
    error = next(payload for name, payload in events if name == "error")
    assert error["code"] == "LLM_TIMEOUT"
    assert "error" in event_names(events)
    assert events[-1][0] == "done"
