# M4 AI 导购聊天 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** 在 M0-M3 基线上实现自然语言找货：首页导购聊天、槽位多轮合并、结构化+商品向量混合召回、LLM 重排 6~8 张商品卡、按档案与尺码表推荐尺码、无结果放宽/澄清一次。

**Architecture:** 复用 `chat_sessions` / `chat_messages`（`type=guide`）与现有 SSE 端点；新增 `app/modules/guide/` 承载导购检索、管线与尺码接口，`app/ai/` 新增 `GuideLLM` 抽象与本地/Fake/DashScope 实现。M3 support 管线不改，只在 service/router 中按会话类型分流。

**Tech Stack:** FastAPI、PostgreSQL + pgvector、SQLAlchemy async、LangGraph 不参与 guide、Pydantic、Vue 3 + Vant 4、Playwright。测试/E2E 固定 `AI_PROVIDER=fake`。

---

## Contracts

- `POST /api/chat/sessions` 新增 `new: bool = false`：`type=guide` 默认复用最近 active guide，`new=true` 显式新建；guide 不写问候消息。
- `GET /api/chat/sessions?type=guide` 可用；未知 type 仍 400。
- `POST /api/chat/sessions/{id}/escalate` 对 guide 返回 400；support 行为不变。
- SSE guide 顺序：`meta → token* → products → done`；错误时在 meta 后插入 `error`，仍保持 token 在 products 前、done 最后。
- 新增 `GET /api/products/{id}/size-recommendation`，需登录；不改 M1 商品 DTO。
- 商品卡字段：`id/title/price/original_price/main_image/brand/attributes/reason/recommended_size/size_reason/sales_count`。
- `slot_state` 结构：`{"query": GuideQuery, "clarify_count": int}`；多轮 refine 合并，切换品类时重置旧条件。
- 无结果放宽顺序固定为 `厚薄 → 材质 → 价格`，颜色/品类不放宽；放宽后仍无结果时澄清一次，第二次返回固定话术。
- `products.embedding` 无 key 时保持 NULL；`seed_product_embeddings.py` 默认只补 NULL，`--reembed` 全量重建。

## File Map

**Create**
- `backend/app/ai/guide_slots.py`：本地槽位解析、`merge_guide_query`、默认推荐理由。
- `backend/app/ai/guide_local.py`：`LocalGuideLLM`（解析/重排/流式总结）。
- `backend/app/ai/prompts/guide_parse.py`、`guide_rerank.py`、`guide_answer.py`。
- `backend/app/modules/guide/{__init__,schemas,size,search,pipeline,router}.py`。
- `backend/scripts/seed_product_embeddings.py`。
- `backend/tests/test_guide_slots.py`、`test_guide_size.py`、`test_guide_search.py`、`test_guide_api.py`、`test_product_embeddings.py`。
- `frontend/src/types/guide.ts`、`frontend/src/api/guide.ts`。
- `frontend/src/components/guide/GuideProductCard.vue`、`GuideEmptyState.vue`。
- `frontend/tests/e2e/guide.spec.ts`。

**Modify**
- `backend/app/ai/base.py`：`GuideQuery/GuidePrice/GuideSizeProfile/GuideRerank/GuideLLM`。
- `backend/app/ai/{fake,dashscope,deps}.py`：guide 实现与依赖。
- `backend/app/modules/support/{schemas,service,router}.py`：放开 guide、escalate 400、SSE 分流。
- `backend/app/main.py`：注册 guide router。
- `backend/tests/conftest.py`：`guide_catalog` fixture（10 衬衫 + 15 运动鞋 + 15 双肩包，含尺码表与 fake 向量）。
- `frontend/src/views/user/{HomeView,ProductDetailView,MeView}.vue`。
- `frontend/tests/e2e/catalog.spec.ts`：首页入口改为直达 `/category/1` + 热门商品卡。
- `README.md`、`docs/progress.md`、`docs/implementation-handoff.md`。

---

## Task 1: Guide 槽位、尺码规则与 AI 抽象（commit 1）

**Files:** `app/ai/base.py`、`app/ai/guide_slots.py`、`app/ai/guide_local.py`、`app/ai/fake.py`、`app/ai/dashscope.py`、`app/ai/deps.py`、`app/ai/prompts/guide_*.py`、`tests/test_guide_slots.py`、`tests/test_guide_size.py`、`app/modules/guide/size.py`

