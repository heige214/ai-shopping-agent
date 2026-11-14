from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[3]
UPLOAD_URL_PREFIX = "/static/uploads/"
UPLOAD_DIR = (
    Path(settings.upload_dir)
    if Path(settings.upload_dir).is_absolute()
    else BACKEND_DIR / settings.upload_dir
)

IMAGE_MIME_EXTENSIONS: dict[str, set[str]] = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}
VOICE_MIME_EXTENSIONS: dict[str, set[str]] = {
    "audio/webm": {".webm"},
    "audio/mp4": {".mp4"},
    "video/mp4": {".mp4"},
    "audio/wav": {".wav"},
    "audio/x-wav": {".wav"},
}


@dataclass
class StoredUpload:
    url: str
    filename: str
    path: Path
    size: int


def _safe_filename(filename: str | None) -> str:
    """只取客户端文件名最后一段，最终落盘名仍由服务端 UUID 生成。"""
    return (filename or "").replace("\\", "/").rsplit("/", 1)[-1]


def _mime_type(raw: str | None) -> str:
    return (raw or "").split(";")[0].strip().lower()


def _has_valid_magic(data: bytes, suffix: str) -> bool:
    if suffix in (".jpg", ".jpeg"):
        return data.startswith(b"\xff\xd8\xff")
    if suffix == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix == ".webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if suffix == ".webm":
        return data.startswith(b"\x1a\x45\xdf\xa3")
    if suffix == ".wav":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if suffix == ".mp4":
        return len(data) >= 12 and data[4:8] == b"ftyp"
    return False


def _validate_meta(file: UploadFile, kind: str) -> tuple[str, str]:
    mime = _mime_type(file.content_type)
    filename = _safe_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    allowed = IMAGE_MIME_EXTENSIONS if kind == "image" else VOICE_MIME_EXTENSIONS
    if mime not in allowed or suffix not in allowed[mime]:
        label = "图片" if kind == "image" else "语音"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的{label}格式",
        )
    return mime, suffix


async def save_upload(
    file: UploadFile, kind: str, max_bytes: int
) -> StoredUpload:
    """校验 MIME/扩展名/魔数/大小后以 UUID 文件名落盘。"""
    _mime, suffix = _validate_meta(file, kind)
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="文件大小超出限制",
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="文件不能为空"
        )
    if not _has_valid_magic(data, suffix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容与格式不匹配",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    path = UPLOAD_DIR / filename
    path.write_bytes(data)
    return StoredUpload(
        url=f"{UPLOAD_URL_PREFIX}{filename}",
        filename=filename,
        path=path,
        size=len(data),
    )


def resolve_upload_path(url: str) -> Path | None:
    """把 /static/uploads/<uuid>.<ext> 映射为本地路径，拒绝路径穿越。"""
    text = (url or "").strip()
    if not text.startswith(UPLOAD_URL_PREFIX):
        return None
    name = text[len(UPLOAD_URL_PREFIX) :]
    if (
        not name
        or "/" in name
        or "\\" in name
        or ".." in name
        or name.startswith(".")
    ):
        return None
    return UPLOAD_DIR / name


def media_type_for_url(url: str) -> str:
    suffix = Path((url or "").split("?")[0]).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".webm": "audio/webm",
        ".mp4": "audio/mp4",
        ".wav": "audio/wav",
    }.get(suffix, "application/octet-stream")
