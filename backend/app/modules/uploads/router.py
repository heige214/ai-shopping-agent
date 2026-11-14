from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.ai.base import ASRClient, LLMError
from app.ai.deps import get_asr_client
from app.core.config import settings
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.uploads.service import save_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


class ImageUploadOut(BaseModel):
    url: str


class VoiceUploadOut(BaseModel):
    url: str
    transcript: str


@router.post("/image", response_model=ImageUploadOut)
async def upload_image(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
) -> ImageUploadOut:
    """保存导购图片；jpg/png/webp，单文件 ≤5MB（可配置）。"""
    stored = await save_upload(
        file, "image", int(settings.max_image_upload_mb * 1024 * 1024)
    )
    return ImageUploadOut(url=stored.url)


@router.post("/voice", response_model=VoiceUploadOut)
async def upload_voice(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    asr: ASRClient = Depends(get_asr_client),
) -> VoiceUploadOut:
    """保存语音并转写；webm/mp4/wav，单文件 ≤10MB（可配置）。"""
    stored = await save_upload(
        file, "voice", int(settings.max_voice_upload_mb * 1024 * 1024)
    )
    try:
        transcript = (
            await asr.transcribe(
                stored.path.read_bytes(), _mime_type(file.content_type), stored.filename
            )
        ).strip()
        if not transcript:
            raise LLMError("empty transcript")
    except LLMError as exc:
        stored.path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="语音转写失败，请重试",
        ) from exc
    return VoiceUploadOut(url=stored.url, transcript=transcript)


def _mime_type(raw: str | None) -> str:
    return (raw or "").split(";")[0].strip().lower()