- [ ] 写失败测试 `test_guide_slots.py`：解析“蓝色薄款纯棉衬衫，200元以内，身高172，体重75”；解析“300-500元运动鞋”；解析“深灰色加厚外套”；`merge_guide_query` 保留颜色并覆盖价格；切换品类重置；档案身高体重兜底；`随便看看` 不追问；“你好”为 chitchat。
- [ ] 写失败测试 `test_guide_size.py`：172/75→L；165/55 同时命中 S/M 时取较大 M；180/90 无精确命中→最近 XL 且含“建议试穿”；缺体重→不推荐；鞋款无脚长→用 `usual_size` 兜底；无尺码表→原因明确。
- [ ] 运行 `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_guide_slots.py tests/test_guide_size.py -q`，确认失败。
- [ ] 在 `base.py` 增加 Pydantic 模型与 `GuideLLM` Protocol；`guide_slots.py` 实现 `extract_local_guide_query`、`merge_guide_query`（`RESET_WORDS`、`不限预算` 清价格、档案兜底）、`default_reason`。
- [ ] `guide_local.py` 实现规则解析（品类 hint 最长匹配、颜色/材质/厚薄词表、价格区间、“身高/体重”标签、chitchat）与确定性总结；`fake.py` 增加可注入 query/rerank/answer 与 `fail_parse/fail_rerank/fail_stream` 的 `FakeGuideLLM`。
- [ ] `dashscope.py` 用现有 `_structured` 增加 `parse_guide_query` / `rerank_products`，用新增 prompt 增加 `stream_guide_answer`；`deps.py` 增加 `get_guide_llm()`（fake / dashscope / local）。
- [ ] `modules/guide/size.py` 实现 `resolve_size_chart`、`recommend_size`（规则 1 精确命中；规则 2 中心归一化距离、并列取较大码；规则 3 最近行 + 建议试穿；规则 4 缺身高/体重不推荐）与 `recommend_product_size`。
- [ ] 运行上述两个测试文件，全部通过；`git add -A && git commit -m "feat: add guide slots and size recommendation"`。

## Task 2: 混合检索、导购管线、会话 API 与商品向量（commit 2）

**Files:** `modules/guide/{schemas,search,pipeline,router}.py`、`modules/support/{schemas,service,router}.py`、`main.py`、`scripts/seed_product_embeddings.py`、`tests/conftest.py`、`tests/test_guide_search.py`、`tests/test_guide_api.py`、`tests/test_product_embeddings.py`

- [ ] 在 `conftest.py` 增加 `guide_catalog` fixture：一级品类服装/鞋靴/箱包 + 叶子衬衫/运动鞋/双肩包；10 件衬衫覆盖蓝/黑/白、纯棉/亚麻/聚酯、薄款/常规/加厚、109~389 元；15 双运动鞋、15 个双肩包；衬衫带 S/M/L/XL 尺码表；用 `FakeEmbeddingClient` 写入标题+属性向量。
- [ ] 写失败测试 `test_guide_search.py`：品类解析到叶子；颜色/材质/厚薄/价格结构化过滤；`棉` 用 ILIKE 命中纯棉/棉麻；fake 向量召回；RRF 合并顺序；放宽顺序 `["厚薄","材质","价格"]`；颜色永不放宽。
- [ ] 写失败测试 `test_guide_api.py`：guide 创建 201 且无问候、默认复用、`new=true` 新建、escalate 400、用户隔离；SSE 顺序 `meta→token*→products→done`；商品卡 8 张；多轮“蓝色衬衫”→“150以内”颜色保留且价格覆盖；放宽 query 返回 `relaxed=["厚薄","材质"]`；无结果首次 `need_clarify=true`、第二次固定话术；rerank/stream/parse 失败降级仍出卡；chitchat 无产品；尺码接口 172/75→L、缺档案不推荐、未登录 401、商品不存在 404。
- [ ] 写失败测试 `test_product_embeddings.py`：默认只补 NULL、二次执行 0、`refresh=True` 全量、Noop 客户端保持 NULL。
- [ ] 实现 `search.py`：`resolve_category_ids`（一级含子类、叶子自身）、`build_conditions`（status/品类/价格/属性，材质 ILIKE、颜色/厚薄等值）、结构化 top30、`Product.embedding` 余弦 top30、`rrf_merge_products(k=60)`、按 `厚薄→材质→价格` 逐级放宽。
- [ ] 实现 `pipeline.py`：解析→合并 slot_state→检索→发 `meta`（intent/query/need_clarify/relaxed/quick_replies/degraded）→重排（失败回退 RRF 前 8）→尺码推荐→流式总结→`products`→持久化 AI 消息与 `slot_state`→`done`；chitchat/价格区间矛盾/无结果分别走固定分支。
- [ ] `schemas.py` 定义 `GuideProductCard/GuideProductsPayload/SizeRecommendationOut`；`router.py` 实现 `GET /products/{id}/size-recommendation`；`main.py` 注册。
- [ ] 改 `support/schemas.py` 加 `new`；`support/service.py` 放开 guide、复用/新建、无问候、escalate 400、列表允许 guide；`support/router.py` 按 `session.type` 分流 `stream_guide_turn` 并注入 `get_guide_llm`。同步更新 M3 中“guide 400”的旧断言。
- [ ] 实现 `seed_product_embeddings.py`：`build_product_text(title/brand/品类/描述/属性)`，批量 10 条，默认补 NULL，`--reembed` 全量，无 key 不中断。
- [ ] 运行 `tests/test_guide_search.py tests/test_guide_api.py tests/test_product_embeddings.py tests/test_support_api.py tests/test_support_pipeline.py -q` 通过；提交 `feat: add hybrid guide retrieval and APIs`。

