# M3 知识库 + RAG 商品客服 实施计划

> 执行方式：主窗口按下方 4 个提交批次直接实现；每批先写测试再实现，完成后跑相关 pytest。最终跑全量 pytest、`npm run build`、Playwright。

**目标：** 在 M0-M2 之上落地知识库、混合检索与商品客服 SSE 问答，支持引用、反馈、一次性澄清和最小转人工闭环。

**架构：** 新增 `knowledge`（文档/切片/检索）与 `support`（会话/消息/工单/SSE）两个后端模块；AI 能力集中在 `app/ai/`，通过 `SupportLLM` / `EmbeddingClient` 协议切换 DashScope、本地规则和测试 Fake。检索范围固定为当前商品 + 一级品类 + 平台，向量 top20 + 关键词 top20 经 RRF 取 top8。前端新增独立客服页，用 fetch + ReadableStream 解析 POST SSE。

**技术栈：** FastAPI、SQLAlchemy async、PostgreSQL + pgvector、jieba、httpx、Vue 3 + Vant 4、Playwright。

---

## 数据与文件结构

```text
backend/app/modules/knowledge/{__init__,models,retrieval}.py
backend/app/modules/support/{__init__,models,schemas,service,pipeline,router}.py
backend/app/ai/{__init__,base,local,fake,dashscope,embeddings,deps}.py
backend/app/ai/prompts/{__init__,support_intent,support_answerable,support_answer}.py
backend/alembic/versions/20261113_0004_create_knowledge_support.py
backend/seeds/knowledge/{knowledge.json,category_faq_drafts.json,review.csv}
backend/scripts/{build_knowledge_seed,seed_knowledge}.py
backend/tests/{test_knowledge_schema,test_knowledge_retrieval,test_support_api,test_support_pipeline}.py
frontend/src/types/support.ts
frontend/src/api/support.ts
frontend/src/utils/sse.ts
frontend/src/views/user/SupportView.vue
frontend/tests/e2e/support.spec.ts
frontend/tests/e2e/start-backend.mjs
```

关键契约：

- `knowledge_documents(id, scope, product_id, category_id, doc_type, title, source, status, created_at, updated_at)`；scope=product/category/platform，status=active/archived。
- `knowledge_chunks(id, document_id, product_id, category_id, content, search_text, embedding vector(1024), meta, created_at, updated_at)`；HNSW `vector_cosine_ops` + GIN `to_tsvector('simple', search_text)`。
- `chat_sessions(id, user_id, type, product_id, title, status, slot_state, summary, created_at, updated_at)`；status=active/waiting_human/human/closed。
- `chat_messages(id, session_id, sender_type, sender_id, content_type, content, meta, created_at)`。
- `support_tickets(id, session_id, user_id, product_id, status, assigned_agent_id, context_summary, extraction_status, close_reason, rating, rating_comment, connected_at, closed_at, created_at, updated_at)`。
- 不建 `chat_actions`（M5）、`knowledge_candidates` / `product_field_history`（M7）。

---

## 批次 1：知识表 + 种子 + AI 基础

**Files:** migration 0004、`knowledge/models.py`、`support/models.py`、`app/models.py`、`core/config.py`、`ai/*`、`scripts/build_knowledge_seed.py`、`scripts/seed_knowledge.py`、`seeds/knowledge/*`、`tests/test_knowledge_schema.py`。

