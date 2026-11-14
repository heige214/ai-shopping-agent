# 项目进度日志

> 用途：每个模块 / 窗口结束时更新一次，给下一个窗口做交接。
> 规则：只记事实，不重复设计文档；接口、DB 契约变更先改设计文档，再改这里。
> 最新记录放最上面。

最后更新：2026-11-14

## 当前状态

| 里程碑 | 内容 | 状态 | 最近提交 |
|---|---|---|---|
| M0 | 项目骨架：配置、DB、认证、前端壳、测试基线 | 已完成 | m0 |
| M1 | 商品域 + 种子数据 + 商品详情 | 已完成 | m1-product-catalog |
| M2 | 购物车、地址、订单、模拟支付/发货 | 已完成 | m2 |
| M3 | 知识库 + RAG 商品客服 | 已完成 | m3 |
| M4 | 导购聊天、意图槽位、澄清、尺码 | 已完成 | m4 |
| M5 | 图片理解、语音、AI 加购 | 未开始 | — |
| M6 | 转人工、客服端队列/工作台 | 未开始 | — |
| M7 | 知识提炼、审核、入库 | 未开始 | — |
| M8 | 评测集、消融实验、指标 | 未开始 | — |
| M9 | 部署、论文材料、演示排练 | 未开始 | — |

状态只用：未开始 / 进行中 / 已完成 / 阻塞。

## 当前阻塞

- 无。

## 模块记录

<!-- 每完成一个模块，把记录加在这里的最上面；第一条从 M0 开始。 -->

## 2026-11-14 · M4.1 导购历史会话抽屉

- 状态：已完成（分支 `m4.1-guide-history`，tag `m4.1`）
- 本次目标：补设计 §11.1.2 的导购会话历史抽屉，支持查看和切换历史会话。
- 完成内容：
  - 首页顶部新增「历史」按钮；左侧 Vant popup 列出 `GET /api/chat/sessions?type=guide` 返回的会话，显示标题、更新时间、进行中/已结束，当前会话高亮。
  - 点击会话切换并加载最近 50 条消息，恢复商品卡；抽屉内可显式新建会话；已结束会话输入禁用。
  - 无后端、DB、环境变量改动。
- 改动文件：`frontend/src/views/user/HomeView.vue`、`frontend/tests/e2e/guide.spec.ts`、`README.md`、`docs/progress.md`、`docs/implementation-handoff.md`
- 测试与验收：前端 `npm run build` 成功；E2E `8 passed`（guide 用例扩展历史抽屉，其余 7 条不回归）。
- 遗留问题：无。
- 下一模块依赖：M5 可继续在 guide 会话上增加图片/语音与加购。
- commit：m4.1 tag（见 `git log`）

## 2026-11-14 · M4 AI 导购聊天

- 状态：已完成（分支 `m4-guide-agent`，tag `m4`）
- 本次目标：首页导购聊天、自然语言找货、多轮槽位合并、结构化 + 商品向量混合检索与重排、无结果放宽/澄清、按档案与尺码表推荐尺码。
- 完成内容：
  - 会话：复用 `chat_sessions` / `chat_messages`，放开 `type=guide`；默认复用最近 active guide，`new=true` 显式新建，不写问候消息；guide escalate 返回 400；support 行为不变。
  - 槽位：`GuideQuery`（intent / semantic / category_path / filters / price / size_profile）；本地规则与 DashScope 解析共用；`merge_guide_query` 多轮合并，切换品类/重置词清空旧条件，档案身高体重兜底，“不限预算”清空价格。
  - 检索：`resolve_category_ids`（一级含子类、叶子自身）；结构化条件（on_sale / 品类 / 价格 / 颜色 / 材质 ILIKE / 厚薄）+ `products.embedding` 余弦 top30 → RRF(k=60) → LLM 重排 top8；无结果按厚薄→材质→价格放宽，颜色与品类不放宽；仍无结果澄清一次，第二次固定话术。
  - SSE：`meta → token* → products → done`；meta 含 intent/query/need_clarify/relaxed/quick_replies/degraded；错误事件插在 meta 后；AI 消息持久化 `meta.products/query/relaxed`，历史可从消息恢复商品卡。
  - 尺码：新增 `GET /api/products/{id}/size-recommendation`；精确命中→中心归一化距离最小（并列取较大码）、无命中→最近行 + 建议试穿、缺身高体重/鞋款缺脚长不推荐（鞋款可用常穿尺码兜底）；导购卡与详情卡展示 `recommended_size/size_reason`，未改 M1 DTO。
  - 商品向量：新增 `seed_product_embeddings.py`，默认只补 NULL、`--reembed` 全量、无 key 时保持 NULL；开发库已用 `text-embedding-v3` 写入 300/300。
  - 前端：首页改为导购聊天（问候 + 档案提示 + 3 条示例 + 4 个品类入口 + 8 个热门商品；消息流 + AI 气泡 + 6~8 张商品卡 + 流式 + 快捷回复 + 新对话；不含图片/语音）；商品详情新增尺码推荐卡；Me 页入口改为“AI 找货”。
