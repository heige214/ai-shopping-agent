"""批量生成：CSV 读取、任务队列、重试、状态持久化、ZIP 打包。"""

from __future__ import annotations

import csv
import json
import random
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

from prompts import PRODUCT_COLUMNS, build_prompt, validate_rows
from seedream import SeedreamError, generate_image

TOOL_DIR = Path(__file__).resolve().parent
DATA_DIR = TOOL_DIR / "data"
STATUS_FILE = DATA_DIR / "batch_status.json"
FAILED_FILE = DATA_DIR / "failed.csv"


@dataclass
class ItemResult:
    row: dict
    status: str  # done / failed / skipped
    file: str = ""
    error: str = ""
    duration: float = 0.0


def read_csv(path: str | Path) -> list[dict[str, str]]:
    """读取 CSV，兼容 Excel 导出的 UTF-8 BOM 和常见 GBK。"""
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                rows: list[dict[str, str]] = []
                for raw in reader:
                    row: dict[str, str] = {}
                    for key, value in raw.items():
                        if key is None:
                            continue
                        row[str(key).strip()] = (
                            value.strip() if isinstance(value, str) else ""
                        )
                    if any(row.values()):
                        rows.append(row)
                return rows
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(f"CSV 编码无法识别：{last_error}")


def sanitize_filename(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r'[\\/:*?"<>|\s]+', "_", text)
    return text.strip("._") or "unknown"


def output_path(output_dir: str | Path, row: dict) -> Path:
    row_id = sanitize_filename(row.get("id", ""))
    color = sanitize_filename(row.get("color", ""))
    return Path(output_dir) / f"{row_id}_{color}.png"


def load_status() -> dict:
    if not STATUS_FILE.exists():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_status(status: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = STATUS_FILE.with_suffix(".tmp")
    temp.write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp.replace(STATUS_FILE)


def write_failed(rows: list[dict]) -> None:
    """把失败项写入 data/failed.csv；传空列表会清空旧失败记录。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = PRODUCT_COLUMNS + ["error"]
    with open(FAILED_FILE, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{key: row.get(key, "") for key in PRODUCT_COLUMNS},
                    "error": row.get("error", ""),
                }
            )


def read_failed() -> list[dict[str, str]]:
    if not FAILED_FILE.exists():
        return []
    rows = read_csv(FAILED_FILE)
    return [{key: row.get(key, "") for key in PRODUCT_COLUMNS} for row in rows]


def _is_retryable(code: int | None) -> bool:
    # None = 超时/网络错误；429 = 限流；5xx = 服务端错误
    return code is None or code == 429 or (500 <= code < 600)


def _run_one(
    row: dict,
    output_dir: Path,
    template: str,
    size: str,
    retries: int,
    force: bool,
    skip_existing: bool,
    stop_event: threading.Event,
) -> ItemResult:
    path = output_path(output_dir, row)
    if stop_event.is_set():
        return ItemResult(row, "skipped", error="已停止")

    if path.exists() and not force and skip_existing:
        return ItemResult(row, "skipped", file=str(path), error="文件已存在")

    prompt = build_prompt(row, template)
    last_error = ""
    started = time.time()

    for attempt in range(retries + 1):
        if stop_event.is_set():
            return ItemResult(row, "skipped", error="已停止")
        try:
            image = generate_image(prompt, size=size, watermark=False)
            output_dir.mkdir(parents=True, exist_ok=True)
            image.save(path, format="PNG")
            return ItemResult(
                row, "done", file=str(path), duration=time.time() - started
            )
        except SeedreamError as exc:
            last_error = str(exc)
            if attempt < retries and _is_retryable(exc.status_code):
                time.sleep(min(2**attempt + random.random(), 10))
                continue
            break
        except Exception as exc:  # 未预期异常：重试后放弃
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(2**attempt + random.random(), 10))
                continue
            break

    return ItemResult(row, "failed", error=last_error, duration=time.time() - started)


def iter_batch(
    rows: list[dict],
    output_dir: str | Path,
    template: str,
    size: str = "1K",
    concurrency: int = 2,
    retries: int = 2,
    force: bool = False,
    skip_existing: bool = True,
    stop_event: threading.Event | None = None,
) -> Iterator[ItemResult]:
    """并发执行批量任务，按完成顺序 yield 结果。"""
    output_dir = Path(output_dir)
    stop_event = stop_event or threading.Event()
    workers = max(1, min(int(concurrency), 3))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _run_one,
                row,
                output_dir,
                template,
                size,
                retries,
                force,
                skip_existing,
                stop_event,
            ): row
            for row in rows
        }
        for future in as_completed(futures):
            row = futures[future]
            try:
                yield future.result()
            except Exception as exc:
                yield ItemResult(row, "failed", error=str(exc))


def make_zip(output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    images = sorted(output_dir.glob("*.png"))
    if not images:
        raise ValueError(f"输出目录没有 PNG：{output_dir}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / f"product_images_{datetime.now():%Y%m%d_%H%M%S}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for image in images:
            archive.write(image, arcname=image.name)
    return zip_path
