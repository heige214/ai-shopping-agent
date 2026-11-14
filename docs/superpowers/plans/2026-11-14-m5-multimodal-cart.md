# M5 图片理解、语音转写、AI 加购 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M4 导购会话上增加图片找货、语音转写回填、两阶段 AI 加购（action_card 确认/取消），不回归 M0-M4.1。

**Architecture:** 上传接口只负责落盘与转写，图片理解/ASR 由 `VisionClient`/`ASRClient` 抽象，fake 模式走确定性实现。图片理解结果合并进 `GuideQuery` 后复用 M4 结构化 + 商品向量 + RRF（倒数排名融合）+ 重排；加购解析复用 `slot_state.last_products`，新建 `chat_actions` 表，确认接口在事务内锁 action/SKU 并复用 `cart_service` 写 `cart_items`。前端在 `HomeView` 增加图片/录音控件与 `GuideActionCard`。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2 / Alembic / PostgreSQL 16 + pgvector / DashScope（qwen3-vl-flash、paraformer-v2）/ Vue 3 + Vant 4 + TypeScript / Playwright。

---

## 契约与文件边界

- 上传：`POST /api/uploads/image`（field `file`）→ `{url}`；`POST /api/uploads/voice` → `{url, transcript}`。图片 jpg/png/webp ≤5MB；音频 webm/mp4/wav ≤10MB；需登录。
- 消息：guide 允许 `text/image/voice`；support 仍只允许 `text`。图片 content `{image_url, text?}`，语音 content `{audio_url, transcript, text}`；pipeline 补写 `vision`。
- SSE：找货 `meta → token* → products → done`；加购 `meta → action → done`；确认/取消为普通 JSON。
- `action_card` content：`{action_id, action_type:"add_to_cart", status, payload:{product_id, sku_id, title, color, size, quantity, price, image}}`。
- `chat_actions` 状态：`pending/confirmed/cancelled/executed/failed`；确认成功直接 `executed`。

**新增文件**
- `backend/app/modules/uploads/{__init__,router,service}.py`
- `backend/app/ai/vision.py`、`backend/app/ai/asr.py`
- `backend/app/modules/guide/cart.py`、`backend/app/modules/guide/actions.py`
- `backend/alembic/versions/20261114_0005_create_chat_actions.py`
- `backend/tests/{test_uploads_api,test_vision_guide,test_guide_cart}.py`
- `frontend/src/api/uploads.ts`、`frontend/src/components/guide/{GuideActionCard,VoiceRecorder}.vue`
- `frontend/tests/fixtures/sample.png`

**修改文件**
- `backend/app/ai/{base,deps,fake,guide_local,guide_slots,dashscope}.py`、`app/ai/prompts/guide_parse.py`
- `backend/app/core/config.py`、`app/main.py`、`app/models.py`、`app/modules/support/{models,service}.py`
- `backend/app/modules/guide/{pipeline,router,schemas}.py`、`app/modules/commerce/cart_service.py`
- `backend/.env.example`、`.gitignore`、`README.md`
- `frontend/src/{api/guide.ts,types/guide.ts,types/support.ts,views/user/HomeView.vue,tests/e2e/guide.spec.ts,playwright.config.ts}`

---

## Commit 1：AI Vision/ASR 抽象 + 上传接口 + 单测

### Task 1.1 配置与客户端抽象

- [ ] 在 `core/config.py` 增加 `vision_model="qwen3-vl-flash"`、`asr_model="paraformer-v2"`、`max_image_upload_mb=5`、`max_voice_upload_mb=10`；`.env.example` 同步。
- [ ] `ai/base.py` 增加 `VisionResult`（category_path/attributes/description/confidence）、`VisionClient`、`ASRClient` 协议与 `VisionError`/`ASRError`。
- [ ] `ai/fake.py` 增加 `FakeVisionClient`（默认蓝色薄款纯棉衬衫，可注入结果/失败）、`FakeASRClient`（默认 “推荐几件衬衫”，可注入失败）。
- [ ] `ai/vision.py`：`LocalVisionClient` 返回低置信空结果；`DashScopeVisionClient` 用 OpenAI 兼容 `chat/completions` 发 base64 `image_url`，JSON 输出经 Pydantic 校验，失败重试 2 次。
- [ ] `ai/asr.py`：`LocalASRClient` 抛 `ASRError`；`DashScopeASRClient` 走百炼文件上传策略 + 异步 `audio/asr/transcription` + 轮询任务，读取 `transcription_url` 取 `transcripts[0].text`。
- [ ] `ai/deps.py` 增加 `get_vision_client`/`get_asr_client`：fake → Fake；dashscope+key → 真实；否则 Local。
- [ ] 测试：`tests/test_vision_guide.py` 覆盖 Fake 输出与失败；运行 `pytest tests/test_vision_guide.py -q`。

