import base64
import json

import pytest

from app.ai.deps import get_vision_client
from app.ai.fake import FakeVisionClient
from app.main import app
from app.modules.uploads import service as upload_service

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Wl2n1sAAAAASUVORK5CYII="
)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def register_and_login(client, username: str) -> dict:
    payload = {"username": username, "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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


def payload_of(events, name):
    return next(payload for event, payload in events if event == name)


def answer_text(events) -> str:
    return "".join(
        payload["text"] for event, payload in events if event == "token"
    )


def upload_png(client, headers, tmp_path):
    response = client.post(
        "/api/uploads/image",
        files={"file": ("sample.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["url"]


def send_message(client, headers, session_id, content_type, content):
    with client.stream(
        "POST",
        f"/api/chat/sessions/{session_id}/messages",
        json={"content_type": content_type, "content": content},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        return parse_sse("".join(response.iter_text()))


def create_guide_session(client, headers):
    response = client.post(
        "/api/chat/sessions", json={"type": "guide"}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_image_message_merges_vision_into_guide_slots(
    client, guide_catalog, execute_sql, tmp_path, monkeypatch
):
    monkeypatch.setattr(upload_service, "UPLOAD_DIR", tmp_path)
    headers = register_and_login(client, "vision_user")
    session_id = create_guide_session(client, headers)
    image_url = upload_png(client, headers, tmp_path)

    events = send_message(
        client,
        headers,
        session_id,
        "image",
        {"image_url": image_url, "text": "找类似这种的"},
    )

    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert names.index("token") < names.index("products")
    assert names[-1] == "done"
    meta = payload_of(events, "meta")
    assert meta["intent"] == "search"
    assert meta["query"]["category_path"] == ["服装", "衬衫"]
    assert meta["query"]["filters"]["color"] == ["蓝色"]
    assert meta["query"]["filters"]["thickness"] == ["薄款"]
    assert meta["vision"]["confidence"] >= 0.8

    products = payload_of(events, "products")["items"]
    assert products
    assert all("蓝色" in item["title"] for item in products)

    messages = client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=headers
    ).json()["items"]
    user_image = next(item for item in messages if item["content_type"] == "image")
    assert user_image["content"]["image_url"] == image_url
    assert user_image["content"]["vision"]["category_path"] == ["服装", "衬衫"]
    assert user_image["content"]["vision"]["attributes"]["color"] == ["蓝色"]


def test_image_failure_degrades_to_text_search(
    client, guide_catalog, execute_sql, tmp_path, monkeypatch
):
    monkeypatch.setattr(upload_service, "UPLOAD_DIR", tmp_path)
    app.dependency_overrides[get_vision_client] = lambda: FakeVisionClient(
        fail=True
    )
    headers = register_and_login(client, "vision_fail")
    session_id = create_guide_session(client, headers)
    image_url = upload_png(client, headers, tmp_path)

    events = send_message(
        client,
        headers,
        session_id,
        "image",
        {"image_url": image_url, "text": "衬衫"},
    )

    meta = payload_of(events, "meta")
    assert meta["degraded"] is True
    assert "图片识别失败" in answer_text(events)
    assert "已按文字条件搜索" in answer_text(events)
    assert len(payload_of(events, "products")["items"]) == 8


def test_voice_message_uses_transcript_and_keeps_content(
    client, guide_catalog, execute_sql, tmp_path, monkeypatch
):
    monkeypatch.setattr(upload_service, "UPLOAD_DIR", tmp_path)
    headers = register_and_login(client, "voice_user")
    session_id = create_guide_session(client, headers)
    upload = client.post(
        "/api/uploads/voice",
        files={
            "file": (
                "voice.webm",
                b"\x1aE\xdf\xa3" + b"\x00" * 32,
                "audio/webm",
            )
        },
        headers=headers,
    )
    assert upload.status_code == 200
    audio_url = upload.json()["url"]

    events = send_message(
        client,
        headers,
        session_id,
        "voice",
        {
            "audio_url": audio_url,
            "transcript": "蓝色衬衫",
            "text": "蓝色衬衫",
        },
    )

    meta = payload_of(events, "meta")
    assert meta["query"]["category_path"] == ["服装", "衬衫"]
    assert meta["query"]["filters"]["color"] == ["蓝色"]
    assert payload_of(events, "products")["items"]

    messages = client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=headers
    ).json()["items"]
    voice = next(item for item in messages if item["content_type"] == "voice")
    assert voice["content"] == {
        "audio_url": audio_url,
        "transcript": "蓝色衬衫",
        "text": "蓝色衬衫",
    }


def test_guide_rejects_unsupported_message_content(
    client, guide_catalog, execute_sql
):
    headers = register_and_login(client, "voice_invalid")
    session_id = create_guide_session(client, headers)

    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content_type": "image", "content": {"image_url": "https://x.test/a.png"}},
        headers=headers,
    )
    assert response.status_code == 400

    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content_type": "voice", "content": {"audio_url": "/static/uploads/a.webm"}},
        headers=headers,
    )
    assert response.status_code == 400
