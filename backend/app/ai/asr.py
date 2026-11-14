from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import httpx

from app.ai.base import ASRError, LLMTimeoutError


class LocalASRClient:
    """无 key / local 模式：没有真实 ASR，明确提示不可用。"""

    async def transcribe(
        self, audio_bytes: bytes, mime_type: str, filename: str
    ) -> str:
        raise ASRError("语音转写服务未配置，请改用文字输入")


class DashScopeASRClient:
    """百炼 Paraformer 文件转写：上传策略 → 异步任务 → 轮询 → 取结果。"""

    def __init__(
        self,
        *,
        api_key: str,
        native_base_url: str,
        model: str,
        timeout_seconds: float = 20.0,
        poll_interval_seconds: float = 1.0,
        max_polls: int = 30,
    ) -> None:
        self.api_key = api_key
        self.native_base_url = native_base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _upload_file(
        self, client: httpx.AsyncClient, audio_bytes: bytes, mime_type: str,
        filename: str,
    ) -> str:
        policy_response = await client.get(
            f"{self.native_base_url}/uploads",
            headers=self._headers,
            params={"action": "getPolicy", "model": self.model},
        )
        if policy_response.status_code >= 400:
            raise ASRError(
                f"获取上传凭证失败：HTTP {policy_response.status_code}"
            )
        policy = (policy_response.json() or {}).get("data") or {}
        upload_host = str(policy.get("upload_host") or "")
        upload_dir = str(policy.get("upload_dir") or "").strip("/")
        if not upload_host or not upload_dir:
            raise ASRError("上传凭证缺少 upload_host/upload_dir")

        suffix = Path(filename).suffix.lower() or ".webm"
        object_key = f"{upload_dir}/{uuid.uuid4().hex}{suffix}"
        form = {
            "policy": policy.get("policy", ""),
            "signature": policy.get("signature", ""),
            "oss_access_key_id": policy.get("oss_access_key_id", ""),
            "x_oss_object_acl": policy.get("x_oss_object_acl", "private"),
            "x_oss_forbid_overwrite": policy.get(
                "x_oss_forbid_overwrite", "true"
            ),
            "key": object_key,
            "success_action_status": "200",
        }
        upload_response = await client.post(
            upload_host,
            data=form,
            files={"file": (Path(filename).name, audio_bytes, mime_type)},
        )
        if upload_response.status_code >= 400:
            raise ASRError(
                f"音频上传失败：HTTP {upload_response.status_code}"
            )
        return f"oss://{object_key}"

    async def _submit_task(
        self, client: httpx.AsyncClient, file_url: str
    ) -> str:
        response = await client.post(
            f"{self.native_base_url}/services/audio/asr/transcription",
            headers={**self._headers, "X-DashScope-Async": "enable"},
            json={
                "model": self.model,
                "input": {"file_urls": [file_url]},
                "parameters": {"language_hints": ["zh", "en"]},
            },
        )
        if response.status_code >= 400:
            raise ASRError(f"创建转写任务失败：HTTP {response.status_code}")
        task_id = ((response.json() or {}).get("output") or {}).get("task_id")
        if not task_id:
            raise ASRError("转写任务缺少 task_id")
        return str(task_id)

    async def _wait_task(self, client: httpx.AsyncClient, task_id: str) -> str:
        for _ in range(self.max_polls):
            response = await client.get(
                f"{self.native_base_url}/tasks/{task_id}",
                headers=self._headers,
            )
            if response.status_code >= 400:
                raise ASRError(f"查询转写任务失败：HTTP {response.status_code}")
            output = (response.json() or {}).get("output") or {}
            status = str(output.get("task_status") or "").upper()
            if status == "SUCCEEDED":
                results = output.get("results") or []
                if not results or not results[0].get("transcription_url"):
                    raise ASRError("转写任务成功但缺少结果地址")
                return str(results[0]["transcription_url"])
            if status in ("FAILED", "CANCELED", "UNKNOWN"):
                raise ASRError(f"转写任务失败：{status}")
            await asyncio.sleep(self.poll_interval_seconds)
        raise LLMTimeoutError("语音转写超时")

    async def _fetch_transcript(
        self, client: httpx.AsyncClient, url: str
    ) -> str:
        response = await client.get(url)
        if response.status_code >= 400:
            raise ASRError("下载转写结果失败")
        transcripts = (response.json() or {}).get("transcripts") or []
        text = str((transcripts[0] or {}).get("text") or "").strip()
        if not text:
            raise ASRError("转写结果为空")
        return text

    async def transcribe(
        self, audio_bytes: bytes, mime_type: str, filename: str
    ) -> str:
        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                file_url = await self._upload_file(
                    client, audio_bytes, mime_type, filename
                )
                task_id = await self._submit_task(client, file_url)
                result_url = await self._wait_task(client, task_id)
                return await self._fetch_transcript(client, result_url)
        except LLMTimeoutError:
            raise
        except ASRError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("语音转写请求超时") from exc
        except httpx.HTTPError as exc:
            raise ASRError(f"语音转写请求失败：{exc}") from exc