- 改动文件 / 目录：
  - `backend/app/ai/{base,guide_slots,guide_local,fake,dashscope,deps}.py`、`app/ai/prompts/guide_*.py`
  - `backend/app/modules/guide/`、`app/modules/support/{schemas,service,router}.py`、`app/main.py`
  - `backend/scripts/seed_product_embeddings.py`
  - `backend/tests/{conftest,test_guide_slots,test_guide_size,test_guide_search,test_guide_api,test_product_embeddings,test_support_api}.py`
  - `frontend/src/types/guide.ts`、`api/guide.ts`、`components/guide/`、`views/user/{HomeView,ProductDetailView,MeView}.vue`
  - `frontend/tests/e2e/{guide,catalog,commerce}.spec.ts`
  - `README.md`、`docs/superpowers/plans/2026-11-14-m4-guide-agent.md`
- DB 迁移：无（`products.embedding` 列已存在）
- 新增环境变量：无
- 测试与验收：
  - 命令：`cd backend && ./.venv/Scripts/python.exe -m pytest -q`；`cd frontend && npm run build`；`cd frontend && npm run test:e2e`
  - 结果：后端 `193 passed`（145.35s；原 155 + 新增 38）；前端构建成功；E2E `8 passed`（43.3s；原 6 条不回归 + 新增导购 2 条）。
  - 真实模型手工（qwen-plus + text-embedding-v3）：
    - “推荐几件衬衫” → 8 张卡、全部推荐 L；“通勤双肩包” → 8 张；“跑步运动鞋” → 8 张。
    - “找一件200元以内的蓝色薄衬衫，身高172体重75” → 1 张蓝色亚麻衬衫（L）；再问“要150元以内的” → 颜色/厚薄保留，价格覆盖为 150。
    - “紫色真丝加厚衬衫10元以内” → `relaxed=["厚薄","材质","价格"]`，首次 `need_clarify=true`。
- 遗留问题：
  - [备注] 商品卡数量受候选池限制；候选 >=8 时为 8 张，精确过滤后可能少于 6 张。
  - [已完成] 导购会话历史抽屉已在 M4.1 补齐，见上方记录。
  - [后续] 图片/语音、AI 加购与 `chat_actions` 留 M5；转人工队列/工作台留 M6。
  - [后续] 切换 embedding 模型需手动重跑 `seed_product_embeddings --reembed`。
- 下一模块依赖：M5 可复用 guide 会话/`slot_state`、商品卡与尺码接口，增加 image/voice content_type 与 `chat_actions` 两阶段加购；M6 复用 `support_tickets`。
- commit：m4 tag（见 `git log`）

## 2026-11-14 · M3 后续：LangGraph 客服 Agent + 开放式问题

- 状态：已完成（M3 后续优化，分支 `fix/support-size-availability`）
- 本次目标：解决“这个小孩子能带吗”被当成未知问题反问固定菜单的问题；把意图路由 + 检索 + 可回答性三段式改成 LangGraph 受控 Agent，让模型自己选择工具、读取商品事实和知识库后回答。
- 完成内容：
  - 新增 `langgraph>=1.2,<2` 依赖与 `app/modules/support/agent.py`：`StateGraph` 两个节点 `plan → tools`；`plan` 输出 `SupportPlan(action/tools/search_query/size/handoff_kind)`，`tools` 执行 `product_facts` / `search_knowledge` / `size_stock`。
  - 移除独立的意图模型和可回答性模型调用：规划模型一次完成分流与工具选择，回答模型直接基于工具结果流式生成；开放问题不再因为“意图表没有这一项”被反问。总模型调用从 3 次降到 2 次（固定尺码/转人工/闲聊路径 0~1 次）。
  - `unknown` 默认走 Agent 检索；只有规划器明确选择 `clarify` 时才澄清一次。商品事实前置层继续优先处理尺码/库存问题（0 次模型调用）。
  - 规划提示词 `support_plan.py` 覆盖材质、洗护、尺码、适用人群/儿童/年龄、送礼等开放式问法；回答提示词补充“资料未标注儿童信息时明确说明并建议转人工”。
  - 引用按问题主题收窄：材质只带 detail/faq，洗护带 care/detail/faq，政策带 policy/faq，适用人群带 detail/faq/size，避免材质回答附平台政策等无关引用。
  - 本地/Fake 规划器同步支持 `plan_support`；无 key 时“这个小孩子能带吗”返回“商品资料标注适用人群为男，没有标注儿童年龄信息，建议转人工确认”，不再输出商品编码等无关内容。
