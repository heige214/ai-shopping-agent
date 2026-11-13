"""商品图批量生成器（Gradio 本地网页）。

参考 D:\\develop\\vibecoding\\demo.py 的 Seedream 调用方式改写，
原项目不做任何修改。

运行：
    D:\\develop\\vibecoding\\.venv\\Scripts\\python.exe app.py
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

import gradio as gr

from batch import (
    DATA_DIR,
    iter_batch,
    load_status,
    make_zip,
    read_csv,
    read_failed,
    save_status,
    write_failed,
)
from prompts import DEFAULT_TEMPLATE, PRODUCT_COLUMNS, build_prompt, validate_rows
from seedream import ARK_IMAGE_MODEL, generate_image, has_api_key

TOOL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOL_DIR.parents[1]
STATIC_ROOT = PROJECT_ROOT / "backend" / "static"
DEFAULT_OUTPUT = STATIC_ROOT / "products"
STATUS_HEADERS = ["id", "color", "status", "file", "error"]

_STOP_EVENT = threading.Event()
_LOG_LINES: list[str] = []


def _append_log(message: str) -> None:
    _LOG_LINES.append(f"[{datetime.now():%H:%M:%S}] {message}")
    del _LOG_LINES[:-200]


def _log_text() -> str:
    return "\n".join(_LOG_LINES)


def _stats_text(total: int, done: int, failed: int, skipped: int, current: str) -> str:
    processed = done + failed + skipped
    return (
        f"总计：{total}\n"
        f"完成：{done} ｜ 失败：{failed} ｜ 跳过：{skipped}\n"
        f"进度：{processed}/{total}\n"
        f"当前：{current}"
    )


def _parse_output_dir(text: str) -> Path:
    text = (text or "").strip().strip('"').strip("'")
    return Path(text).expanduser() if text else DEFAULT_OUTPUT


def load_csv(file_path):
    if isinstance(file_path, list):
        file_path = file_path[0] if file_path else None
    if not file_path:
        return [], [], "未上传文件"

    try:
        rows = read_csv(file_path)
    except Exception as exc:
        return [], [], f"读取失败：{exc}"

    errors = validate_rows(rows)
    preview = [[row.get(col, "") for col in PRODUCT_COLUMNS] for row in rows[:200]]
    info = f"已读取 {len(rows)} 行"
    if errors:
        info += "\n" + "\n".join(errors[:20])
        if len(errors) > 20:
            info += f"\n... 还有 {len(errors) - 20} 条错误"
    else:
        info += "，校验通过"
    return preview, rows, info


def preview_first(template, rows):
    if not rows:
        return "请先上传 CSV"
    return build_prompt(rows[0], template)


def test_first(rows, template, size):
    if not rows:
        return None, "没有商品", "请先上传 CSV"
    row = rows[0]
    try:
        prompt = build_prompt(row, template)
        image = generate_image(prompt, size=size, watermark=False)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = DATA_DIR / "test_preview.png"
        image.save(path, format="PNG")
        log = f"测试成功：{row.get('id')} {row.get('color')}\n提示词：{prompt}"
        return (
            str(path),
            f"测试成功：{row.get('id')} {row.get('color')}（仅预览，未写入输出目录）",
            log,
        )
    except Exception as exc:
        return None, f"测试失败：{exc}", f"测试失败：{exc}"


def _batch_generator(
    rows,
    template,
    size,
    concurrency,
    retries,
    force,
    skip_existing,
    output_dir_text,
    progress,
):
    if not rows:
        yield "没有可处理的商品", [], [], "请先上传 CSV"
        return

    errors = validate_rows(rows)
    if errors:
        yield "校验失败", [], [], "\n".join(errors)
        return

    output_dir = _parse_output_dir(output_dir_text)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        yield "输出目录不可用", [], [], f"无法创建输出目录 {output_dir}：{exc}"
        return

    _LOG_LINES.clear()
    stop_event = _STOP_EVENT
    stop_event.clear()

    status = load_status()
    total = len(rows)
    done = failed = skipped = 0
    status_rows: list[list[str]] = []
    gallery_paths: list[str] = []
    failed_rows: list[dict] = []

    _append_log(
        f"开始批量：{total} 条，尺寸 {size}，并发 {concurrency}，输出 {output_dir}"
    )
    yield _stats_text(total, 0, 0, 0, "启动中"), status_rows, gallery_paths, _log_text()

    for result in iter_batch(
        rows,
        output_dir,
        template,
        size=size,
        concurrency=int(concurrency),
        retries=int(retries),
        force=bool(force),
        skip_existing=bool(skip_existing),
        stop_event=stop_event,
    ):
        row_id = result.row.get("id", "")
        color = result.row.get("color", "")

        if result.status == "done":
            done += 1
            gallery_paths.append(result.file)
            gallery_paths = gallery_paths[-12:]
            _append_log(f"OK   {row_id} {color} -> {Path(result.file).name}")
        elif result.status == "failed":
            failed += 1
            failed_rows.append({**result.row, "error": result.error})
            _append_log(f"FAIL {row_id} {color}: {result.error}")
        else:
            skipped += 1
            _append_log(f"SKIP {row_id} {color}: {result.error or '已存在'}")

        status[row_id] = {
            "status": result.status,
            "file": result.file,
            "error": result.error,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
        save_status(status)

        status_rows.append(
            [
                row_id,
                color,
                result.status,
                Path(result.file).name if result.file else "",
                result.error,
            ]
        )
        processed = done + failed + skipped
        try:
            progress(processed / total, desc=f"{processed}/{total}")
        except Exception:
            pass

        yield (
            _stats_text(total, done, failed, skipped, f"{row_id} {color}"),
            status_rows,
            gallery_paths,
            _log_text(),
        )

    write_failed(failed_rows)
    _append_log(f"结束：完成 {done}，失败 {failed}，跳过 {skipped}")
    yield (
        _stats_text(total, done, failed, skipped, "已结束"),
        status_rows,
        gallery_paths,
        _log_text(),
    )


def start_batch(
    rows,
    template,
    size,
    concurrency,
    retries,
    force,
    skip_existing,
    output_dir_text,
    progress=gr.Progress(),
):
    yield from _batch_generator(
        rows,
        template,
        size,
        concurrency,
        retries,
        force,
        skip_existing,
        output_dir_text,
        progress,
    )


def retry_failed(
    rows,
    template,
    size,
    concurrency,
    retries,
    force,
    skip_existing,
    output_dir_text,
    progress=gr.Progress(),
):
    failed_rows = read_failed()
    if not failed_rows:
        status = load_status()
        failed_rows = [
            row
            for row in rows
            if status.get(row.get("id", ""), {}).get("status") == "failed"
        ]
    if not failed_rows:
        yield "没有失败项", [], [], "没有可重试的失败项"
        return

    # 重试时强制覆盖失败项，避免旧的半成品文件被跳过
    yield from _batch_generator(
        failed_rows,
        template,
        size,
        concurrency,
        retries,
        True,
        False,
        output_dir_text,
        progress,
    )


def stop_batch():
    _STOP_EVENT.set()
    _append_log("收到停止请求：当前进行中的请求完成后停止")
    return _log_text()


def zip_handler(output_dir_text):
    output_dir = _parse_output_dir(output_dir_text)
    try:
        return str(make_zip(output_dir))
    except Exception as exc:
        raise gr.Error(str(exc))


def download_template():
    path = DATA_DIR / "sample_products.csv"
    return str(path) if path.exists() else None


def create_ui() -> gr.Blocks:
    key_state = "已配置" if has_api_key() else "未配置"
    key_hint = (
        f"模型：`{ARK_IMAGE_MODEL}` ｜ API Key：**{key_state}**"
        if has_api_key()
        else (
            f"模型：`{ARK_IMAGE_MODEL}` ｜ API Key：**未配置**\n\n"
            "请在本目录创建 `.env`（复制 `.env.example`），或确认 "
            "`D:\\develop\\vibecoding\\.env` 里有 `ARK_API_KEY`。"
        )
    )

    with gr.Blocks(title="商品图批量生成器") as demo:
        gr.Markdown("# 商品图批量生成器")
        gr.Markdown(
            "基于火山方舟 Seedream，参考 `vibecoding/demo.py` 改写；"
            "原项目未改动。CSV → 固定模板 → 批量生图 → 按 `{id}_{color}.png` 落盘。"
        )
        gr.Markdown(key_hint)

        rows_state = gr.State([])

        with gr.Row():
            with gr.Column(scale=3):
                csv_file = gr.File(
                    label="1. 上传商品清单 CSV",
                    file_types=[".csv"],
                    type="filepath",
                )
                preview_table = gr.Dataframe(
                    label="商品预览（前 200 行）",
                    headers=PRODUCT_COLUMNS,
                    type="array",
                    interactive=False,
                    wrap=True,
                    max_height=320,
                )
                load_info = gr.Textbox(
                    label="读取 / 校验结果", lines=3, interactive=False
                )
                template_btn = gr.Button("下载 CSV 模板")
                template_file = gr.File(label="CSV 模板", interactive=False)

                with gr.Accordion("2. 生成参数", open=True):
                    with gr.Row():
                        size = gr.Dropdown(
                            choices=["1K", "1.5K", "2K"],
                            value="1K",
                            label="分辨率",
                        )
                        concurrency = gr.Slider(
                            minimum=1, maximum=3, value=2, step=1, label="并发数"
                        )
                        retries = gr.Slider(
                            minimum=0, maximum=3, value=2, step=1, label="失败重试"
                        )
                    with gr.Row():
                        force = gr.Checkbox(
                            label="强制重生成（覆盖已有文件）", value=False
                        )
                        skip_existing = gr.Checkbox(
                            label="跳过已存在文件", value=True
                        )
                    output_dir = gr.Textbox(
                        label="输出目录",
                        value=str(DEFAULT_OUTPUT),
                    )

                with gr.Accordion("3. 提示词模板", open=True):
                    template = gr.Textbox(
                        label="模板（支持占位符）",
                        value=DEFAULT_TEMPLATE,
                        lines=8,
                    )
                    gr.Markdown(
                        "占位符：`{id}` `{category}` `{subcategory}` `{color}` "
                        "`{color_hex}` `{material}` `{fit}` `{thickness}` "
                        "`{style}` `{gender}` `{key_feature}` "
                        "`{composition}` `{background}`"
                    )
                    preview_btn = gr.Button("预览首条提示词")
                    prompt_preview = gr.Textbox(
                        label="首条提示词预览", lines=6, interactive=False
                    )

                with gr.Row():
                    test_btn = gr.Button("测试第 1 条")
                    start_btn = gr.Button("开始批量生成", variant="primary")
                    stop_btn = gr.Button("停止", variant="stop")
                    retry_btn = gr.Button("重试失败项")

                with gr.Row():
                    zip_btn = gr.Button("打包下载 ZIP")
                    zip_file = gr.File(label="ZIP 下载", interactive=False)

                test_image = gr.Image(
                    label="测试结果（仅预览）", height=320, interactive=False
                )

            with gr.Column(scale=2):
                stats = gr.Textbox(
                    label="4. 进度",
                    value="未开始",
                    lines=4,
                    interactive=False,
                )
                status_table = gr.Dataframe(
                    label="生成状态",
                    headers=STATUS_HEADERS,
                    type="array",
                    interactive=False,
                    wrap=True,
                    max_height=420,
                )
                gallery = gr.Gallery(
                    label="最近生成",
                    columns=3,
                    height=420,
                    object_fit="contain",
                    allow_preview=True,
                )
                log = gr.Textbox(
                    label="日志", lines=14, max_lines=24, interactive=False
                )

        csv_file.change(
            load_csv,
            inputs=[csv_file],
            outputs=[preview_table, rows_state, load_info],
        )
        preview_btn.click(
            preview_first,
            inputs=[template, rows_state],
            outputs=[prompt_preview],
        )
        test_btn.click(
            test_first,
            inputs=[rows_state, template, size],
            outputs=[test_image, stats, log],
        )
        start_btn.click(
            start_batch,
            inputs=[
                rows_state,
                template,
                size,
                concurrency,
                retries,
                force,
                skip_existing,
                output_dir,
            ],
            outputs=[stats, status_table, gallery, log],
        )
        stop_btn.click(stop_batch, inputs=None, outputs=[log])
        retry_btn.click(
            retry_failed,
            inputs=[
                rows_state,
                template,
                size,
                concurrency,
                retries,
                force,
                skip_existing,
                output_dir,
            ],
            outputs=[stats, status_table, gallery, log],
        )
        zip_btn.click(zip_handler, inputs=[output_dir], outputs=[zip_file])
        template_btn.click(download_template, inputs=None, outputs=[template_file])

    return demo


if __name__ == "__main__":
    ui = create_ui()
    ui.queue(default_concurrency_limit=4)
    ui.launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=True,
        show_error=True,
        theme=gr.themes.Soft(),
        # 生成结果落在项目 backend/static 下，需显式允许 Gradio 读取
        allowed_paths=[str(STATIC_ROOT)],
    )
