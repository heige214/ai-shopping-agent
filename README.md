# AI 购物导购 Agent 平台

本科毕业设计项目：移动端优先的 AI 购物导购平台，规划包含对话式找货、商品客服、转人工与知识回灌闭环。

- 设计文档：[docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md](docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md)
- 实施交接：[docs/implementation-handoff.md](docs/implementation-handoff.md)
- 项目进度：[docs/progress.md](docs/progress.md)

## 当前进度

- M0 项目骨架：登录 / 注册、双 Tab 空壳、PostgreSQL + Alembic、pytest、Playwright。
- M1 商品域：4 个一级 + 34 个叶子品类、300 个商品、1108 条 SKU、收藏、分类列表、商品详情与可复用商品发现组件。
- M2 交易域：购物车、收货地址、订单、模拟支付、客服发货、确认收货；商品详情加购/立即购买已接通，客服端提供已支付订单发货页。
- M3 知识库 + RAG 商品客服：913 篇知识文档 / 1813 个切片，商品 + 一级品类 + 平台三级范围混合检索；LangGraph 受控 Agent（`plan → tools`）按问题选择商品事实、知识检索、尺码库存工具；商品客服页支持 SSE 流式回答、可点击引用/尺码表、反馈、澄清一次与最小转人工（等待工单）。无 DashScope key 时自动降级为本地规则 + 关键词检索。
- M4 AI 导购：首页改为导购聊天（空状态 + 示例问法 + 品类入口 + 热门商品 + 历史会话抽屉），支持品类/颜色/材质/厚薄/价格/身高体重的自然语言找货与多轮条件合并；结构化过滤 + 商品向量 top30 → RRF → LLM 重排 6~8 张商品卡；无结果按厚薄→材质→价格放宽或澄清一次；商品卡与详情页按用户档案和尺码表给出推荐尺码。

## 环境要求

- Python 3.12
- Node.js 20+
- Docker Desktop
- Git（Windows 下使用 Git Bash）

## 本地启动

以下命令在 Windows Git Bash 中执行，并默认从仓库根目录开始；启动后端和前端时请各开一个终端。macOS/Linux 请将 `.venv/Scripts/activate` 换成 `.venv/bin/activate`。

### 1. 启动数据库

```bash
cd deploy
docker compose -f docker-compose.dev.yml up -d
```

首次启动会创建 `shop`（开发库）和 `shop_test`（测试库）。宿主机端口使用 **5433**，避免与本机 PostgreSQL 的 5432 冲突。

### 2. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements-dev.txt
cp -n .env.example .env
python - <<'PY'
import re
import secrets
from pathlib import Path

path = Path(".env")
text = path.read_text(encoding="utf-8")
if re.search(r"(?m)^JWT_SECRET_KEY=[^\s#]+", text):
    print("JWT_SECRET_KEY 已配置，跳过")
else:
    new_text, count = re.subn(
        r"(?m)^JWT_SECRET_KEY=[ \t]*$",
        f"JWT_SECRET_KEY={secrets.token_urlsafe(48)}",
        text,
        count=1,
    )
    if count == 0:
        raise SystemExit("未找到可填充的 JWT_SECRET_KEY 行，请检查 .env 或删除后重试")
    path.write_text(new_text, encoding="utf-8")
    print("JWT_SECRET_KEY 已写入 .env")