- 改动文件 / 目录：
  - `backend/app/modules/support/agent.py`、`pipeline.py`
  - `backend/app/ai/{base,local,fake,dashscope}.py`、`app/ai/prompts/{support_plan,support_answer,support_intent}.py`
  - `backend/app/modules/knowledge/retrieval.py`
  - `backend/requirements.txt`
  - `backend/tests/test_support_agent.py`、`test_support_pipeline.py`、`test_local_answers.py`、`test_size_rules.py`
  - `frontend/src/types/support.ts`、`frontend/tests/e2e/support.spec.ts`
  - `README.md`
- DB 迁移：无
- 新增环境变量：无
- 测试与验收：
  - 后端：`155 passed`（137.1s）
  - 前端：`npm run build` 成功
  - E2E：`6 passed`（41.2s，M0-M2 不回归）
  - 真实模型手工验收（qwen-plus）：
    - `这个小孩子能带吗` → “不建议小孩子穿，这款衬衫适用人群明确标注为男，尺码最小 S 码……”，引用 detail/faq/size。
    - `这件衬衫是什么材质？` → “这件衬衫是纯棉材质的，柔软透气，适合春夏季日常穿着。”，引用 faq/detail，不再附带洗护建议。
    - `有XS的吗` → “不好意思，这款没有 XS 码，可选尺码是 S、M、L、XL、XXL 码。”，引用尺码指南。
- 遗留问题：
  - [后续] LangGraph 只做了 `plan → tools` 两节点，回答生成仍在管线中流式完成；如需可视化完整 Agent 轨迹，可增加 `verify` / `answer` 节点。
  - [后续] 规划提示词依赖 qwen-plus 的 JSON 输出，异常时走 3 次结构化重试；后续可加规划结果缓存/降级策略。
  - [备注] 当前 E2E 仍用 `AI_PROVIDER=fake`，真实模型仅在手工验收中调用。
- 下一模块依赖：M4 可复用 `run_support_agent`、`SupportPlan`、工具注册方式与引用过滤；导购 Agent 可在此基础上扩展商品搜索、尺码推荐和加购工具。
- commit：待提交（分支 `fix/support-size-availability`）

## 2026-11-14 · M3 补充：尺码库存直答 + 引用表格

- 状态：已完成（M3 后续优化，分支 `fix/support-size-availability`）
- 本次目标：解决“有XS的吗”因缺少“尺码/码”字样而无法回答的问题；把尺码有无从“知识库检索问题”改为“商品库存查表问题”，并让引用弹层更直观。
- 完成内容：
  - 新增 `app/ai/size_rules.py`：识别 `XS/S/M/L/XL/XXL/XXXL`、数字尺码、均码；识别“有…吗/有没有/有货/库存/缺货”等问法；按商品库存、属性、尺码表生成“有的/没有/暂时缺货”的自然回答。
  - 客服管线新增“商品事实前置层”：在意图路由和 RAG 之前，若问题确定是尺码/库存问题，直接用当前商品的 `stock_by_size`、`attributes.size`、`size_chart` 回答，不再因为知识库没有“XS”文档而误判；回答附带尺码指南引用。
  - 检索补词：字母尺码统一映射到“尺码”，`有货 → 现货`，避免裸尺码问题召回失败；`retrieve_context` 支持复用已加载的商品事实。
  - 引用增强：SSE `citations` 增加 `content`（前 400 字）；前端引用 chip 可点击，尺码引用用表格展示尺码/身高体重/胸围腰围或脚长，其他引用显示原文。
  - 配置：`seed_knowledge.py` 新增 `--reembed`，切换真实 embedding 模型后可重建全部 1813 条知识向量；README 增加阿里云百炼 `DASHSCOPE_API_KEY`、`qwen-plus`、`text-embedding-v3` 配置与重建步骤。
- 改动文件 / 目录：
  - `backend/app/ai/size_rules.py`、`backend/app/ai/local.py`
  - `backend/app/modules/knowledge/retrieval.py`、`backend/app/modules/support/pipeline.py`
  - `backend/scripts/seed_knowledge.py`
  - `backend/tests/test_size_rules.py`、`test_local_answers.py`、`test_knowledge_retrieval.py`、`test_support_pipeline.py`、`test_knowledge_schema.py`
  - `frontend/src/types/support.ts`、`frontend/src/views/user/SupportView.vue`、`frontend/tests/e2e/support.spec.ts`
  - `README.md`