### Task 1.2 上传接口

- [ ] `modules/uploads/service.py`：`save_upload(file, kind, max_bytes)` 校验 MIME + 扩展名 + 魔数，分块读并在超限时抛 413；UUID 文件名；路径固定 `backend/static/uploads/`，禁止客户端文件名参与路径。`image` 允许 jpg/jpeg/png/webp；`voice` 允许 webm/mp4/wav（含 `audio/x-m4a`）。
- [ ] `modules/uploads/router.py`：两个 POST，`get_current_user` 鉴权；voice 调 `ASRClient.transcribe`，失败删除文件并返回 502「语音转写失败，请重试」。
- [ ] `main.py` 注册路由；`.gitignore` 增加 `backend/static/uploads/`。
- [ ] 测试 `test_uploads_api.py`：401、合法 PNG、错误扩展名/MIME、伪魔数、超限、voice fake transcript、voice ASR 失败 502。
- [ ] 运行：`pytest tests/test_uploads_api.py tests/test_vision_guide.py -q`。
- [ ] 提交：`feat: add vision and ASR clients with upload APIs`。

## Commit 2：chat_actions 迁移 + 加购管线 + confirm/cancel API + 单测

### Task 2.1 数据模型与迁移

- [ ] `support/models.py` 增加 `ChatAction`：id/session_id/message_id/action_type/payload/status/result/executed_at + created_at/updated_at；check 约束与索引；`app/models.py` 导出。
- [ ] 迁移 `20261114_0005_create_chat_actions.py`，down_revision `20261113_0004`；状态/动作类型 check，session/message 外键 CASCADE/SET NULL。
- [ ] `tests/test_guide_cart.py` 先写 schema 用例：迁移后表存在、非法 status 拒绝。
- [ ] 运行 `pytest tests/test_guide_cart.py -q`。

### Task 2.2 槽位解析与 last_products

- [ ] `ai/base.py`：`GuideIntent` 增加 `add_to_cart`；新增 `GuideCartQuery`（reference/ordinal/product_name/size/quantity）并作为 `GuideQuery.cart` 可选字段。
- [ ] `ai/guide_slots.py`：本地解析“加入购物车/加购/放到购物车”，支持“第一/第二/第2件”、显式商品名、“这个/它”、尺码、数量“2件/两件”，默认 1；非加购文本行为不变。`merge_guide_query` 只在搜索意图下合并 cart 为 None。
- [ ] `pipeline.py` 在 products 生成后写 `slot_state.last_products`（≤8：product_id/title/price/main_image/recommended_size）。
- [ ] 单测：解析、多轮、last_products 长度与字段。

### Task 2.3 加购动作服务

- [ ] `guide/cart.py`：`resolve_cart_target`（显式名 > 第 N 件 > 这个/它；多件“这个”反问）、`resolve_sku`（显式尺码 > last_products.recommended_size > 唯一尺码；多尺码反问）、`create_action`（校验商品/SKU/库存，写 chat_actions + action_card 消息）。
- [ ] `guide/pipeline.py` 识别 `intent=add_to_cart`：成功 `meta → action → done`（无 token/products）；需澄清 `meta → token* → done`；不覆盖既有 search 槽位。
- [ ] `commerce/cart_service.py` 给 `add_cart_item` 增加 `commit=True` 参数（默认行为不变），事务内复用。
- [ ] `guide/actions.py`：confirm 锁 action/SKU、越权 404、非 pending 幂等返回、pending 重校验并复用加购、失败置 failed + result.reason + available_sizes、成功 executed；同步更新 action_card 消息 content。cancel 同理幂等。
- [ ] `guide/router.py` 增加 `POST /chat/actions/{id}/confirm`、`/cancel`。
- [ ] 测试：第二件、显式尺码、尺码缺失反问、均码直加、confirm 幂等、cancel 幂等、库存不足 failed、下架 failed、越权 404。
- [ ] 运行：`pytest tests/test_guide_cart.py tests/test_guide_api.py -q`。
- [ ] 提交：`feat: add two-phase chat cart actions`。