PY
python -m alembic upgrade head
python -m scripts.seed_demo_user   # 同时创建 demo/demo123 与 agent/agent123
python -m scripts.seed_catalog
python -m scripts.seed_knowledge   # 商品/品类/平台知识；无 key 时只入库不生成向量
python -m scripts.seed_product_embeddings   # 商品级向量；无 key 时保持 NULL
uvicorn app.main:app --reload --port 8100
```

AI 配置为可选项：不配置 `DASHSCOPE_API_KEY` 时，客服使用 `LocalSupportLLM`（规则意图 + 片段拼接回答）和关键词检索，仍可完整演示；配置 key 后自动使用 `qwen-plus` + `text-embedding-v3`。如需强制本地/测试模式，可设置 `AI_PROVIDER=local` 或 `AI_PROVIDER=fake`。变量说明见 `backend/.env.example`。

#### 配置阿里云百炼（可选）

1. 在阿里云百炼控制台创建 API Key。
2. 写入 `backend/.env`（该文件已被 gitignore）：

```bash
AI_PROVIDER=auto
DASHSCOPE_API_KEY=sk-你的Key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
CHAT_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024
```

3. 切换 embedding 模型后必须同时重建知识向量与商品向量，否则新旧向量不可比：

```bash
cd backend
source .venv/Scripts/activate
python -m scripts.seed_knowledge --reembed
python -m scripts.seed_product_embeddings --reembed
```

4. 重启后端使其读取新环境变量。

健康检查：<http://localhost:8100/api/health>

说明：本项目本地开发后端统一使用 **8100**（本机 Windows 保留了 7997–8096 端口段，8000 不可用），前端 Vite 固定使用 **5175**（避开本机其他项目常占用的 5173/5174），`/api` 代理已指向 8100。如需改用其他端口，请同步调整 `uvicorn` 启动端口与 `frontend/vite.config.ts` 的代理目标；若修改前端端口，还需同步 `frontend/vite.config.ts` 的 `server.port`、`backend/.env` 的 `CORS_ORIGINS`，以及 `frontend/playwright.config.ts` 的 `baseURL` 与 `webServer.url`。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5175>，使用演示账号 **demo / demo123** 登录。登录后进入「AI 找货」Tab，可在底部切换到「我的」。

客服账号 **agent / agent123**（role=agent）登录后默认进入桌面端客服工作台 `/agent/orders`，可查看已支付订单并模拟发货。

演示资料：昵称「小鹿」、172cm、75kg、常穿 M 码（E2E 依赖）。

## 测试

以下测试命令请新开终端，并从仓库根目录开始执行。

macOS/Linux 请将 `.venv/Scripts/activate` 换成 `.venv/bin/activate`。

后端（需要 PostgreSQL 测试库已启动，本项目使用 Docker 的 `shop_test`）：

```bash
cd backend
source .venv/Scripts/activate
python -m pytest
```

商品种子（`backend/seeds/catalog/products.json`）已提交；日常启动或重置数据库后直接导入：

```bash
cd backend
source .venv/Scripts/activate
python -m scripts.seed_catalog
```

只有 CSV 或品类 schema 变更、且确认要重建时才运行：

```bash
python -m scripts.build_catalog_seed --force
```

`build` 默认拒绝覆盖已有 JSON；`seed` 按 `product_code` / `sku_code` upsert，重复执行不会重复插入，也不会丢收藏。

知识种子（`backend/seeds/knowledge/knowledge.json`）同样已提交，按 `seed_key` 幂等导入；无 key 时 embedding 为 NULL，可用 `--embeddings-only` 在配置 key 后补齐：

```bash
cd backend
source .venv/Scripts/activate
python -m scripts.seed_knowledge
python -m scripts.seed_knowledge --embeddings-only   # 仅补缺失向量
```

商品向量（`products.embedding`）用于 M4 导购的语义召回；脚本默认只补 NULL，重复执行幂等，无 key 时不写入：

```bash
cd backend
source .venv/Scripts/activate
python -m scripts.seed_product_embeddings
python -m scripts.seed_product_embeddings --reembed   # 切换 embedding 模型后全量重建
```

前端 E2E（先确保数据库已迁移，演示/客服账号、商品与知识种子已创建）：

```bash
cd frontend
npx playwright install chromium   # 首次
npm run test:e2e
```

E2E 会自行启动 Vite 与后端（`tests/e2e/start-backend.mjs` 使用 `AI_PROVIDER=fake`，不访问真实 DashScope）；请先停止前端 dev server 与 8100 上的后端，确保 5175 / 8100 端口空闲。测试完成后两个服务自动关闭。

## 停止与重置

停止后端 / 前端：在对应终端按 `Ctrl+C`。

停止数据库：

```bash
cd deploy
docker compose -f docker-compose.dev.yml down
```

重置开发数据库（会删除 Docker 的 pgdata 卷中的本地数据，不影响 `.env` 与 `backend/static/products/`）：

```bash
cd deploy
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d --wait
cd ../backend
source .venv/Scripts/activate   # macOS/Linux 用 .venv/bin/activate
python -m alembic upgrade head
python -m scripts.seed_demo_user   # demo/demo123 + agent/agent123
python -m scripts.seed_catalog
python -m scripts.seed_knowledge
```

## 主要目录

```text
backend/
├── app/
│   ├── ai/               # SupportLLM / EmbeddingClient 抽象、DashScope、本地规则、Fake、prompts
│   ├── core/             # 配置、安全
│   ├── db/               # engine、Base、session
│   ├── modules/auth/     # 用户、注册、登录
│   ├── modules/catalog/  # 品类、商品、SKU、收藏
│   ├── modules/commerce/ # 购物车、地址、订单、模拟支付/发货
│   ├── modules/knowledge/# 知识文档/切片、混合检索、种子导入
│   ├── modules/guide/    # 导购槽位/商品混合召回/SSE 管线/尺码推荐
│   ├── modules/support/  # 客服会话/消息/SSE 管线/反馈/转人工工单
│   ├── main.py
│   └── models.py
├── alembic/              # 数据库迁移
├── seeds/catalog/        # 品类与商品种子 JSON（商品 JSON 由 CSV 生成）
├── seeds/knowledge/      # 知识种子 JSON、待审草稿、审核 CSV
├── scripts/              # 种子脚本（演示账号 + 客服账号 + 商品 + 知识）
├── static/products/      # 300 张商品图（gitignored）
└── tests/                # pytest