- [ ] 配置新增 `ai_provider=auto|dashscope|local|fake`、`dashscope_api_key`（空串归一为 None）、`dashscope_base_url`、`chat_model`、`embedding_model`、`embedding_dim=1024`、`llm_timeout_seconds=20`。
- [ ] 迁移 0004 建 5 张表、约束、B-tree/partial 索引、HNSW 与 GIN 表达式索引；`downgrade()` 完整回滚。
- [ ] `app/ai/base.py` 定义 `SupportLLM` / `EmbeddingClient` 协议、`IntentResult`、`AnswerabilityResult`、`LLMError`。
- [ ] `app/ai/deps.py`：provider=fake → `FakeSupportLLM` + `FakeEmbeddingClient`；有 key → DashScope；无 key → `LocalSupportLLM` + `NoopEmbeddingClient`。
- [ ] `dashscope.py` 用 httpx 调 OpenAI 兼容 `/chat/completions` 与 `/embeddings`；JSON 输出 Pydantic 校验，失败重试 2 次；流式解析 `data:`；超时 20s。prompt 全部放 `ai/prompts/`。
- [ ] `local.py` 规则意图（product/size/policy/order/complaint/chitchat/unknown）、资料重叠度可答性、片段拼接回答；保证无 key 可演示。
- [ ] `fake.py` 确定性回答 + 可注入意图/可答性；`FakeEmbeddingClient` 用字符 1~2 gram 哈希成 1024 维并归一化。
- [ ] `build_knowledge_seed.py` 读取商品/品类 JSON，生成 300 detail（每份 2 chunk）+ 300 size（1 chunk）+ 900 商品 FAQ（每商品 3 条）+ 4 份一级品类 care + 9 份平台 policy，共 913 文档 / 1813 chunk；商品 FAQ 规则化 approved；24 条品类 FAQ 草稿写 `category_faq_drafts.json` 并标 pending，不进 `knowledge.json`；生成 `review.csv`。默认拒绝覆盖，`--force` 才重建。
- [ ] `seed_knowledge.py` 按 `meta.seed_key` / 文档键幂等导入 approved 内容；embedding 存在时用 pgvector 最近邻余弦 >0.92 去重；`--embeddings-only` 只补 NULL embedding；无 key 时 embedding 为 NULL 且正常完成。
- [ ] 测试：迁移表/索引存在；种子文档与 chunk 数量、pending 未入库；重复执行数量不变；fake embedding 下完全相同文本去重；无 key 模式 seed 成功且 embedding 全 NULL；补齐 embedding 后非空。
- [ ] 提交：`feat: add knowledge tables and seed pipeline`。

## 批次 2：混合检索 + 可回答性

**Files:** `knowledge/retrieval.py`、`ai/prompts/support_answerable.py`、`tests/test_knowledge_retrieval.py`、conftest fixtures。

- [ ] `resolve_scope(db, product)`：返回商品 id、一级品类祖先 id 列表；scope 条件只命中当前商品 / 一级品类 / 平台，排除其他商品、叶子品类、其他一级品类。
- [ ] 向量召回：查询向量非 NULL 时 `embedding <=> query` top20，相似度 `1 - distance`；无向量跳过，不报错。
- [ ] 关键词召回：jieba 分词 → 只保留中文/字母/数字 token → `to_tsquery('simple', 'a | b')`，`search_text` 上 GIN，按 `ts_rank` top20。
- [ ] `rrf_merge(vector_hits, keyword_hits, k=60, limit=8)`：按 chunk id 累加 `1/(k+rank)`；返回相似度、来源、doc 类型/标题。
- [ ] `retrieve_context(...)` 同时读取商品事实（标题、品牌、价格、属性、尺码表、库存汇总），供回答注入。
- [ ] 测试：RRF 排序与去重；范围过滤；关键词 fallback（embedding 全 NULL）；向量召回（fake embedding）；`max_similarity` 正确。
- [ ] 提交：`feat: add hybrid knowledge retrieval`。

## 批次 3：客服 API + SSE 管线

**Files:** `support/{schemas,service,pipeline,router}.py`、`main.py`、`tests/test_support_api.py`、`tests/test_support_pipeline.py`。