## Task 3: 前端导购聊天与尺码卡（commit 3）

**Files:** `frontend/src/types/guide.ts`、`api/guide.ts`、`components/guide/*`、`views/user/HomeView.vue`、`ProductDetailView.vue`、`MeView.vue`、`tests/e2e/{guide,catalog}.spec.ts`

- [ ] `types/guide.ts` 定义 `GuideQuery/GuideProductCard/GuideStreamMeta/SizeRecommendation`；`api/guide.ts` 提供 `createGuideSession(newSession)`、`fetchGuideSessions`、`fetchGuideMessages`、`sendGuideMessage`、`fetchSizeRecommendation`。
- [ ] `GuideEmptyState.vue`：保留“你好，{昵称}”“按品类逛逛”“大家都在看”；3 条示例问法、4 个品类按钮（点击发送“我想看看{品类}”）、8 个热门商品 `ProductCard`、档案提示（172cm · 75kg · 常穿 M 码 / 完善档案提示）。
- [ ] `HomeView.vue` 改为聊天布局：顶部品牌 + 新对话 + 购物车角标；消息区用户/AI 气泡；AI 消息内嵌 6~8 张 `GuideProductCard`（图片、标题、价格、属性、推荐尺码、理由）；流式气泡；澄清快捷回复；底部输入栏（无图片/语音，留 M5）。逻辑：挂载时拉最近 guide 会话与 50 条消息、热门商品；首次发送时创建会话；`新对话` 调 `new=true` 并清空；SSE 处理 `meta/token/products/done/error`；历史消息从 `meta.products` 恢复卡片。
- [ ] `ProductDetailView.vue` 加载后调尺码接口：有推荐显示“推荐 L 码 + 理由 + 选择此尺码”；缺档案显示“去完善身材档案”链接；无尺码表不显示。`MeView.vue` 的“导购会话”改为可点击“去 AI 找货”。
- [ ] 更新 `catalog.spec.ts`：保留“你好，小鹿”“按品类逛逛”，分类列表改为直达 `/category/1`，后续详情/收藏链路不变。
- [ ] 新增 `guide.spec.ts`：空状态断言 → 点“推荐几件衬衫” → 用户气泡 + 8 张 `.guide-product-card` → 点卡进详情 → 返回 → 发送“要蓝色的” → 卡片含“蓝色” → 新对话清空；demo 登录商品详情断言“推荐 L 码”并点选。
- [ ] 运行 `cd frontend && npm run build` 与 `npm run test:e2e` 通过；提交 `feat: add guide chat home and size card`。

## Task 4: 文档、全量回归与合并（commit 4）

**Files:** `README.md`、`docs/progress.md`、`docs/implementation-handoff.md`、必要时测试修正

- [ ] README：M4 功能、`seed_product_embeddings.py`（默认补 NULL / `--reembed`）、无 key 时商品向量 NULL 与结构化兜底、guide SSE/会话规则、测试命令。
- [ ] progress.md 增加 2026-11-14 M4 记录：完成项、改动文件、DB/环境变量（无迁移/无新增变量）、pytest/build/E2E 实际数字、遗留项。
- [ ] implementation-handoff.md 更新当前状态、M4 规则、M5 依赖（图片/语音/加购/chat_actions）。
- [ ] 全量验证：`cd backend && ./.venv/Scripts/python.exe -m pytest -q`；`cd frontend && npm run build`；`cd frontend && npm run test:e2e`。记录实际通过数，不接受估算。
- [ ] 如开发库有真实 key，运行 `python -m scripts.seed_product_embeddings` 填充 300 条商品向量；无 key 时记录 NULL。
- [ ] 提交 `docs: update M4 progress and handoff`；`git push -u origin m4-guide-agent`（GitHub 需要 Clash 代理）；`git checkout main && git merge --no-ff m4-guide-agent`；`git tag m4`；推送 main 与 tag。

---

## Verification Matrix

| 验收项 | 覆盖 |
|---|---|
| 自然语言找货 | `test_guide_slots` + `test_guide_api` + guide E2E |
| 商品卡 6~8 | `test_guide_api` 断言 8；guide E2E 断言 8 |
| 多轮条件合并 | `test_guide_api` 蓝色衬衫→150以内；E2E 蓝色 refine |
| 尺码推荐 | `test_guide_size` + 尺码接口测试 + demo 详情 E2E |
| 无结果放宽/澄清 | `test_guide_search` 放宽顺序；`test_guide_api` 澄清一次 |
| M3 不回归 | `test_support_api`、`test_support_pipeline`、support E2E |
| M0-M2 不回归 | auth/catalog/commerce E2E；M1 DTO 未改 |