- DB 迁移：无
- 新增环境变量：无（继续使用 `AI_PROVIDER`、`DASHSCOPE_API_KEY`、`CHAT_MODEL`、`EMBEDDING_MODEL`、`EMBEDDING_DIM`）
- 测试与验收：
  - 后端：`153 passed`（152.7s）
  - 前端：`npm run build` 成功
  - E2E：`6 passed`（42.2s）；客服用例新增“有XS的吗 → 直接回答没有 XS + 尺码表引用”
  - 手工：`有XS的吗`、`有40码吗`、`有37码吗`、`有货吗`、`有优惠吗`、`订单里有XS吗` 均按预期分流；商品 140 回答“没有 XS，可选 35-39 码”并附尺码表。
- 遗留问题：
  - [已完成] 真实 `DASHSCOPE_API_KEY` 已配置；1813 条知识向量已用 `text-embedding-v3` 全量重建（写入 1813/1813），后端已切换为 `qwen-plus` 真实模型。
  - [备注] 数字尺码在字母尺码商品上默认不当作尺码（如“有40的吗”），避免把价格/身高误判；明确说“40码/40尺码”时仍会按尺码处理。
- 下一模块依赖：M4 可复用 `size_rules` 与“商品事实前置层”的组织方式；导购跨商品尺码推荐需要扩展为按商品范围批次查询。
- commit：待提交（分支 `fix/support-size-availability`）

## 2026-11-14 · M3 知识库 + RAG 商品客服

- 状态：已完成
- 本次目标：在 M0-M2 之上落地知识库、商品范围混合检索、商品客服 SSE 问答、引用/反馈与最小转人工闭环。
- 完成内容：
  - 后端：新增 `knowledge_documents` / `knowledge_chunks` / `chat_sessions` / `chat_messages` / `support_tickets` 五表与 `20261113_0004_create_knowledge_support` 迁移；`knowledge_chunks.embedding vector(1024)` 建 HNSW `vector_cosine_ops` 索引，`search_text` 建 GIN 表达式索引；`chat_actions`（M5）、`knowledge_candidates` / `product_field_history`（M7）未建。
  - 知识种子：`build_knowledge_seed.py` 从商品/品类 JSON 确定性生成 300 商品详情（每份 2 chunk）+ 300 尺码（1 chunk）+ 900 商品 FAQ（每商品 3 条）+ 4 份一级品类洗护 + 9 份平台政策，共 913 文档 / 1813 chunk；24 条品类 FAQ 草稿标 pending 写入 `category_faq_drafts.json`，不进入检索；`review.csv` 供人工审核。`seed_knowledge.py` 按 `seed_key` / 文档键幂等导入，同商品/同品类/平台分别做余弦 >0.92 去重，`--embeddings-only` 只补缺失向量；无 key 时 embedding 保持 NULL 且不中断。
  - 检索：范围固定为当前商品 + 一级品类祖先 + 平台；向量 top20（相似度 <0.35 先过滤）+ jieba 分词 `to_tsquery('simple', ...)`/`ts_rank` 关键词 top20，经 RRF（k=60）融合取 top8；同时读取商品标题、品牌、价格、属性、尺码表、库存作为事实注入。
  - 客服管线：意图路由 → 固定话术或检索 → 可回答性 → 流式回答；`product_qa` / `size_qa` / `policy_qa` 走 RAG；`order_qa` / `complaint` 固定话术 + 转人工；`chitchat` 简短引导；`unknown` 每会话最多澄清一次，第二次兜底 + 转人工。无 chunk 且 `max_similarity < 0.35` 直接不可答；`can_answer=false` 或 `confidence < 0.6` 走澄清/兜底；`partial=true` 回答已知部分并追加转人工建议。LLM 超时 20s、失败发 `error` + 固定降级话术，不挂起。
  - API：`POST/GET /api/chat/sessions`、分页消息、`POST .../messages`（SSE）、`POST .../escalate`（幂等 waiting 工单 + `waiting_human`）、`POST /api/chat/messages/{id}/feedback`；M3 仅 `type=support`，guide 返回 400；全部按 `user_id` 隔离，同用户同商品复用最近 active 会话。
  - AI 抽象：`SupportLLM` / `EmbeddingClient` 协议；`DashScopeSupportLLM` / `DashScopeEmbeddingClient`、`LocalSupportLLM` / `NoopEmbeddingClient`、`FakeSupportLLM` / `FakeEmbeddingClient`；prompts 集中在 `app/ai/prompts/`；JSON 结构化输出经 Pydantic 校验，失败重试 2 次。
  - 前端：新增 `/product/:id/support` 客服页（商品摘要、消息流、SSE 流式气泡、引用 chips、有帮助/没帮助、兜底卡片 + 转人工、等待人工 banner、输入禁用）；商品详情底部「客服」改为跳转并携带已选尺码；`utils/sse.ts` 用 fetch + ReadableStream 解析 POST SSE，不使用 EventSource。
  - E2E：新增 `start-backend.mjs` 定位 `backend/.venv` Python 并以 `AI_PROVIDER=fake` 启动 8100；Playwright `webServer` 同时拉起 fake 后端与 Vite；新增客服用例覆盖材质回答 + 引用 + 反馈、知识库外问题澄清一次、兜底、转人工等待态。
