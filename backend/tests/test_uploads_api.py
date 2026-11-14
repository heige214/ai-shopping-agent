import base64

from app.ai.deps import get_asr_client
from app.ai.fake import FakeASRClient
from app.main import app
from app.modules.uploads import service as upload_service

# 1x1 透明 PNG，仅用于验证扩展名/MIME/魔数链路
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Wl2n1sAAAAASUVORK5CYII="
)
WEBM_BYTES = b"\x1aE\xdf\xa3" + b"\x00" * 32


def register_and_login(client, username: str = "upload_user") -> dict:
    payload = {"username": username, "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def upload_image(client, headers, data=PNG_BYTES, name="sample.png", mime="image/png"):
    return client.post(
        "/api/uploads/image",
        files={"file": (name, data, mime)},
        headers=headers,
    )


def test_uploads_require_login(client, tmp_path, monkeypatch):
    monkeypatch.setattr(upload_service, "UPLOAD_DIR", tmp_path)
    assert upload_image(client, {}).status_code == 401
    assert (
        client.post(
            "/api/uploads/voice",
            files={"file": ("a.webm", WEBM_BYTES, "audio/webm")},
        ).status_code
        == 401
    )


def test_image_upload_saves_uuid_file(client, tmp_path, monkeypatch):
    monkeypatch.setattr(upload_service, "UPLOAD_DIR", tmp_path)
    headers = register_and_login(client)

    response = upload_image(client, headers)

    assert response.status_code == 200
    url = response.json()["url"]
    assert url.startswith("/static/uploads/")
    filename = url.rsplit("/", 1)[-1]
    assert filename.endswith(".png")
    assert filename != "sample.png"
    assert (tmp_path / filename).read_bytes() == PNG_BYTES


def test_image_upload_rejects_type_and_magic_mismatch(
    client, tmp_path, monkeypatch
):
    monkeypatch.setattr(upload_service, "UPLOAD_DIR", tmp_path)
    headers = register_and_login(client, "upload_bad")

    assert (
        upload_image(client, headers, b"GIF89a", "a.gif", "image/gif").status_code
        == 400
    )
    # 扩展名与 MIME 不一致
    assert (
        upload_image(client, headers, PNG_BYTES, "a.png", "image/jpeg").status_code
        == 400
    )
    # 伪装成 PNG 的非图片内容
    assert (
        upload_image(client, headers, b"not-a-png", "a.png", "image/png").status_code
        == 400
    )
    assert (
        upload_image(
            client, headers, PNG_BYTES, "../../evil.png", "image/png"
        ).status_code
        == 200
    )
    assert not (tmp_path.parent / "evil.png").exists()
    assert not list(tmp_path.glob("*evil*"))


def test_image_upload_size_limit(client, tmp_path, monkeypatch):
    monkeypatch.setattr(upload_service, "UPLOAD_DIR", tmp_path)
    headers = register_and_login(client, "upload_big")
    monkeypatch.setattr(
        upload_service.settings, "max_image_upload_mb", 0.000001
    )

    response = upload_image(client, headers)

    assert response.status_code == 413
    assert not list(tmp_path.iterdir())


def test_voice_upload_returns_transcript(client, tmp_path, monkeypatch):
    monkeypatch.setattr(upload_service, "UPLOAD_DIR", tmp_path)
    headers = register_and_login(client, "upload_voice")

    response = client.post(
        "/api/uploads/voice",
        files={"file": ("voice.webm", WEBM_BYTES, "audio/webm")},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "推荐几件衬衫"
    assert body["url"].startswith("/static/uploads/")
    filename = body["url"].rsplit("/", 1)[-1]
    assert filename.endswith(".webm")
    assert (tmp_path / filename).read_bytes() == WEBM_BYTES


def test_voice_upload_failure_removes_file_and_returns_502(
    client, tmp_path, monkeypatch
):
    monkeypatch.setattr(upload_service, "UPLOAD_DIR", tmp_path)
    app.dependency_overrides[get_asr_client] = lambda: FakeASRClient(fail=True)
    try:
        headers = register_and_login(client, "upload_voice_fail")
        response = client.post(
            "/api/uploads/voice",
            files={"file": ("voice.webm", WEBM_BYTES, "audio/webm")},
            headers=headers,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert "重试" in response.json()["detail"]
    assert not list(tmp_path.iterdir())