## Commit 3：前端图片/语音输入 + action_card + E2E

### Task 3.1 图片与语音输入

- [ ] `api/uploads.ts`：`uploadImage`/`uploadVoice`（FormData，`Content-Type` 交给浏览器）。
- [ ] `api/guide.ts`：`sendGuideMessage` 改为接收 `{content_type, content}`；新增 confirm/cancel action API。
- [ ] `HomeView.vue` 输入栏加图片/语音按钮：
  - 图片：隐藏 file input（jpg/png/webp，前端限 5MB）→ 上传 → 预览条（缩略图 + 删除）→ 发送时 `content_type=image`，用户气泡显示缩略图与文字。
  - 语音：`VoiceRecorder.vue` 用 MediaRecorder 录 webm，显示计时/取消/完成；完成后上传 `/uploads/voice`，转写回填输入框且**不自动发送**，保留待发送语音附件；发送时 `content_type=voice`，气泡显示 `<audio controls>` + 文本；失败提示可重试。
- [ ] 历史消息恢复 image/voice/action_card 渲染。

### Task 3.2 Action 卡片

- [ ] `types/guide.ts` 增加 ActionCard 类型；`GuideActionCard.vue` 展示商品、颜色/尺码/数量、确认/取消；pending 才可点；成功后“已加入购物车”+“去购物车”，刷新购物车角标；失败展示 reason + 可换尺码；cancelled/executed 只读。
- [ ] `HomeView.vue` 在 AI 消息 content_type=action_card 时渲染该组件，SSE `action` 事件即时插入卡片。
- [ ] 确认/取消后更新消息 content，保证历史抽屉恢复正确状态。

### Task 3.3 E2E

- [ ] `tests/fixtures/sample.png`（1×1 合法 PNG）与 fake 设备录音：playwright 配置 `permissions:['microphone']`、`--use-fake-device-for-media-stream --use-fake-ui-for-media-stream`。
- [ ] `guide.spec.ts` 新增：
  1. 图片选择/预览/发送 → 缩略图 + 8 张衬衫卡（FakeVision）。
  2. 语音录制/完成 → 输入框回填 “推荐几件衬衫” → 用户确认发送 → 语音条 + 商品卡。
  3. “把第二件加入购物车” → action_card → 确认 → 已加入购物车/去购物车 → 重复确认不重复加购。
  4. 取消 action → 已取消且不可再确认。
  5. 显式商品名 + 2 件、预填购物车至库存-1 → 确认失败卡「库存不足」+ 可换尺码。
- [ ] 运行 `npm run build`、`npm run test:e2e`。
- [ ] 提交：`feat: add multimodal guide input and cart action cards`。

## Commit 4：README/progress/handoff + 全量回归

- [ ] README 增加 VISION_MODEL/ASR_MODEL/上传限制、上传目录与清理、fake 模式说明。
- [ ] 更新 `docs/progress.md`、`docs/implementation-handoff.md`（M5 完成项、测试数、遗留）。
- [ ] 全量：`cd backend && ./.venv/Scripts/python.exe -m pytest -q`（193 + 新增全过）；`cd frontend && npm run build && npm run test:e2e`（8 + 新增全过）。
- [ ] 手工烟测（真实 key，可选）：上传商品图识别品类/颜色/材质；录一句“推荐几件衬衫”转写；第二件加购确认。
- [ ] 提交：`docs: update M5 progress and handoff`；推送 `m5-multimodal-cart`；`git checkout main && git merge --no-ff m5-multimodal-cart && git tag m5`；推送 main 与 tag（GitHub 需临时 Clash 代理）。

## 验收清单

- [ ] 图片识别品类/颜色/材质并参与找货，聊天流显示缩略图；识别失败降级文字搜索并提示。
- [ ] 语音转写回填输入框，用户编辑确认后以 voice 消息发送；测试不访问真实百炼。
- [ ] “把第二件加入购物车”生成 action_card；确认后购物车数量正确；重复确认/取消幂等。
- [ ] 库存不足/下架返回 200 + failed 卡 + 可换尺码；越权 404。
- [ ] 原有 193 项 pytest、8 条 E2E、M4 商品卡 6~8 张/多轮/尺码/放宽澄清均不回归。