- [ ] 会话：`POST /api/chat/sessions`；只允许 `type=support`，`guide` 返回 400；同用户同商品复用最近 `active` support 会话，否则新建并写 AI 问候消息；`GET /api/chat/sessions?type=` 按用户隔离。
- [ ] 消息：`GET .../messages?before_id=&limit=` 倒序取再正序返回 `{items, has_more}`；`POST .../messages` 仅 text，图片/语音 400；会话非 active 返回 409；首条用户消息截 50 字写 `title`。
- [ ] 管线：意图路由 → 固定话术或检索 → 可回答性 → 流式回答；`product_qa/size_qa/policy_qa` 走 RAG；`order_qa/complaint` 固定话术 + `handoff_required=true`；`chitchat` 简短引导；`unknown` 澄清一次后兜底。
- [ ] 可回答性：无 chunk 且 `max_similarity < 0.35` 直接不可答；`can_answer=false` 或 `confidence < 0.6` 且 `clarify_count=0` 先澄清（写 `slot_state.clarify_count`），否则固定兜底 + `handoff_required=true`；`partial=true` 回答已知部分并建议转人工。
- [ ] SSE 顺序：能答 `meta → token* → citations → answer_meta → done`；固定/澄清/兜底 `meta → token* → answer_meta → done`；LLM 失败 `meta → error → token(降级话术) → answer_meta → done`，20s 超时不挂起。`answer_meta` 含 `can_answer/confidence/partial/handoff_required/intent`。AI 消息 `meta` 存意图、引用、检索统计、耗时。
- [ ] `POST .../escalate`：幂等创建 `waiting` 工单，会话置 `waiting_human`，返回 `{ticket_id, session_status}`；`POST /api/chat/messages/{id}/feedback` 只允许本人 AI 消息，写 `meta.feedback`。
- [ ] 测试：会话复用/越权/guide 400；消息分页；意图路由各分支；澄清一次；兜底；partial；SSE 事件顺序；LLM 超时/异常降级；escalate 建等待工单且重复幂等；反馈越权 404。
- [ ] 提交：`feat: add support chat API with SSE`。

## 批次 4：前端客服页 + E2E + 文档

**Files:** `types/support.ts`、`api/support.ts`、`utils/sse.ts`、`views/user/SupportView.vue`、`router/index.ts`、`ProductDetailView.vue`、`tests/e2e/support.spec.ts`、`tests/e2e/start-backend.mjs`、`playwright.config.ts`、`README.md`、`docs/progress.md`、`docs/implementation-handoff.md`。

- [ ] 类型与 API：会话/消息/引用/answer_meta 类型；`createSupportSession`、`listSupportMessages`、`sendSupportMessage`、`escalateSupportSession`、`sendSupportFeedback`。
- [ ] `utils/sse.ts`：fetch POST + ReadableStream，处理跨 chunk 缓冲、`\r\n`、`event:`/`data:` 多行；非 2xx 抛后端 detail。
- [ ] `SupportView.vue`：商品摘要、消息流、AI 头像、用户气泡、流式文本、引用 chips、有帮助/没帮助、兜底卡片 + 转人工、等待人工 banner、输入框；session 为 waiting_human 时禁用输入；头部「转人工」。
- [ ] 路由新增 `/product/:id/support`（requiresAuth）；商品详情底部「客服」改为跳转；不改其他 M1/M2 契约。
- [ ] Playwright：`start-backend.mjs` 定位 `backend/.venv` Python 并以 `AI_PROVIDER=fake` 启动 8100；config 增加后端 webServer；用例注册唯一用户 → 商品详情 → 客服 → 问材质（流式+引用）→ 连续两个知识库外问题（澄清 → 兜底）→ 转人工（提示等待）。
- [ ] 跑后端全量 pytest（≥104 + 新增）、`npm run build`、`npm run test:e2e`；M0-M2 用例不回归。
- [ ] 更新 README（新环境变量、知识种子、fake 模式、E2E 自启后端）、progress M3、handoff 下一步 M4。
- [ ] 提交：`feat: add product support page and e2e`；随后按用户要求推送分支、合并 main、打 tag `m3`。

---

## 验证清单

- 后端：`cd backend && source .venv/Scripts/activate && python -m pytest -q`，全绿且无真实 DashScope 请求。
- 种子：`python -m scripts.build_knowledge_seed`（已有文件时跳过）、`python -m scripts.seed_knowledge`、再次执行数量不变；无 key 时 embedding 为 NULL。
- 前端：`cd frontend && npm run build`。
- E2E：后端由 Playwright 以 `AI_PROVIDER=fake` 启动；`npm run test:e2e` 全绿。
- 手工：选 3 个商品分别问材质/尺码/洗护，问 1 个平台政策，问 1 个知识库外问题；确认引用来自当前商品/品类/平台，无编造；转人工后会话为 `waiting_human`。
- 冲突或超 10 分钟卡点立即停下报告，不 force push，不删除 `m3-knowledge-rag`。
