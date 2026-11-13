# AI 购物导购 Agent 平台

本科毕业设计项目：移动端优先的 AI 购物导购平台，包含对话式找货、商品客服、转人工与知识回灌闭环。

- 设计文档：`docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md`
- 实施交接：`docs/implementation-handoff.md`
- 项目进度：`docs/progress.md`

## 当前进度

M0 项目骨架：登录 / 注册、双 Tab 空壳、PostgreSQL + Alembic、pytest、Playwright。

## 环境要求

- Python 3.12
- Node.js 20+
- Docker Desktop
- Git

## 本地启动

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
cp .env.example .env
python - <<'PY'
import secrets
from pathlib import Path

path = Path(".env")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "JWT_SECRET_KEY=\n",
    f"JWT_SECRET_KEY={secrets.token_urlsafe(48)}\n",
    1,
)
path.write_text(text, encoding="utf-8")
print("JWT_SECRET_KEY 已写入 .env")
PY
python -m alembic upgrade head
python -m scripts.seed_demo_user
uvicorn app.main:app --reload --port 8100
```

健康检查：<http://localhost:8100/api/health>

说明：本机 Windows 保留了 7997–8096 端口段，后端无法绑定 8000，因此本地开发使用 **8100**；前端 Vite 的 `/api` 代理已指向该端口。若在其他机器上 8000 可用，可自行调整启动命令与 `frontend/vite.config.ts`。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>，使用演示账号 **demo / demo123** 登录。登录后进入「AI 找货」Tab，可在底部切换到「我的」。

## 测试

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

E2E 会自行启动 Vite（需要 5173 端口空闲），测试完成后自动关闭。后端需保持运行。

## 目录结构

```text
backend/app/
├── core/          # 配置、安全
├── db/            # engine、Base、session
├── modules/auth/  # 用户、注册、登录
├── main.py
└── models.py

frontend/src/
├── api/           # Axios 客户端与接口封装
├── layouts/       # 双 Tab 布局
├── router/        # 路由与鉴权守卫
├── stores/        # Pinia 状态
├── styles/        # 设计变量与全局样式
├── types/         # TypeScript 类型
├── utils/         # token、错误提示
└── views/user/    # 登录、注册、AI 找货、我的

frontend/tests/e2e/  # Playwright 端到端测试
deploy/              # 开发数据库 Docker Compose
```

## 说明

- `backend/static/products/` 约 342MB，已在 `.gitignore` 中排除，需单独备份。
- 当前登录态为 7 天 JWT，存 localStorage；refresh token 留到后续安全增强。
