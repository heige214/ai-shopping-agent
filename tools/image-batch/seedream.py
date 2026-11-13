"""Seedream 图片生成客户端。

参考 D:\\develop\\vibecoding\\demo.py 的火山方舟调用方式改写，
原项目文件不做任何修改。
"""

from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

logger = logging.getLogger("seedream")

TOOL_DIR = Path(__file__).resolve().parent
VIBECODING_ENV = Path(r"D:\develop\vibecoding\.env")

ARK_IMAGE_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
ARK_TIMEOUT = 180
VALID_SIZES = {"1K", "1.5K", "2K"}
_PLACEHOLDER_KEYS = {"", "ark-xxxx", "sk-xxxx"}


def _load_env() -> None:
    """优先读本工具 .env；没有有效 Key 时回退读参考项目 .env。"""
    load_dotenv(TOOL_DIR / ".env")
    key = (os.getenv("ARK_API_KEY") or os.getenv("HUOSHAN_API_KEY") or "").strip()
    if key in _PLACEHOLDER_KEYS and VIBECODING_ENV.exists():
        load_dotenv(VIBECODING_ENV, override=True)


_load_env()

ARK_IMAGE_MODEL = os.getenv("ARK_IMAGE_MODEL", "doubao-seedream-5-0-flash-260915")
ARK_API_KEY = (os.getenv("ARK_API_KEY") or os.getenv("HUOSHAN_API_KEY") or "").strip()


class SeedreamError(RuntimeError):
    """生图接口错误，status_code 用于区分是否值得重试。"""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def has_api_key() -> bool:
    return ARK_API_KEY not in _PLACEHOLDER_KEYS


def _extract_api_error(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300] or "无响应内容"
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return resp.text[:300] or "无响应内容"


def _parse_image_response(body: dict) -> Image.Image:
    """解析 Seedream 响应：优先 b64_json，其次 url 下载。"""
    data = body.get("data") or []
    if not data:
        raise SeedreamError("接口返回 data 为空，未生成图片")

    item = data[0]
    b64_json = item.get("b64_json")
    if b64_json:
        try:
            raw = base64.b64decode(b64_json, validate=True)
        except Exception as exc:
            raise SeedreamError(f"Base64 解析失败：{exc}") from exc
        try:
            return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            raise SeedreamError(f"图片解码失败：{exc}") from exc

    url = item.get("url")
    if url:
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise SeedreamError("下载生成图片超时") from exc
        except requests.exceptions.RequestException as exc:
            raise SeedreamError(f"下载生成图片失败：{exc}") from exc
        try:
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception as exc:
            raise SeedreamError(f"图片解码失败：{exc}") from exc

    raise SeedreamError("接口返回中既没有 b64_json 也没有 url")


def generate_image(prompt: str, size: str = "1K", watermark: bool = False) -> Image.Image:
    """调用火山方舟 Seedream 生成一张图片。"""
    if not has_api_key():
        raise SeedreamError("未配置 ARK_API_KEY / HUOSHAN_API_KEY，请检查 .env")
    if not prompt or not prompt.strip():
        raise SeedreamError("提示词为空")
    if size not in VALID_SIZES:
        raise SeedreamError(f"不支持的尺寸：{size}")

    payload = {
        "model": ARK_IMAGE_MODEL,
        "prompt": prompt.strip(),
        "size": size,
        "response_format": "b64_json",
        "output_format": "png",
        "watermark": bool(watermark),
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ARK_API_KEY}",
    }

    try:
        resp = requests.post(
            ARK_IMAGE_URL, headers=headers, json=payload, timeout=ARK_TIMEOUT
        )
    except requests.exceptions.Timeout as exc:
        raise SeedreamError(f"API 调用超时（{ARK_TIMEOUT} 秒）") from exc
    except requests.exceptions.RequestException as exc:
        raise SeedreamError(f"API 请求失败：{exc}") from exc

    if resp.status_code != 200:
        raise SeedreamError(
            f"API 返回 HTTP {resp.status_code}：{_extract_api_error(resp)}",
            status_code=resp.status_code,
        )

    try:
        body = resp.json()
    except ValueError as exc:
        raise SeedreamError("无法解析 API 返回结果") from exc

    return _parse_image_response(body)