- 改动文件 / 目录：
  - `backend/app/ai/`、`backend/app/modules/knowledge/`、`backend/app/modules/support/`
  - `backend/alembic/versions/20261113_0004_create_knowledge_support.py`
  - `backend/scripts/build_knowledge_seed.py`、`seed_knowledge.py`、`backend/seeds/knowledge/`
  - `backend/app/core/config.py`、`backend/app/main.py`、`backend/app/models.py`、`backend/.env.example`、`backend/requirements.txt`
  - `backend/tests/conftest.py`、`test_knowledge_schema.py`、`test_knowledge_retrieval.py`、`test_support_api.py`、`test_support_pipeline.py`
  - `frontend/src/types/support.ts`、`api/support.ts`、`utils/sse.ts`、`views/user/SupportView.vue`
  - `frontend/src/router/index.ts`、`views/user/ProductDetailView.vue`、`tests/e2e/support.spec.ts`、`tests/e2e/start-backend.mjs`、`playwright.config.ts`
  - `README.md`、`docs/superpowers/plans/2026-11-13-m3-knowledge-rag.md`
- DB 迁移：`20261113_0004_create_knowledge_support`
- 新增环境变量（均可选）：`AI_PROVIDER`、`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`CHAT_MODEL`、`EMBEDDING_MODEL`、`EMBEDDING_DIM=1024`、`LLM_TIMEOUT_SECONDS=20`
- 测试与验收：
  - 命令：`cd backend && ./.venv/Scripts/python.exe -m pytest -q`；`cd frontend && npm run build`；`cd frontend && npm run test:e2e`
  - 结果：后端 `131 passed`（139.98s，M2 基线 104 + 新增 27）；前端构建成功（433 modules，vue-tsc 无报错）；E2E `6 passed`（42.4s，M0-M2 原 5 条不回归 + 新增客服 1 条）。
  - 手工验收（开发库 `shop`，`AI_PROVIDER=fake`，未配置真实 key）：3 个商品（纯棉衬衫 / 网面运动鞋 / 帆布双肩包）分别询问材质、尺码、洗护，均返回 `can_answer=true`，引用覆盖 detail/faq/size/care；平台退货政策返回 policy 引用；知识库外问题第一次澄清、第二次兜底并 `handoff_required=true`；未发现知识库外编造内容。
- 遗留问题：
  - [后续] 未配置真实 `DASHSCOPE_API_KEY`，DashScope 意图/可答性/流式回答与 embedding 仅通过单元 fake 验证，尚未做真实模型质量与延迟验收。
  - [后续] 本地模式回答为检索片段拼接（抽取式），可演示但自然度有限；真实 key 下的生成质量待 M8 评测。
  - [后续] 品类 FAQ 24 条仍为 pending 草稿，需 M7 知识审核闭环处理。
  - [后续] M3 仅文本消息；图片/语音、AI 加购留 M5。
  - [后续] 转人工只创建 waiting 工单并展示等待条，队列/客服接入/工作台/WebSocket/会话总结留 M6。
  - [后续] SSE 无断线重连/事件 ID 续传；前端刷新后依靠消息分页恢复。
  - [后续] `products.embedding` 仍为 NULL，商品本身向量召回留 M4。
  - [备注] E2E 通过 fake 后端验证链路，不访问真实 DashScope；知识种子已在开发库导入 913 文档 / 1813 chunk / 1813 向量（fake embedding）。
- 下一模块依赖：M4 可直接复用 `app/ai/` 的 LLM/Embedding 抽象、`knowledge_chunks` 检索与商品/品类种子；导购会话复用 `chat_sessions.type=guide` 时需放开 M3 的 400 限制并新增槽位/澄清策略；商品向量生成可复用 `FakeEmbeddingClient` / DashScope embedding 客户端。
- commit：M3 分支 `m3-knowledge-rag`，tag `m3`（见 `git log`）

## 2026-11-13 · M2 交易域（购物车 / 地址 / 订单 / 模拟支付发货收货）

- 状态：已完成
- 本次目标：在 M1 商品域之上打通「加购 → 购物车 → 结算 → 下单 → 支付 → 客服发货 → 确认收货」闭环。
- 完成内容：
  - 后端：新增 `addresses` / `cart_items` / `orders` / `order_items` 四表与 `20261113_0003_create_commerce` 迁移；购物车 CRUD（同 SKU 累加、超库存 409、勾选/数量/删除）；地址 CRUD（首个地址自动默认、默认唯一、删除默认后自动补选、跨用户 403）；下单事务内 `SELECT FOR UPDATE OF product_skus` 锁 SKU、校验库存、扣减、写地址/商品快照、删除已结算购物车项；订单列表/详情/支付/取消/确认收货；客服端 `/api/agent/orders` 已支付列表与模拟发货，`/api/agent/*` 要求 `role ∈ {agent, admin}`。
  - 规则：金额内部 Decimal、DTO float；支付幂等且首次支付才累加 `products.sales_count`；取消/超时恢复库存且只恢复一次；`expires_at` 15 分钟，列表/详情/支付惰性扫描 + lifespan 内每分钟兜底扫描；支付/取消/发货/收货状态机 409；中文错误提示。
  - 种子：`seed_demo_user.py` 同时创建 demo/demo123 与客服 agent/agent123（role=agent），重复执行幂等、密码/角色错误时修复。
  - 前端：`/cart`、`/checkout`、`/orders`、`/orders/:id`、`/addresses`、`/agent/orders`；商品详情加购与立即购买真实调用；首页/分类/详情购物车角标；我的页订单/地址入口与四个订单状态快捷入口；客服端桌面订单表格与角色守卫；客服登录默认跳 `/agent/orders`。
  - 测试：后端新增 34 项（schema、购物车、地址越权、订单快照/库存回滚、支付幂等、取消/超时恢复、发货/收货状态机、客服角色守卫、库存 1 并发下单只成功一单）；前端 build 通过；Playwright 新增 2 条（完整交易链路、普通用户访问客服端被带回首页），M0/M1 E2E 不回归。
- 改动文件 / 目录：
  - `backend/app/modules/commerce/`、`backend/app/modules/auth/deps.py`、`backend/app/models.py`、`backend/app/main.py`
  - `backend/alembic/versions/20261113_0003_create_commerce.py`
  - `backend/scripts/seed_demo_user.py`
  - `backend/tests/conftest.py`、`backend/tests/test_commerce_schema.py`、`test_cart_api.py`、`test_address_api.py`、`test_order_api.py`
  - `frontend/src/types/commerce.ts`、`frontend/src/api/commerce.ts`、`frontend/src/stores/cart.ts`、`frontend/src/utils/commerce.ts`
  - `frontend/src/components/commerce/`、`frontend/src/views/user/{Cart,Checkout,Orders,OrderDetail,Addresses}View.vue`、`frontend/src/views/agent/AgentOrdersView.vue`
  - `frontend/src/router/index.ts`、`frontend/src/main.ts`、`frontend/src/views/user/{Home,Category,ProductDetail,Me,Login}View.vue`
  - `frontend/tests/e2e/commerce.spec.ts`
  - `README.md`、`docs/superpowers/plans/2026-11-13-m2-commerce.md`
- DB 迁移：`20261113_0003_create_commerce`
- 新增环境变量：无
- 测试与验收：
  - 命令：`cd backend && source .venv/Scripts/activate && python -m pytest -q`；`cd frontend && npm run build`；`cd frontend && npm run test:e2e`
  - 结果：后端 `104 passed`（M0/M1 原 70 项 + 新增 34 项，79.5s）；前端构建成功（vue-tsc 无报错，Vite 428 modules）；E2E `5 passed`（31.1s，含完整交易链路）。
- 遗留问题：
  - [后续] 支付/发货为模拟，未实现真实支付、退款、售后、物流、发票。
  - [后续] 超时扫描固定 60 秒、每次最多 100 单，未做成可配置；演示环境够用。
  - [后续] 购物车无批量勾选接口，前端全选逐条 PATCH；商品数量大时需优化。
  - [后续] 客服端目前仅订单发货；队列/会话工作台留 M6。
  - [备注] E2E 会累积历史订单记录；用例按订单号定位，不影响断言。
  - [备注] `scripts/seed_demo_user.py` 名称未改，但现在同时创建客服账号，README 已注明。
- 下一模块依赖：M3 知识库 + RAG 商品客服；可直接复用商品/SKU 种子、订单与用户数据、Axios/Pinia 结构；M3 不改交易域契约。
- commit：M2 分支 `m2-commerce`，tag `m2`（见 `git log`）

## 2026-11-13 · M1 商品域 + 种子数据 + 商品详情

- 状态：已完成
- 本次目标：建商品域四表与可重复种子，打通品类树、商品列表/详情、收藏和商品详情页；AI 找货 Tab 提供可复用商品发现入口。
- 完成内容：
  - 后端：`categories` / `products` / `product_skus` / `favorites` 四表与 Alembic 迁移；`products.product_code` 唯一；`embedding vector(1024)` 建列但保持 NULL；品类树（父级 + 叶子合并 `attribute_schema`）；商品列表（`category_id` / `q` / `page` / `page_size` / `sort`，一级品类包含子类）；商品详情（SKU、尺码表、属性、`is_favorited`）；收藏列表与幂等增删；`/static` 商品图挂载；可选登录依赖 `get_current_user_optional`。
  - 种子：4 个一级 + 34 个叶子品类；300 个商品；实际 1108 条 SKU（服装 375、鞋靴 375、箱包 209、配饰 149）；300 张已有商品图；`build_catalog_seed.py`（CSV→JSON，价格/销量/库存一次性生成，默认不覆盖 JSON）与 `seed_catalog.py`（JSON→DB upsert，重复执行不重复、不丢收藏）分离；每商品一图一色，单尺码商品用“均码”。
  - 前端：AI 找货 Tab 嵌入可复用 `ProductDiscoveryPanel`（4 个品类入口 + 热门商品）；`/category/:id` 分类列表（搜索、排序、分页）；`/product/:id` 详情（颜色、尺码、SKU 库存、尺码表弹层、属性、设计细节 tags、收藏）；`/favorites` 收藏页；Me 页“我的收藏”入口；加购/立即购买/客服为 toast 占位。
  - 测试：后端 pytest 新增 22 项（schema、DTO 合并、API、seed/build、幂等与图片校验）；前端 build 通过；Playwright 新增“列表→详情→收藏→我的收藏→取消收藏”用例，M0 认证 E2E 不回归。
- 改动文件 / 目录：
  - `backend/app/modules/catalog/`、`backend/app/models.py`、`backend/app/main.py`、`backend/app/modules/auth/deps.py`
  - `backend/alembic/versions/20261113_0002_create_catalog.py`
  - `backend/seeds/catalog/`、`backend/scripts/build_catalog_seed.py`、`backend/scripts/seed_catalog.py`
  - `backend/tests/test_catalog_*.py`、`backend/tests/unit/test_catalog_*.py`、`backend/tests/conftest.py`、`backend/requirements.txt`
  - `frontend/src/types/catalog.ts`、`frontend/src/api/catalog.ts`、`frontend/src/stores/catalog.ts`、`frontend/src/stores/favorites.ts`、`frontend/src/utils/format.ts`、`frontend/src/utils/colors.ts`
  - `frontend/src/components/catalog/`、`frontend/src/views/user/HomeView.vue`、`CategoryView.vue`、`ProductDetailView.vue`、`FavoritesView.vue`、`MeView.vue`
  - `frontend/src/router/index.ts`、`frontend/src/main.ts`、`frontend/vite.config.ts`、`frontend/playwright.config.ts`、`frontend/tests/e2e/catalog.spec.ts`
  - `README.md`、设计文档 §7.2.2 / §8.1 / §8.2 / §10.2、`docs/superpowers/plans/2026-11-13-m1-product-catalog.md`
- DB 迁移：`20261113_0002_create_catalog`
- 新增环境变量：无
- 测试与验收：
  - 命令：`cd backend && source .venv/Scripts/activate && python -m pytest -v`；`cd frontend && npm run build`；`cd frontend && npm run test:e2e`
  - 结果：后端 `70 passed`（45.52s）；前端构建成功（vue-tsc 无报错）；E2E `3 passed`（13.2s）；手工/接口抽查覆盖分类树合并 schema、父品类含子类、三种排序、详情公开 + 登录 `is_favorited`、收藏幂等、`/static` 图片、重复 seed 后收藏保留。
- 种子实际数量：商品 300、SKU 1108（服装 375、鞋靴 375、箱包 209、配饰 149）、图片 300。
- 遗留问题：
  - [后续] 商品搜索为 `ILIKE` 子串匹配，未接分词/向量检索；M4 再接混合检索。
  - [后续] `products.embedding` 已建列但保持 NULL，M3/M4 再生成向量。
  - [后续] 商品详情“好评率”、购物车、立即购买、客服为占位；M2/M3/M6 接入。
  - [后续] 尺码推荐卡片按计划留到 M4；M1 只提供尺码表与尺码选择。
  - [后续] `backend/static/products` 仍未单独备份；商品图不进 git。
  - [后续] 商品列表筛选目前只做品类/关键词/排序，叶子属性筛选（颜色、材质等）待 M4 对话找货或后续补 UI。
  - [备注] Playwright 因 demo 账号共享状态固定 `workers: 1`；新增测试文件不要依赖并行隔离。
- 下一模块依赖：M2 可直接复用 `products` / `product_skus`、`favorites` 用户态、Axios 客户端与详情页底部占位按钮；购物车落 SKU 时使用 `product_skus.id` 与库存，需新增库存扣减/恢复与订单状态机。
- commit：M1 分支 `m1-product-catalog`（见 `git log`）

## 2026-11-13 · M0 项目骨架

- 状态：已完成
- 本次目标：搭好前后端骨架，打通登录链路，登录后显示「AI 找货 / 我的」两个 Tab。
- 完成内容：
  - 后端：FastAPI + PostgreSQL + Alembic；users 表；注册、登录、当前用户接口；健康检查；演示账号种子脚本；422 校验失败脱敏。
  - 前端：Vue 3 + Vite + TypeScript + Vant 4；登录/注册页；双 Tab 布局；鉴权路由守卫；Axios 自动带 token 与 401 退出；会话过期事件处理。
  - 测试：pytest 48 项（14 安全 + 29 认证/API + 1 迁移 + 1 健康 + 3 种子）；Playwright 2 项（登录后双 Tab 流程、未登录深链接回跳）。
  - 工程：git 初始化；`.gitignore` 排除商品图与 node_modules；Docker 开发数据库；README；本地开发端口适配为 8100；文档：设计文档 §13.3 环境变量名与实现对齐（JWT_SECRET_KEY）。
- 改动文件 / 目录：
  - `backend/app/`、`backend/alembic/`、`backend/scripts/`、`backend/tests/`
  - `frontend/src/`、`frontend/tests/e2e/`、`frontend/playwright.config.ts`、`frontend/vite.config.ts`
  - `deploy/docker-compose.dev.yml`、`deploy/initdb/`
  - `.gitignore`、`README.md`、`docs/`
- DB 迁移：`20261113_0001_create_users`
- 新增环境变量：`DATABASE_URL`、`TEST_DATABASE_URL`、`JWT_SECRET_KEY`、`JWT_ALGORITHM`、`JWT_EXPIRE_MINUTES`、`CORS_ORIGINS`
- 测试与验收：
  - 命令：`cd backend && source .venv/Scripts/activate && python -m pytest -v`；`cd frontend && npm run build`；`cd frontend && npm run test:e2e`
  - 结果：后端 `48 passed`（16.91s）；前端构建成功（vue-tsc 无报错，Vite 378 modules，2.40s）；E2E `2 passed`（5.5s，含用户资料卡断言）；手工验收 6 步通过（真实浏览器 Playwright 抽查：未登录重定向、demo 登录、双 Tab、我的页资料与退出、退出回登录、刷新仍在登录页）。
- 遗留问题：
  - [后续] 登录态为 localStorage JWT，无 refresh token；改密码/找回密码/OAuth/限流均未实现。
  - [后续] `PATCH /api/users/me` 个人资料编辑未实现。
  - [后续] 统一业务错误码、SSE/WebSocket 契约留到后续模块。
  - [M1 前] `backend/static/products` 本地备份仍未执行。
  - [后续] Vant 全量引入导致首屏包偏大（JS 主包约 143.40 kB gzip、CSS 约 53.49 kB gzip），后续按需引入优化。
  - [后续] 部分设计 token 组合对比度偏低（WCAG）；登录/注册页存在重复 CSS；favicon 404、iOS 输入聚焦缩放未处理。
  - [后续] 网络异常且保留 token 时，首页问候语/我的页姓名为空，后续补加载/失败态。
  - [备注] Playwright 固定 1.64.1 以匹配本机 chromium-1248；换机后需 `npx playwright install chromium`。
  - [低] README 的 `.env` 脚本对带引号空值 `JWT_SECRET_KEY=""` 会误判为已配置（边缘情况）。
- 下一模块依赖：M1 可直接复用 users 表、`get_current_user` 依赖、Axios 客户端、Pinia 认证 store、双 Tab 布局；后端本地端口 8100，前端代理已指向该端口。
- commit：`m0` tag（M0 提交范围 `190bdb5..m0`；实现提交见 `git log`）

## 记录模板（复制用）

```markdown
## YYYY-MM-DD · Mx 模块名

- 状态：已完成 / 进行中 / 阻塞
- 本次目标：
- 完成内容：
- 改动文件 / 目录：
- DB 迁移：
- 新增环境变量：
- 测试与验收：
  - 命令：
  - 结果：
- 遗留问题：
- 下一模块依赖：
- commit：
```

## 维护约定

1. 每个模块 / 窗口结束前必须更新一次，并提交 git。
2. 只写“做了什么、怎么验证、还差什么”，不要复制设计文档的大段内容。
3. 如果改动涉及 API DTO、错误码、DB 字段或路由，先更新设计文档，再在记录里注明“契约已变更”。
4. 下一个窗口开场读：`docs/implementation-handoff.md` + 本文件 + 设计文档相关章节。