frontend/
├── src/
│   ├── api/              # Axios 客户端与接口封装
│   ├── components/catalog/ # 商品图、商品卡、商品发现面板
│   ├── components/commerce/ # 购物车角标、地址表单
│   ├── components/guide/  # 导购空状态、带推荐尺码的商品卡
│   ├── layouts/          # 双 Tab 布局
│   ├── router/           # 路由与鉴权/角色守卫
│   ├── stores/           # Pinia 状态（认证、收藏、购物车）
│   ├── styles/           # 设计变量与全局样式
│   ├── types/            # TypeScript 类型
│   ├── utils/            # token、错误提示、格式化、颜色、订单状态
│   ├── views/user/       # 登录、注册、找货、分类、详情、客服、收藏、购物车、结算、订单、地址、我的
│   └── views/agent/      # 客服端订单发货
├── tests/e2e/            # Playwright 端到端测试（含 fake 后端启动脚本）
├── playwright.config.ts
└── vite.config.ts

deploy/                   # 开发数据库 Docker Compose
```

## 说明

- `backend/static/products/` 约 342MB，已在 `.gitignore` 中排除，需单独备份；M1 商品图通过后端 `/static` 挂载、Vite `/static` 代理访问。
- 演示账号 `demo / demo123` 与客服账号 `agent / agent123` 仅用于本地演示，生产环境必须更换密码；客服端接口 `/api/agent/*` 要求 `role ∈ {agent, admin}`。
- M3 知识库：`build_knowledge_seed.py` 由商品/品类 JSON 确定性生成 300 商品详情 + 300 尺码 + 900 商品 FAQ + 4 一级品类洗护 + 9 平台政策，共 913 文档 / 1813 切片；24 条品类 FAQ 草稿标 pending，留在 `category_faq_drafts.json`，不进入检索。审核清单见 `review.csv`。
- M3 检索：向量 top20 + jieba/tsvector 关键词 top20 → RRF 融合取 top8；范围固定为当前商品、其一级品类、平台，不跨商品/跨一级品类。无 embedding 时自动退化为关键词检索。
- M3 客服：`/product/:id/support` 使用 fetch + ReadableStream 解析 POST SSE；会话按 `user_id` 隔离，同商品复用最近 active 会话。M3 仅文本与最小转人工，队列/客服工作台/WebSocket/会话总结留 M6。
- M3 Agent：`backend/app/modules/support/agent.py` 使用 `langgraph` 的 `StateGraph` 执行 `plan → tools`；规划模型选择 `product_facts` / `search_knowledge` / `size_stock`，尺码库存问题优先走确定性事实层，引用按问题主题过滤。独立意图和可回答性模型调用已移除。
- M4 导购：首页 `/` 为导购聊天；`POST /api/chat/sessions` 的 `type=guide` 默认复用最近 active 会话，`new=true` 显式新建，guide 不写问候消息，escalate 返回 400。SSE 顺序固定为 `meta → token* → products → done`。
- M4 历史：首页顶部「历史」抽屉列出 `type=guide` 会话（标题/时间/进行中或已结束），点击切换并恢复消息与商品卡；抽屉内可显式新建会话。
- M4 检索：结构化（品类子树 + 颜色/材质/厚薄 + 价格 + on_sale）+ `products.embedding` 余弦 top30 → RRF → LLM 重排 top8；无结果按厚薄→材质→价格放宽，仍无结果澄清一次。颜色与品类不放宽。
- M4 尺码：新增 `GET /api/products/{id}/size-recommendation`，按用户身高体重与商品尺码表返回推荐尺码；导购商品卡与商品详情卡展示 `recommended_size/size_reason`，不改 M1 商品 DTO。
- 商品向量：`seed_product_embeddings.py` 默认只补 NULL，`--reembed` 全量重建；无 key 时保持 NULL，导购检索退化为结构化召回。M4 不做图片/语音、AI 加购与 `chat_actions`（留 M5）。
- 当前登录态为 7 天 JWT，存 localStorage（仅为简化实现，生产应改用 HttpOnly Cookie）；refresh token 留到后续安全增强。
- 启动命令、端口、演示账号或 `.env` 配置变更时，请同步更新本 README；以代码和 `.env.example` 为准。
