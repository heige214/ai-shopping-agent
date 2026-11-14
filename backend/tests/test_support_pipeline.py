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
    assert citations["items"][0]["content"]
    assert "纯棉" in answer_text(events)

    messages = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers
    ).json()["items"]
    ai_message = messages[-1]
    assert ai_message["sender_type"] == "ai"
    assert ai_message["meta"]["citations"]
    assert ai_message["meta"]["intent"] == "product_qa"
    assert ai_message["meta"]["retrieval"]["chunks"] > 0
    assert ai_message["meta"]["agent"]["action"] == "rag"
    assert "tool:search_knowledge" in ai_message["meta"]["agent"]["trace"]


def test_size_availability_uses_product_facts_before_llm(
    client, sample_knowledge
):
    # 意图模型故意失败；如果仍能回答，说明走了商品事实的尺码库存前置层
    use_llm(FakeSupportLLM(fail_intent=True))
    headers = register_and_login(client, "pipeline_size_facts")
    session = create_session(client, headers, sample_knowledge["product_a_id"])

    events = send(client, headers, session["id"], "有S的吗")
    names = event_names(events)
    text = answer_text(events)

    assert "没有 S 码" in text
    assert "M、L" in text
    assert names[0] == "meta"
    assert names.index("citations") < names.index("answer_meta")
    assert names[-1] == "done"
    meta = answer_meta(events)
    assert meta["intent"] == "size_qa"
    assert meta["can_answer"] is True
    assert meta["handoff_required"] is False

    citations = next(payload for name, payload in events if name == "citations")
    assert citations["items"][0]["doc_type"] == "size"

    messages = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers
    ).json()["items"]
    ai_message = messages[-1]
    assert ai_message["meta"]["retrieval"]["source"] == "product_facts"


def test_generic_stock_question_uses_fact_path(client, sample_knowledge):
    use_llm(FakeSupportLLM(fail_intent=True))
    headers = register_and_login(client, "pipeline_stock_facts")
    session = create_session(client, headers, sample_knowledge["product_a_id"])

    events = send(client, headers, session["id"], "有货吗")

    assert "M、L" in answer_text(events)
    assert answer_meta(events)["handoff_required"] is False


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
    assert "方便再具体说说" in answer_text(first)
    assert answer_meta(first)["handoff_required"] is False

    second = send(client, headers, session["id"], "那这个呢")
    assert "暂未检索到" in answer_text(second)
    assert answer_meta(second)["handoff_required"] is True


def test_unseen_question_uses_agent_tools_instead_of_clarifying(
    client, sample_knowledge
):
    use_llm(
        FakeSupportLLM(
            plan={
                "action": "rag",
                "tools": ["product_facts", "search_knowledge"],
                "search_query": "材质",
            },
            answer_text="资料没有标注儿童适用年龄。",
            fail_answerability=True,
        )
    )
    headers = register_and_login(client, "pipeline_agent_unseen")
    session = create_session(client, headers, sample_knowledge["product_a_id"])

    events = send(client, headers, session["id"], "这个小孩子能带吗")
    text = answer_text(events)

    assert "儿童适用年龄" in text
    assert "方便再具体说说" not in text
    assert "citations" in event_names(events)
    meta = answer_meta(events)
    assert meta["can_answer"] is True
    assert meta["handoff_required"] is False

    messages = client.get(
        f"/api/chat/sessions/{session['id']}/messages", headers=headers
    ).json()["items"]
    agent = messages[-1]["meta"]["agent"]
    assert agent["action"] == "rag"
    assert "search_knowledge" in agent["tools"]
    assert "tool:search_knowledge" in agent["trace"]


def test_model_no_answer_phrase_sets_handoff(client, sample_knowledge):
    use_llm(
        FakeSupportLLM(
            intent="product_qa",
            answer_text="知识库暂未检索到有效信息",
        )
    )
    headers = register_and_login(client, "pipeline_no_answer")
    session = create_session(client, headers, sample_knowledge["product_a_id"])
    events = send(client, headers, session["id"], "这件衬衫是什么材质？")

    text = answer_text(events)
    assert "知识库暂未检索到有效信息" in text
    assert "建议转人工客服进一步确认" in text
    meta = answer_meta(events)
    assert meta["can_answer"] is False
    assert meta["handoff_required"] is True


def test_low_similarity_falls_back_without_extra_model_call(
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
    assert "暂未检索到" in answer_text(events)
    assert answer_meta(events)["handoff_required"] is True


def test_plan_llm_failure_emits_error_and_fallback(client, sample_knowledge):
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
        async def plan_support(self, question: str, product_title: str):
            await asyncio.sleep(0.2)
            return await super().plan_support(question, product_title)

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
