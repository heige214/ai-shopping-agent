# AI 购物导购 Agent 平台

本科毕业设计项目：移动端优先的 AI 购物导购平台，规划包含对话式找货、商品客服、转人工与知识回灌闭环。

- 设计文档：[docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md](docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md)
- 实施交接：[docs/implementation-handoff.md](docs/implementation-handoff.md)
- 项目进度：[docs/progress.md](docs/progress.md)

## 当前进度

M0 项目骨架：登录 / 注册、双 Tab 空壳、PostgreSQL + Alembic、pytest、Playwright。

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
python -m scripts.seed_demo_user
uvicorn app.main:app --reload --port 8100
```

健康检查：<http://localhost:8100/api/health>

说明：本项目本地开发统一使用 **8100**（本机 Windows 保留了 7997–8096 端口段，8000 不可用），前端 Vite 的 `/api` 代理已指向该端口。如需改用其他端口，请同步调整 `uvicorn` 启动端口与 `frontend/vite.config.ts` 的代理目标；若修改前端端口，还需同步 `frontend/vite.config.ts` 的 `server.port`、`backend/.env` 的 `CORS_ORIGINS`，以及 `frontend/playwright.config.ts` 的 `baseURL` 与 `webServer.url`。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>，使用演示账号 **demo / demo123** 登录。登录后进入「AI 找货」Tab，可在底部切换到「我的」。

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

前端 E2E（先确保数据库已迁移、演示账号已创建、后端已在 8100 端口运行）：

```bash
cd frontend
npx playwright install chromium   # 首次
npm run test:e2e
```

E2E 会自行启动 Vite，请先停止前端 dev server 并确保 5173 端口空闲；测试完成后 Vite 自动关闭。后端需保持运行。

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
python -m scripts.seed_demo_user
```

## 主要目录

```text
backend/
├── app/
│   ├── core/          # 配置、安全
│   ├── db/            # engine、Base、session
│   ├── modules/auth/  # 用户、注册、登录
│   ├── main.py
│   └── models.py
├── alembic/           # 数据库迁移
├── scripts/           # 种子脚本
└── tests/             # pytest

frontend/
├── src/
│   ├── api/           # Axios 客户端与接口封装
│   ├── layouts/       # 双 Tab 布局
│   ├── router/        # 路由与鉴权守卫
│   ├── stores/        # Pinia 状态
│   ├── styles/        # 设计变量与全局样式
│   ├── types/         # TypeScript 类型
│   ├── utils/         # token、错误提示
│   └── views/user/    # 登录、注册、AI 找货、我的
├── tests/e2e/         # Playwright 端到端测试
├── playwright.config.ts
└── vite.config.ts

deploy/                # 开发数据库 Docker Compose
```

## 说明

- `backend/static/products/` 约 342MB，已在 `.gitignore` 中排除，需单独备份；M0 运行不依赖商品图，后续商品模块再使用。
- 演示账号 `demo / demo123` 仅用于本地演示，生产环境必须更换密码。
- 当前登录态为 7 天 JWT，存 localStorage（仅为简化实现，生产应改用 HttpOnly Cookie）；refresh token 留到后续安全增强。
- 启动命令、端口、演示账号或 `.env` 配置变更时，请同步更新本 README；以代码和 `.env.example` 为准。
