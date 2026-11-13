# M0 项目骨架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭好前后端项目骨架，打通「注册 → 登录 → 进入双 Tab 空壳」链路，并建立数据库迁移、测试与 Docker 开发库基线。

**Architecture:** 后端采用 FastAPI 单体 + 模块分包，M0 只实现 `auth` 模块（users 表、注册、登录、当前用户），其余业务表随 M1~M7 各自迁移。前端采用 Vue 3 + Vite + TypeScript + Vant 4，登录态为 7 天有效期的 JWT，存 localStorage，通过 Axios 拦截器自动携带；登录后进入 `/`（AI 找货）与 `/me`（我的）两个 Tab 空壳。

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + asyncpg + PostgreSQL 16/pgvector + PyJWT + bcrypt；Vue 3 + Vite 6 + TypeScript + Pinia + Vue Router + Vant 4 + Axios；pytest + httpx + Playwright；Docker Compose（仅开发数据库）。

---

## 0. 范围与验收

**M0 完成标志（用户确认）：**

- 能用演示账号 `demo / demo123` 登录。
- 登录后看到「AI 找货 / 我的」两个 Tab 的空壳，可切换。
- 能连上 PostgreSQL，迁移可执行。

**M0 包含：**

- Git 初始化、`.gitignore`（排除 300 张商品图与 `node_modules`）。
- Docker 开发数据库（PostgreSQL 16 + pgvector，宿主机端口 5433）。
- `users` 表 + Alembic 基线迁移。
- `POST /api/auth/register`、`POST /api/auth/login`、`GET /api/auth/me`、`GET /api/health`。
- 演示账号种子脚本。
- 前端只做 4 个页面：登录页、注册页、AI 找货空壳、我的空壳。
- 双 Tab 布局、路由守卫、JWT 存储与 Axios 拦截器。
- 后端 pytest 测试、前端 Playwright 登录 E2E、README。

**M0 页面清单（严格只做这 4 个）：**

| 路由 | 页面 | M0 内容 |
|---|---|---|
| `/login` | 登录页 | Logo、标题、副标题、用户名/密码、登录按钮、注册入口、演示账号提示 |
| `/register` | 注册页 | 用户名、昵称（可选）、密码、确认密码、注册并登录、返回登录 |
| `/` | AI 找货空壳 | 顶部品牌栏 + 一句问候 + 「AI 导购将在 M4 上线」占位卡 |
| `/me` | 我的空壳 | 顶部标题 + 用户卡片 + 退出登录 + 后续功能占位文案 |

**M0 不包含（后续模块实现）：**

- refresh token、改密码、找回密码、邮箱、OAuth、登录限流。
- `PATCH /api/users/me` 个人资料编辑。
- 商品列表/详情、AI 客服、购物车、结算、订单、地址、收藏、会话列表、客服端 `/agent` 的队列/工作台/知识审核页面。
- 12 个用户端页面中的其余 8 个，以及 3 个客服端页面，全部留到 M1~M7。
- Nginx 与全栈 Docker Compose（M9）。
- 统一业务错误码体系（M1 建立接口契约时统一）。

**视觉基准（前端实现必须遵守）：**

- 用户端布局参考：
  - `docs/mockups/screens-user-part1.png`：登录页、AI 找货空状态等。
  - `docs/mockups/screens-user-part2.png`：我的页等。
- 客服端布局参考 `docs/mockups/screens-agent.png`，仅作为后续 M6 的视觉基准，M0 不实现。
- 色值、圆角、间距、字号：`docs/mockups/mockup.css` + 设计文档 §11.1.9。
- 关键 token：主色 `#FF5A1F`；品牌渐变 `#FF8A3D → #FF4D2E`；页面背景 `#F6F7F9`；卡片纯白、圆角 14px；主文字 `#22262A`；次要文字 `#9AA0A6`；价格 `#FF4D2E`；底部 Tabbar 高度 56px。
- **只参考布局与视觉，不直接复制 mockup 的 HTML/CSS**；一律用 Vue 3 + Vant 4 组件 + scoped CSS 重新实现。
- 图标按钮触控区 ≥ 44×44px（设计文档 §11.1.9）。

**已确认取舍：**

| 决策点 | 结论 |
|---|---|
| 登录态 | 简版 JWT，7 天，localStorage，无 refresh token |
| DB 迁移范围 | M0 只建 `users` 表 |
| 开发/测试数据库 | 统一 PostgreSQL（开发库 `shop`、测试库 `shop_test`） |
| Docker 范围 | M0 只提供开发数据库 + 后端 Dockerfile 骨架 |
| 前端页面范围 | 只做登录、注册、AI 找货空壳、我的空壳 |

### 参考登录模块的复用边界

参考模块位于 `D:\develop\功能模块\登录注册模块`，技术栈同为 FastAPI + Vue 3 + TypeScript，但功能范围大得多。

**只读参考，不修改该目录**：不写入、不删除、不提交，也不把它的 `.git`、`.env`、README 或 Element Plus 代码带入本项目。

**复用：**

- 后端 `core/config.py`、`core/security.py`、`api/deps.py` 的分层方式与 JWT Bearer 依赖写法。
- 前端 Axios 实例、Pinia auth store、路由守卫的组织方式。
- 测试 conftest 的「导入 app 前设置测试环境变量」做法。

**不复用：**

- Element Plus 桌面端登录界面；本项目按 `docs/mockups/screens-user-part1.png`、`screens-user-part2.png`、`mockup.css` 与设计文档 §11.1.9 的移动端视觉，用 Vant 4 重写。
- 邮箱验证码、邮箱换绑、GitHub OAuth、refresh token 轮换、登录失败限流、管理员用户管理。
- 参考模块的 SQLite 测试库与 `Base.metadata.create_all` 建表方式；本项目用 PostgreSQL + Alembic。

---

## 1. 文件结构

```text
graduation-project-new/
├── .gitignore
├── README.md
├── deploy/
│   ├── docker-compose.dev.yml
│   └── initdb/01-create-test-db.sql
├── backend/
│   ├── .env.example
│   ├── .env                      # 本地创建，不提交
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/20261113_0001_create_users.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py             # 汇总导入 ORM 模型，供 Alembic 发现
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   └── modules/
│   │       ├── __init__.py
│   │       └── auth/
│   │           ├── __init__.py
│   │           ├── models.py
│   │           ├── schemas.py
│   │           ├── service.py
│   │           ├── deps.py
│   │           └── router.py
│   ├── scripts/
│   │   ├── __init__.py
│   │   └── seed_demo_user.py
│   └── tests/
│       ├── conftest.py
│       ├── test_health.py
│       ├── test_db_schema.py
│       ├── test_auth.py
│       ├── test_seed.py
│       └── unit/
│           ├── __init__.py
│           └── test_security.py
└── frontend/
    ├── package.json
    ├── package-lock.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── playwright.config.ts
    ├── index.html
    ├── src/
    │   ├── env.d.ts
    │   ├── main.ts
    │   ├── App.vue
    │   ├── styles/main.css
    │   ├── types/index.ts
    │   ├── utils/token.ts
    │   ├── utils/error.ts
    │   ├── api/http.ts
    │   ├── api/auth.ts
    │   ├── stores/auth.ts
    │   ├── router/index.ts
    │   ├── layouts/TabbarLayout.vue
    │   └── views/user/
    │       ├── LoginView.vue
    │       ├── RegisterView.vue
    │       ├── HomeView.vue
    │       └── MeView.vue
    └── tests/e2e/auth.spec.ts
```

---

## 2. 执行前置

- 平台：Windows 11，Git Bash。
- 已安装：Python 3.12、Node.js 24、npm 11、Docker Desktop、Git。
- 宿主机 5432 已被本机 PostgreSQL 占用，因此 Docker 数据库映射到 **5433**。
- 以下所有 `backend` 命令都在 `backend/` 目录、已激活 `.venv` 的终端执行。
- 以下所有 `frontend` 命令都在 `frontend/` 目录执行。

---

### Task 1: Git 初始化与忽略规则

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: 初始化仓库**

```bash
cd /d/develop/graduation-project-new
git init -b main
```

Expected: `Initialized empty Git repository in D:/develop/graduation-project-new/.git/`

- [ ] **Step 2: 写 `.gitignore`**

```gitignore
# Python
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
backend/.env
backend/app.db

# Node
node_modules/
frontend/dist/
frontend/.vite/
frontend/test-results/
frontend/playwright-report/

# 商品图与上传文件：体积大，单独备份，不进 git
backend/static/products/
backend/static/*.png
backend/uploads/

# 工具与本地文件
.playwright-mcp/
*.log
.DS_Store
.idea/
.vscode/
```

- [ ] **Step 3: 验证大文件未被暂存**

```bash
git add .
git status --short | grep -E "backend/static|node_modules" || echo "OK: no large binaries staged"
```

Expected: `OK: no large binaries staged`

- [ ] **Step 4: 提交基线**

```bash
git commit -m "chore: initialize repository with ignore rules"
```

Expected: 1 file changed（若 `.gitignore` 之外没有其他可提交文件）。

---

### Task 2: Docker 开发数据库与后端镜像骨架

**Files:**
- Create: `deploy/docker-compose.dev.yml`
- Create: `deploy/initdb/01-create-test-db.sql`
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

- [ ] **Step 1: 写 compose 文件**

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: ai-shop-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: shop
      POSTGRES_USER: shop
      POSTGRES_PASSWORD: shop
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./initdb:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U shop -d shop"]
      interval: 5s
      timeout: 3s
      retries: 20

volumes:
  pgdata:
```

- [ ] **Step 2: 写测试库初始化脚本**

```sql
CREATE DATABASE shop_test OWNER shop;
```

- [ ] **Step 3: 写后端镜像骨架**

`backend/Dockerfile`：

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

`backend/.dockerignore`：

```text
.venv
__pycache__
*.pyc
.pytest_cache
.env
static/products
```

> M0 只建立镜像骨架，不执行 `docker build`；M9 补全全栈 compose 与 Nginx 时再验证镜像。

- [ ] **Step 4: 启动数据库**

```bash
cd /d/develop/graduation-project-new
docker compose -f deploy/docker-compose.dev.yml up -d
```

Expected: `Container ai-shop-db  Started`

- [ ] **Step 5: 等待健康检查通过**

```bash
docker inspect --format='{{.State.Health.Status}}' ai-shop-db
```

Expected: `healthy`（若为 `starting`，等 5 秒再执行一次）。

- [ ] **Step 6: 验证两个数据库存在**

```bash
docker exec ai-shop-db psql -U shop -d postgres -tAc \
  "SELECT datname FROM pg_database WHERE datname IN ('shop','shop_test') ORDER BY datname;"
```

Expected:

```text
shop
shop_test
```

若只看到 `shop`，说明数据卷在加入初始化脚本之前已创建过，执行下面的命令补建测试库：

```bash
docker exec ai-shop-db psql -U shop -d postgres -c "CREATE DATABASE shop_test OWNER shop;"
```

- [ ] **Step 7: 提交**

```bash
git add deploy backend/Dockerfile backend/.dockerignore
git commit -m "chore: add dockerized postgres and backend image skeleton"
```

---

### Task 3: 后端骨架与健康检查

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/pytest.ini`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: 写依赖清单**

`backend/requirements.txt`：

```text
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy[asyncio]>=2.0.35
asyncpg>=0.30.0
alembic>=1.14.0
pydantic>=2.8.0
pydantic-settings>=2.4.0
PyJWT>=2.9.0
bcrypt>=4.2.0
anyio>=4.0.0
```

`backend/requirements-dev.txt`：

```text
-r requirements.txt
pytest>=8.3.0
httpx>=0.27.0
```

`backend/pytest.ini`：

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 2: 写环境变量模板**

`backend/.env.example`：

```dotenv
# 开发库（Docker 映射到宿主机 5433，避免与本机 5432 冲突）
DATABASE_URL=postgresql+asyncpg://shop:shop@localhost:5433/shop
# 测试库；pytest 会自动使用
TEST_DATABASE_URL=postgresql+asyncpg://shop:shop@localhost:5433/shop_test

# 必填：python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

# 允许跨域的前端地址，多个用逗号分隔
CORS_ORIGINS=http://localhost:5173
```

- [ ] **Step 3: 创建虚拟环境并安装依赖**

```bash
cd /d/develop/graduation-project-new/backend
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements-dev.txt
```

Expected: 最后一行 `Successfully installed ...`，且 `python -c "import fastapi, sqlalchemy, asyncpg, alembic, jwt, bcrypt"` 无报错。

- [ ] **Step 4: 先写失败的健康检查测试**

`backend/tests/test_health.py`：

```python
def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
```

- [ ] **Step 5: 运行测试，确认失败**

```bash
python -m pytest tests/test_health.py -v
```

Expected: ERROR，`fixture 'client' not found`（此时 conftest 尚未创建）。

- [ ] **Step 6: 写配置、数据库与主应用**

`backend/app/__init__.py`、`backend/app/core/__init__.py`、`backend/app/db/__init__.py` 均为空文件。

`backend/app/core/config.py`：

```python
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：所有可变参数都从环境变量或 .env 读取。"""

    app_name: str = "AI 找货"
    api_prefix: str = "/api"
    database_url: str = "postgresql+asyncpg://shop:shop@localhost:5433/shop"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        """拒绝空值与过短密钥，强制在 .env 中配置随机字符串。"""
        secret = value.strip()
        if len(secret) < 32:
            raise ValueError("JWT_SECRET_KEY 必须至少 32 个字符")
        return secret

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的前端地址转换成列表。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，避免重复读取 .env。"""
    return Settings()


settings = get_settings()
```

`backend/app/db/base.py`：

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# 统一约束命名，保证 Alembic 迁移可预测、可回滚
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

`backend/app/db/session.py`：

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：为每个请求提供一个数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session
```

`backend/app/main.py`：

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时探测数据库，关闭时释放连接池。"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("数据库连接正常")
    except Exception:
        logger.exception("数据库连接失败，健康检查将返回 503")
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(f"{settings.api_prefix}/health")
async def health_check() -> JSONResponse:
    """健康检查：同时确认服务与数据库可用。"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "down"},
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})
```

- [ ] **Step 7: 写测试 conftest**

`backend/tests/conftest.py`：

```python
import os

# 必须在导入 app 之前设置环境变量，确保测试使用独立的测试库
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://shop:shop@localhost:5433/shop_test",
)
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-key-for-pytest-only-0123456789abcdef"
)
os.environ.setdefault("JWT_EXPIRE_MINUTES", "10080")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    """整个测试会话共用一个 TestClient。"""
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 8: 创建本地 `.env` 并生成密钥**

```bash
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
```

Expected: `JWT_SECRET_KEY 已写入 .env`；`grep '^JWT_SECRET_KEY=..' .env` 有输出。

- [ ] **Step 9: 运行测试，确认通过**

```bash
python -m pytest tests/test_health.py -v
```

Expected: `1 passed`。

- [ ] **Step 10: 提交**

```bash
git add backend/requirements.txt backend/requirements-dev.txt backend/pytest.ini \
  backend/.env.example backend/app backend/tests
git commit -m "feat: scaffold fastapi backend with health check"
```

---

### Task 4: users 表与 Alembic 迁移

**Files:**
- Create: `backend/app/modules/__init__.py`
- Create: `backend/app/modules/auth/__init__.py`
- Create: `backend/app/modules/auth/models.py`
- Create: `backend/app/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/20261113_0001_create_users.py`
- Create: `backend/tests/test_db_schema.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: 先写失败的表结构测试**

`backend/tests/test_db_schema.py`：

```python
import asyncio
import os

import asyncpg


def test_users_table_exists(migrated_database):
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def table_name() -> str | None:
        connection = await asyncpg.connect(dsn)
        try:
            return await connection.fetchval("SELECT to_regclass('public.users')::text")
        finally:
            await connection.close()

    assert asyncio.run(table_name()) == "users"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_db_schema.py -v
```

Expected: ERROR，`fixture 'migrated_database' not found`。

- [ ] **Step 3: 写 User 模型**

`backend/app/modules/__init__.py`、`backend/app/modules/auth/__init__.py` 均为空文件。

`backend/app/modules/auth/models.py`：

```python
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """用户表：登录账号与尺码推荐需要的身体档案。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(50))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(
        String(20), default="user", server_default="user", nullable=False
    )
    height_cm: Mapped[int | None] = mapped_column(SmallInteger)
    weight_kg: Mapped[int | None] = mapped_column(SmallInteger)
    usual_size: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

`backend/app/models.py`：

```python
"""集中导入所有 ORM 模型，供 Alembic 发现元数据。"""

from app.modules.auth.models import User  # noqa: F401

__all__ = ["User"]
```

- [ ] **Step 4: 写 Alembic 配置**

`backend/alembic.ini`：

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

`backend/alembic/env.py`：

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401  确保所有模型注册到 Base.metadata
from app.core.config import settings
from app.db.base import Base

config = context.config
# 百分号是 ConfigParser 的插值语法，URL 中若含 % 需要转义
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库。"""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

`backend/alembic/script.py.mako`：

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: 写初始迁移**

`backend/alembic/versions/20261113_0001_create_users.py`：

```python
"""create users table

Revision ID: 20261113_0001
Revises:
Create Date: 2026-11-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261113_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("nickname", sa.String(length=50), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
        sa.Column("height_cm", sa.SmallInteger(), nullable=True),
        sa.Column("weight_kg", sa.SmallInteger(), nullable=True),
        sa.Column("usual_size", sa.String(length=10), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
```

- [ ] **Step 6: 更新 conftest，自动迁移并清理数据**

`backend/tests/conftest.py` 完整替换为：

```python
import asyncio
import os
import subprocess
import sys
from pathlib import Path

# 必须在导入 app 之前设置环境变量，确保测试使用独立的测试库
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://shop:shop@localhost:5433/shop_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-key-for-pytest-only-0123456789abcdef"
)
os.environ.setdefault("JWT_EXPIRE_MINUTES", "10080")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.main import app

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def migrated_database():
    """对整个测试会话执行一次 Alembic 迁移，同时验证迁移脚本可用。"""
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        check=True,
    )
    yield


@pytest.fixture(scope="session")
def client(migrated_database):
    """整个测试会话共用一个 TestClient。"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_users(migrated_database):
    """每个测试开始前清空 users 表，保证用例互不影响。"""

    async def _clean() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE TABLE users RESTART IDENTITY CASCADE")
            )
        await engine.dispose()

    asyncio.run(_clean())
    yield
```

- [ ] **Step 7: 对开发库执行迁移**

```bash
python -m alembic upgrade head
```

Expected:

```text
INFO  [alembic.runtime.migration] Running upgrade  -> 20261113_0001, create users table
```

- [ ] **Step 8: 运行测试，确认通过**

```bash
python -m pytest tests/test_db_schema.py -v
```

Expected: `1 passed`。

- [ ] **Step 9: 提交**

```bash
git add backend/app/modules backend/app/models.py backend/alembic.ini backend/alembic \
  backend/tests/conftest.py backend/tests/test_db_schema.py
git commit -m "feat: add users table and initial alembic migration"
```

---

### Task 5: 密码哈希与 JWT 工具

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/tests/unit/__init__.py`
- Create: `backend/tests/unit/test_security.py`

- [ ] **Step 1: 先写失败的安全工具测试**

`backend/tests/unit/__init__.py` 为空文件。

`backend/tests/unit/test_security.py`：

```python
import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip():
    password_hash = hash_password("secret123")
    assert password_hash != "secret123"
    assert verify_password("secret123", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_password_hash_rejects_over_72_bytes():
    with pytest.raises(ValueError):
        hash_password("密" * 30)


def test_access_token_round_trip():
    token, expires_in = create_access_token(42)
    assert expires_in > 0
    assert decode_access_token(token) == 42


def test_decode_invalid_token_raises():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-token")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/unit/test_security.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'app.core.security'`。

- [ ] **Step 3: 实现安全工具**

`backend/app/core/security.py`：

```python
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

# bcrypt 只处理前 72 字节，超出部分会被静默截断，因此显式拒绝
BCRYPT_MAX_BYTES = 72


class InvalidTokenError(Exception):
    """访问令牌无效或已过期。"""


def hash_password(password: str) -> str:
    """使用 bcrypt 生成密码哈希，自动加盐。"""
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError("密码不能超过 72 字节")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验明文密码；损坏的哈希或超长输入视为不匹配。"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def create_access_token(user_id: int) -> tuple[str, int]:
    """签发 access token，返回令牌字符串与有效秒数。"""
    expires_in = settings.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return token, expires_in


def decode_access_token(token: str) -> int:
    """校验 access token，返回用户 id；无效时抛出 InvalidTokenError。"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("invalid token") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise InvalidTokenError("invalid token type")

    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError("invalid subject") from exc
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/unit/test_security.py -v
```

Expected: `4 passed`。

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/security.py backend/tests/unit
git commit -m "feat: add bcrypt password hashing and jwt helpers"
```

---

### Task 6: 注册接口

**Files:**
- Create: `backend/app/modules/auth/schemas.py`
- Create: `backend/app/modules/auth/service.py`
- Create: `backend/app/modules/auth/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: 先写失败的注册测试**

`backend/tests/test_auth.py`：

```python
def register(
    client,
    username: str = "alice",
    password: str = "secret123",
    nickname: str | None = "Alice",
):
    payload = {"username": username, "password": password}
    if nickname is not None:
        payload["nickname"] = nickname
    return client.post("/api/auth/register", json=payload)


def test_register_returns_user_without_password_hash(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert body["nickname"] == "Alice"
    assert body["role"] == "user"
    assert "password_hash" not in body


def test_register_duplicate_username_returns_409(client):
    register(client)
    response = register(client)
    assert response.status_code == 409
    assert response.json()["detail"] == "用户名已被注册"


def test_register_rejects_short_password(client):
    response = register(client, password="12345")
    assert response.status_code == 422


def test_register_rejects_password_over_72_bytes(client):
    response = register(client, password="密" * 30)
    assert response.status_code == 422


def test_register_without_nickname_uses_username(client):
    response = register(client, nickname=None)
    assert response.status_code == 201
    assert response.json()["nickname"] == "alice"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_auth.py -v
```

Expected: FAIL，5 个用例均为 `404 Not Found`。

- [ ] **Step 3: 写请求/响应模型**

`backend/app/modules/auth/schemas.py`：

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_]+$"


class RegisterRequest(BaseModel):
    """注册请求：用户名、密码与可选昵称。"""

    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=6, max_length=128)
    nickname: str | None = Field(default=None, max_length=50)

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        """去掉用户名首尾空白，避免产生不可见字符账号。"""
        return value.strip() if isinstance(value, str) else value

    @field_validator("nickname", mode="before")
    @classmethod
    def blank_nickname_to_none(cls, value: object) -> object:
        """空白昵称按未填写处理。"""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        """bcrypt 只支持 72 字节以内的密码。"""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码不能超过 72 字节")
        return value


class UserOut(BaseModel):
    """对外返回的用户信息，不包含密码哈希。"""

    id: int
    username: str
    nickname: str | None
    avatar_url: str | None
    role: str
    height_cm: int | None
    weight_kg: int | None
    usual_size: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: 写注册服务**

`backend/app/modules/auth/service.py`：

```python
import anyio
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterRequest


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    """注册新用户：检查用户名重复后写入数据库。"""
    existing = await db.scalar(select(User.id).where(User.username == data.username))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="用户名已被注册"
        )

    # bcrypt 是 CPU 密集操作，放到线程池避免阻塞事件循环
    password_hash = await anyio.to_thread.run_sync(hash_password, data.password)
    user = User(
        username=data.username,
        password_hash=password_hash,
        nickname=data.nickname or data.username,
        role="user",
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        # 并发注册同名用户时由数据库唯一约束兜底
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="用户名已被注册"
        ) from exc
    await db.refresh(user)
    return user
```

- [ ] **Step 5: 写注册路由**

`backend/app/modules/auth/router.py`：

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterRequest, UserOut
from app.modules.auth import service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserOut, status_code=status.HTTP_201_CREATED
)
async def register(
    data: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> User:
    """注册接口：创建账号并返回用户公开信息。"""
    return await service.register_user(db, data)
```

- [ ] **Step 6: 在 main.py 挂载 auth 路由**

在 `backend/app/main.py` 的 import 区加入：

```python
from app.modules.auth.router import router as auth_router
```

在 `app.add_middleware(...)` 之后加入：

```python
app.include_router(auth_router, prefix=settings.api_prefix)
```

- [ ] **Step 7: 运行测试，确认通过**

```bash
python -m pytest tests/test_auth.py -v
```

Expected: `5 passed`。

- [ ] **Step 8: 提交**

```bash
git add backend/app/modules/auth backend/app/main.py backend/tests/test_auth.py
git commit -m "feat: add user registration endpoint"
```

---

### Task 7: 登录与当前用户接口

**Files:**
- Modify: `backend/app/modules/auth/schemas.py`
- Modify: `backend/app/modules/auth/service.py`
- Modify: `backend/app/modules/auth/router.py`
- Modify: `backend/tests/test_auth.py`

- [ ] **Step 1: 先写失败的登录/当前用户测试**

在 `backend/tests/test_auth.py` 末尾追加：

```python
def login(client, username: str = "alice", password: str = "secret123"):
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


def test_login_returns_token_and_user(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "alice"


def test_login_with_wrong_password_returns_401(client):
    register(client)
    response = login(client, password="wrong-password")
    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码错误"


def test_login_with_unknown_user_returns_same_message(client):
    response = login(client, username="nobody", password="wrong-password")
    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码错误"


def test_me_requires_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "未登录或登录已过期"


def test_me_returns_current_user(client):
    register(client)
    token = login(client).json()["access_token"]
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_me_with_invalid_token_returns_401(client):
    response = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_auth.py -v
```

Expected: 新增的 6 个用例失败，登录返回 `404 Not Found`，`/me` 返回 `404 Not Found`。

- [ ] **Step 3: 扩展 schemas**

在 `backend/app/modules/auth/schemas.py` 的 `RegisterRequest` 之后加入：

```python
class LoginRequest(BaseModel):
    """登录请求：用户名 + 密码。"""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        """去掉用户名首尾空白；密码保持原样。"""
        return value.strip() if isinstance(value, str) else value
```

在 `UserOut` 之后加入：

```python
class TokenResponse(BaseModel):
    """登录成功后返回的令牌信息。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
```

- [ ] **Step 4: 扩展 service**

在 `backend/app/modules/auth/service.py` 文件顶部（import 与模块常量）替换为：

```python
import anyio
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginRequest, RegisterRequest

# 账号不存在时也执行一次哈希校验，避免用响应时间探测账号是否存在
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")
```

在文件末尾加入：

```python
async def authenticate_user(db: AsyncSession, data: LoginRequest) -> User:
    """按用户名查找用户并校验密码；凭据错误统一返回 401。"""
    user = await db.scalar(select(User).where(User.username == data.username))

    if user is None:
        await anyio.to_thread.run_sync(
            verify_password, data.password, DUMMY_PASSWORD_HASH
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    password_ok = await anyio.to_thread.run_sync(
        verify_password, data.password, user.password_hash
    )
    if not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    return user


def issue_access_token(user: User) -> tuple[str, int]:
    """为用户签发 access token。"""
    return create_access_token(user.id)
```

- [ ] **Step 5: 写登录依赖**

`backend/app/modules/auth/deps.py`：

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.modules.auth.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized_exception() -> HTTPException:
    """统一的 401 响应，并声明 Bearer 认证方式。"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或登录已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 Authorization 头解析 access token，返回当前登录用户。"""
    if credentials is None:
        raise unauthorized_exception()

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise unauthorized_exception() from exc

    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized_exception()
    return user
```

- [ ] **Step 6: 扩展 router**

`backend/app/modules/auth/router.py` 完整替换为：

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserOut, status_code=status.HTTP_201_CREATED
)
async def register(
    data: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> User:
    """注册接口：创建账号并返回用户公开信息。"""
    return await service.register_user(db, data)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """登录接口：返回 access token 与用户信息。"""
    user = await service.authenticate_user(db, data)
    access_token, expires_in = service.issue_access_token(user)
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def read_me(current_user: User = Depends(get_current_user)) -> User:
    """返回当前登录用户信息。"""
    return current_user
```

- [ ] **Step 7: 运行测试，确认通过**

```bash
python -m pytest tests/test_auth.py -v
```

Expected: `11 passed`。

- [ ] **Step 8: 提交**

```bash
git add backend/app/modules/auth backend/tests/test_auth.py
git commit -m "feat: add login and current user endpoints"
```

---

### Task 8: 演示账号种子脚本

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/seed_demo_user.py`
- Create: `backend/tests/test_seed.py`

- [ ] **Step 1: 先写失败的种子脚本测试**

`backend/tests/test_seed.py`：

```python
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def run_seed() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "scripts.seed_demo_user"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_seed_demo_user_creates_loginable_account(client):
    result = run_seed()
    assert "已创建演示账号" in result.stdout
    response = client.post(
        "/api/auth/login", json={"username": "demo", "password": "demo123"}
    )
    assert response.status_code == 200


def test_seed_demo_user_is_idempotent(client):
    run_seed()
    result = run_seed()
    assert "已存在" in result.stdout
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_seed.py -v
```

Expected: FAIL，`No module named scripts.seed_demo_user`。

- [ ] **Step 3: 实现种子脚本**

`backend/scripts/__init__.py` 为空文件。

`backend/scripts/seed_demo_user.py`：

```python
"""创建演示账号 demo / demo123；重复执行不会重复创建。"""

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.modules.auth.models import User

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"


async def seed_demo_user() -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(User.id).where(User.username == DEMO_USERNAME)
        )
        if existing is not None:
            print("演示账号已存在，跳过")
            return

        session.add(
            User(
                username=DEMO_USERNAME,
                password_hash=hash_password(DEMO_PASSWORD),
                nickname="小鹿",
                role="user",
                height_cm=172,
                weight_kg=75,
                usual_size="M",
            )
        )
        await session.commit()
        print("已创建演示账号 demo / demo123")


async def main() -> None:
    try:
        await seed_demo_user()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/test_seed.py -v
```

Expected: `2 passed`。

- [ ] **Step 5: 对开发库执行种子脚本并验证幂等**

```bash
python -m scripts.seed_demo_user
python -m scripts.seed_demo_user
```

Expected: 第一次 `已创建演示账号 demo / demo123`，第二次 `演示账号已存在，跳过`。

- [ ] **Step 6: 提交**

```bash
git add backend/scripts backend/tests/test_seed.py
git commit -m "feat: seed demo account"
```

---

### Task 9: 前端脚手架与全局样式

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/env.d.ts`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/views/user/HomeView.vue`
- Create: `frontend/src/styles/main.css`

- [ ] **Step 1: 写包与构建配置**

`frontend/package.json`：

```json
{
  "name": "ai-shopping-agent-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "axios": "^1.7.9",
    "pinia": "^2.3.0",
    "vant": "^4.9.15",
    "vue": "^3.5.13",
    "vue-router": "^4.5.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.49.1",
    "@types/node": "^22.10.2",
    "@vitejs/plugin-vue": "^5.2.1",
    "typescript": "~5.6.3",
    "vite": "^6.0.5",
    "vue-tsc": "^2.1.10"
  }
}
```

`frontend/vite.config.ts`：

```ts
import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

`frontend/tsconfig.json`：

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "strict": true,
    "noEmit": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "useDefineForClassFields": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    },
    "types": ["vite/client", "node"]
  },
  "include": [
    "src/**/*.ts",
    "src/**/*.d.ts",
    "src/**/*.vue",
    "vite.config.ts",
    "playwright.config.ts",
    "tests/**/*.ts"
  ]
}
```

- [ ] **Step 2: 安装依赖**

```bash
cd /d/develop/graduation-project-new/frontend
npm install
```

Expected: 生成 `package-lock.json`，最后一行类似 `added 120 packages in 10s`。

- [ ] **Step 3: 写入口文件**

`frontend/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"
    />
    <title>AI 找货</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

`frontend/src/env.d.ts`：

```ts
/// <reference types="vite/client" />
```

`frontend/src/main.ts`：

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Vant from 'vant'
import 'vant/lib/index.css'

import App from './App.vue'
import router from './router'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(Vant)
app.mount('#app')
```

`frontend/src/App.vue`：

```vue
<template>
  <router-view />
</template>
```

- [ ] **Step 4: 写最小路由与首页空壳**

视觉参考 `docs/mockups/screens-user-part1.png` 的「02 导购空状态」与 `docs/mockups/mockup.css`；只取布局、色值和间距，用 Vant 组件 + scoped CSS 重写，不复制 mockup 的 HTML/CSS。

`frontend/src/router/index.ts`：

```ts
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/user/HomeView.vue'),
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
```

`frontend/src/views/user/HomeView.vue`：

```vue
<template>
  <div class="page home-page">
    <header class="home-header">
      <div class="brand">
        <div class="brand-logo">AI</div>
        <div>
          <div class="brand-title">AI 找货</div>
          <div class="brand-sub">对话式导购助手</div>
        </div>
      </div>
    </header>
    <main class="home-body">
      <div class="empty-card">
        <div class="empty-avatar">AI</div>
        <h2>AI 导购即将上线</h2>
        <p>当前为 M0 项目骨架</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.home-page {
  min-height: 100vh;
  background: var(--color-bg);
}

.home-header {
  height: 58px;
  background: #fff;
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid #eef0f3;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.1;
}

.brand-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.home-body {
  padding: 16px;
}

.empty-card {
  background: #fff;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 36px 20px;
  text-align: center;
}

.empty-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  margin: 0 auto 14px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-card h2 {
  font-size: 16px;
  margin: 0 0 6px;
}

.empty-card p {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0;
}
</style>
```

- [ ] **Step 5: 写全局样式**

`frontend/src/styles/main.css`：

```css
:root {
  --color-primary: #ff5a1f;
  --color-primary-gradient: linear-gradient(135deg, #ff8a3d, #ff4d2e);
  --color-bg: #f6f7f9;
  --color-card: #ffffff;
  --color-text: #22262a;
  --color-text-secondary: #9aa0a6;
  --color-price: #ff4d2e;
  --radius-card: 14px;
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.04);
  --van-primary-color: #ff5a1f;
  --van-tabbar-height: 56px;
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  height: 100%;
}

body {
  margin: 0;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Microsoft YaHei", sans-serif;
  -webkit-font-smoothing: antialiased;
}

button,
input {
  font-family: inherit;
}

.page {
  min-height: 100vh;
  background: var(--color-bg);
}
```

- [ ] **Step 6: 构建验证**

```bash
npm run build
```

Expected: `vue-tsc` 无报错，Vite 输出 `built in ...`。

- [ ] **Step 7: 提交**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts \
  frontend/tsconfig.json frontend/index.html frontend/src
git commit -m "feat: scaffold vue frontend with vant and design tokens"
```

---

### Task 10: 前端认证数据层

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/utils/token.ts`
- Create: `frontend/src/utils/error.ts`
- Create: `frontend/src/api/http.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/stores/auth.ts`

- [ ] **Step 1: 写类型定义**

`frontend/src/types/index.ts`：

```ts
export type UserRole = 'user' | 'agent' | 'admin'

export interface User {
  id: number
  username: string
  nickname: string | null
  avatar_url: string | null
  role: UserRole
  height_cm: number | null
  weight_kg: number | null
  usual_size: string | null
  created_at: string
}

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  password: string
  nickname?: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}
```

- [ ] **Step 2: 写 token 与错误提示工具**

`frontend/src/utils/token.ts`：

```ts
const TOKEN_KEY = 'ai-shop-access-token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}
```

`frontend/src/utils/error.ts`：

```ts
import axios from 'axios'

interface ValidationErrorItem {
  msg?: string
}

export function getErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return '操作失败，请稍后重试'
  }

  const detail: unknown = error.response?.data?.detail
  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as ValidationErrorItem
    if (typeof first?.msg === 'string') {
      return first.msg.replace(/^Value error, /, '')
    }
  }

  if (!error.response) {
    return '网络异常，请稍后重试'
  }
  return '操作失败，请稍后重试'
}
```

- [ ] **Step 3: 写 HTTP 客户端与认证 API**

`frontend/src/api/http.ts`：

```ts
import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

import { clearToken, getToken } from '@/utils/token'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig | undefined
    const isLoginRequest = original?.url?.includes('/auth/login')

    // 登录接口本身返回 401 时只提示，不触发全局退出
    if (error.response?.status === 401 && !isLoginRequest) {
      clearToken()
      window.dispatchEvent(new CustomEvent('auth:expired'))
    }
    return Promise.reject(error)
  },
)

export default http
```

`frontend/src/api/auth.ts`：

```ts
import http from '@/api/http'
import type {
  LoginPayload,
  RegisterPayload,
  TokenResponse,
  User,
} from '@/types'

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await http.post<User>('/auth/register', payload)
  return data
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  const { data } = await http.post<TokenResponse>('/auth/login', payload)
  return data
}

export async function fetchMe(): Promise<User> {
  const { data } = await http.get<User>('/auth/me')
  return data
}
```

- [ ] **Step 4: 写 Pinia 认证 store**

`frontend/src/stores/auth.ts`：

```ts
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as authApi from '@/api/auth'
import type {
  LoginPayload,
  RegisterPayload,
  TokenResponse,
  User,
} from '@/types'
import { clearToken, getToken, setToken } from '@/utils/token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<User | null>(null)
  const initialized = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value))

  function applyLogin(data: TokenResponse): void {
    token.value = data.access_token
    user.value = data.user
    setToken(data.access_token)
    initialized.value = true
  }

  function clear(): void {
    token.value = null
    user.value = null
    initialized.value = true
    clearToken()
  }

  async function login(payload: LoginPayload): Promise<void> {
    applyLogin(await authApi.login(payload))
  }

  async function registerAndLogin(payload: RegisterPayload): Promise<void> {
    await authApi.register(payload)
    await login({ username: payload.username, password: payload.password })
  }

  async function ensureUserLoaded(): Promise<void> {
    if (initialized.value) {
      return
    }
    if (!token.value) {
      initialized.value = true
      return
    }
    try {
      user.value = await authApi.fetchMe()
    } catch {
      clear()
    } finally {
      initialized.value = true
    }
  }

  function logout(): void {
    clear()
  }

  return {
    token,
    user,
    initialized,
    isAuthenticated,
    login,
    registerAndLogin,
    ensureUserLoaded,
    logout,
    clear,
  }
})
```

- [ ] **Step 5: 构建验证**

```bash
npm run build
```

Expected: `vue-tsc` 无报错，Vite 构建成功。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/types frontend/src/utils frontend/src/api frontend/src/stores
git commit -m "feat: add frontend auth api client and pinia store"
```

---

### Task 11: 登录页与注册页

**Files:**
- Create: `frontend/src/views/user/LoginView.vue`
- Create: `frontend/src/views/user/RegisterView.vue`

- [ ] **Step 1: 写登录页**

视觉参考 `docs/mockups/screens-user-part1.png` 的「01 登录 / 注册」屏与 `docs/mockups/mockup.css`：Logo、标题、副标题、灰色圆角输入框、主色登录按钮、描边注册按钮、演示账号提示。用 Vant `van-form` / `van-field` / `van-button` 重写，不复制 mockup 的 HTML/CSS。

`frontend/src/views/user/LoginView.vue`：

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/error'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
})

async function handleSubmit(): Promise<void> {
  if (loading.value) {
    return
  }
  if (!form.username.trim() || !form.password) {
    showToast('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    await auth.login({ username: form.username.trim(), password: form.password })
    showToast('登录成功')
    const redirect =
      typeof route.query.redirect === 'string' &&
      route.query.redirect.startsWith('/')
        ? route.query.redirect
        : '/'
    await router.replace(redirect)
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-logo">AI</div>
    <h1 class="login-title">AI 找货</h1>
    <p class="login-subtitle">说出你想找的，AI 帮你挑</p>

    <van-form class="login-form" @submit="handleSubmit">
      <van-field
        v-model="form.username"
        name="username"
        placeholder="用户名"
        autocomplete="username"
        class="login-field"
      />
      <van-field
        v-model="form.password"
        type="password"
        name="password"
        placeholder="密码"
        autocomplete="current-password"
        class="login-field"
      />
      <van-button
        block
        type="primary"
        native-type="submit"
        :loading="loading"
        class="login-button"
      >
        登录
      </van-button>
    </van-form>

    <van-button
      block
      plain
      type="primary"
      class="register-button"
      @click="router.push('/register')"
    >
      注册新账号
    </van-button>
    <p class="login-hint">演示账号：demo / demo123</p>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  background: #fff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 30px;
}

.login-logo {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-weight: 800;
  font-size: 21px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
}

.login-title {
  font-size: 22px;
  margin: 0 0 4px;
}

.login-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0 0 26px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.login-field {
  border-radius: 12px;
  background: #f4f5f7;
}

:deep(.login-field::after) {
  display: none;
}

:deep(.login-field .van-field__control) {
  font-size: 13px;
}

.login-button {
  height: 44px;
  margin-top: 6px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
}

.register-button {
  height: 44px;
  margin-top: 9px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
}

.login-hint {
  text-align: center;
  font-size: 10.5px;
  color: #a0a5ab;
  margin-top: 16px;
}
</style>
```

- [ ] **Step 2: 写注册页**

注册页沿用登录页的视觉语言（同 Logo、同输入框、同按钮样式），只增加昵称和确认密码字段，不新增 mockup 之外的元素。

`frontend/src/views/user/RegisterView.vue`：

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'

import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/error'

const auth = useAuthStore()
const router = useRouter()

const loading = ref(false)
const form = reactive({
  username: '',
  nickname: '',
  password: '',
  confirmPassword: '',
})

async function handleSubmit(): Promise<void> {
  if (loading.value) {
    return
  }
  if (!form.username.trim() || !form.password) {
    showToast('请填写用户名和密码')
    return
  }
  if (form.password !== form.confirmPassword) {
    showToast('两次输入的密码不一致')
    return
  }

  loading.value = true
  try {
    await auth.registerAndLogin({
      username: form.username.trim(),
      password: form.password,
      nickname: form.nickname.trim() || null,
    })
    showToast('注册成功')
    await router.replace('/')
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register-page">
    <div class="register-logo">AI</div>
    <h1 class="register-title">注册新账号</h1>
    <p class="register-subtitle">注册后自动登录</p>

    <van-form class="register-form" @submit="handleSubmit">
      <van-field
        v-model="form.username"
        name="username"
        placeholder="用户名"
        autocomplete="username"
        class="register-field"
      />
      <van-field
        v-model="form.nickname"
        name="nickname"
        placeholder="昵称（可选）"
        class="register-field"
      />
      <van-field
        v-model="form.password"
        type="password"
        name="password"
        placeholder="密码"
        autocomplete="new-password"
        class="register-field"
      />
      <van-field
        v-model="form.confirmPassword"
        type="password"
        name="confirmPassword"
        placeholder="确认密码"
        autocomplete="new-password"
        class="register-field"
      />
      <van-button
        block
        type="primary"
        native-type="submit"
        :loading="loading"
        class="register-submit"
      >
        注册并登录
      </van-button>
    </van-form>

    <van-button
      block
      plain
      type="primary"
      class="back-button"
      @click="router.push('/login')"
    >
      返回登录
    </van-button>
  </div>
</template>

<style scoped>
.register-page {
  min-height: 100vh;
  background: #fff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 30px;
}

.register-logo {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-weight: 800;
  font-size: 21px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
}

.register-title {
  font-size: 22px;
  margin: 0 0 4px;
}

.register-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0 0 26px;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.register-field {
  border-radius: 12px;
  background: #f4f5f7;
}

:deep(.register-field::after) {
  display: none;
}

:deep(.register-field .van-field__control) {
  font-size: 13px;
}

.register-submit {
  height: 44px;
  margin-top: 6px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
}

.back-button {
  height: 44px;
  margin-top: 9px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
}
</style>
```

- [ ] **Step 3: 构建验证**

```bash
npm run build
```

Expected: `vue-tsc` 无报错，Vite 构建成功。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/user/LoginView.vue frontend/src/views/user/RegisterView.vue
git commit -m "feat: add login and register pages"
```

---

### Task 12: 路由守卫、双 Tab 布局与我的页

**Files:**
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/layouts/TabbarLayout.vue`
- Modify: `frontend/src/views/user/HomeView.vue`
- Create: `frontend/src/views/user/MeView.vue`
- Modify: `frontend/src/main.ts`

- [ ] **Step 1: 写双 Tab 布局**

视觉参考 `docs/mockups/screens-user-part1.png`、`screens-user-part2.png` 的底部 Tabbar 与 `docs/mockups/mockup.css`；Tabbar 高度 56px，选中色 `#FF5A1F`，未选中色 `#9AA0A6`。用 Vant `van-tabbar` 实现，不复制 mockup 的 HTML/CSS。

`frontend/src/layouts/TabbarLayout.vue`：

```vue
<template>
  <div class="app-shell">
    <main class="app-main">
      <router-view />
    </main>
    <van-tabbar route active-color="#FF5A1F" inactive-color="#9AA0A6">
      <van-tabbar-item replace to="/" icon="chat-o">AI 找货</van-tabbar-item>
      <van-tabbar-item replace to="/me" icon="user-o">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: var(--color-bg);
}

.app-main {
  min-height: 100vh;
  padding-bottom: 56px;
}

:deep(.van-tabbar) {
  height: 56px;
}
</style>
```

- [ ] **Step 2: 把首页接到当前用户**

视觉参考 `docs/mockups/screens-user-part1.png` 的「02 导购空状态」：顶部品牌栏 + 问候 + 占位卡。M0 不实现示例问法、品类入口、热门商品卡、输入栏，这些留到 M4。

`frontend/src/views/user/HomeView.vue` 完整替换为：

```vue
<script setup lang="ts">
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const displayName = computed(
  () => auth.user?.nickname || auth.user?.username || '',
)
</script>

<template>
  <div class="page home-page">
    <header class="home-header">
      <div class="brand">
        <div class="brand-logo">AI</div>
        <div>
          <div class="brand-title">AI 找货</div>
          <div class="brand-sub">对话式导购助手</div>
        </div>
      </div>
    </header>
    <main class="home-body">
      <div class="empty-card">
        <div class="empty-avatar">AI</div>
        <h2>你好，{{ displayName }}</h2>
        <p>AI 导购对话将在 M4 上线</p>
        <p class="empty-sub">当前为 M0 项目骨架，登录与双 Tab 已就绪</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.home-page {
  min-height: 100vh;
  background: var(--color-bg);
}

.home-header {
  height: 58px;
  background: #fff;
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid #eef0f3;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.1;
}

.brand-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.home-body {
  padding: 16px;
}

.empty-card {
  background: #fff;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 36px 20px;
  text-align: center;
}

.empty-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  margin: 0 auto 14px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-card h2 {
  font-size: 16px;
  margin: 0 0 6px;
}

.empty-card p {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0;
}

.empty-sub {
  margin-top: 4px;
  color: #c0c5cb;
}
</style>
```

- [ ] **Step 3: 写我的页**

视觉参考 `docs/mockups/screens-user-part2.png` 的「10 我的」屏与 `mockup.css`。M0 只保留用户卡片、后续功能占位文案和退出登录；订单快捷入口、收藏/地址/会话菜单等留到后续模块，不在 M0 实现。

`frontend/src/views/user/MeView.vue`：

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { showConfirmDialog } from 'vant'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function handleLogout(): Promise<void> {
  try {
    await showConfirmDialog({
      title: '退出登录',
      message: '确定要退出当前账号吗？',
    })
  } catch {
    return
  }
  auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="page me-page">
    <header class="me-header">
      <h1>我的</h1>
    </header>
    <main class="me-body">
      <section class="me-card">
        <div class="me-avatar">
          {{ (auth.user?.nickname || auth.user?.username || '?').slice(0, 1) }}
        </div>
        <div class="me-info">
          <div class="me-name">
            {{ auth.user?.nickname || auth.user?.username }}
          </div>
          <div class="me-sub">
            <template v-if="auth.user?.height_cm || auth.user?.weight_kg">
              <span v-if="auth.user?.height_cm">{{ auth.user?.height_cm }}cm</span>
              <span v-if="auth.user?.weight_kg"> / {{ auth.user?.weight_kg }}kg</span>
              <span v-if="auth.user?.usual_size">
                · 常穿 {{ auth.user?.usual_size }} 码
              </span>
            </template>
            <template v-else>账号：{{ auth.user?.username }}</template>
          </div>
        </div>
      </section>

      <section class="me-placeholder">
        <div class="placeholder-title">更多功能将在后续模块上线</div>
        <p class="placeholder-text">收藏、地址、订单、导购会话</p>
      </section>

      <van-button block class="logout-button" @click="handleLogout">
        退出登录
      </van-button>
    </main>
  </div>
</template>

<style scoped>
.me-page {
  min-height: 100vh;
  background: var(--color-bg);
}

.me-header {
  height: 58px;
  background: #fff;
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid #eef0f3;
}

.me-header h1 {
  font-size: 16px;
  margin: 0;
}

.me-body {
  padding: 14px;
}

.me-card {
  background: #fff;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 16px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.me-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ffb08a, #ff5a1f);
  color: #fff;
  font-size: 17px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.me-name {
  font-size: 15px;
  font-weight: 700;
}

.me-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
  margin-top: 3px;
}

.me-placeholder {
  background: #fff;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  margin-top: 10px;
  padding: 20px 14px;
  text-align: center;
}

.placeholder-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--color-text);
}

.placeholder-text {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin: 6px 0 0;
}

.logout-button {
  margin-top: 18px;
  height: 42px;
  border-radius: 9px;
  color: #ff4d2e;
  border: 1px solid #ffd2bd;
  background: #fff;
  font-size: 13px;
}
</style>
```

- [ ] **Step 4: 写完整路由与守卫**

`frontend/src/router/index.ts` 完整替换为：

```ts
import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/user/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/user/RegisterView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/TabbarLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'home',
          component: () => import('@/views/user/HomeView.vue'),
        },
        {
          path: 'me',
          name: 'me',
          component: () => import('@/views/user/MeView.vue'),
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.ensureUserLoaded()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'home' }
  }
  return true
})

export default router
```

- [ ] **Step 5: 在 main.ts 处理会话过期**

`frontend/src/main.ts` 完整替换为：

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Vant from 'vant'
import 'vant/lib/index.css'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './styles/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(Vant)

const auth = useAuthStore(pinia)

// HTTP 拦截器发现 401 时广播事件，这里清理登录态并回到登录页
window.addEventListener('auth:expired', () => {
  auth.clear()
  const current = router.currentRoute.value
  if (current.name !== 'login') {
    router.push({ name: 'login', query: { redirect: current.fullPath } })
  }
})

app.mount('#app')
```

- [ ] **Step 6: 构建验证**

```bash
npm run build
```

Expected: `vue-tsc` 无报错，Vite 构建成功。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/router frontend/src/layouts frontend/src/views/user/HomeView.vue \
  frontend/src/views/user/MeView.vue frontend/src/main.ts
git commit -m "feat: add guarded routes and two-tab mobile shell"
```

---

### Task 13: Playwright 登录 E2E

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/e2e/auth.spec.ts`

- [ ] **Step 1: 写 Playwright 配置**

`frontend/playwright.config.ts`：

```ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  fullyParallel: false,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'mobile-chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 390, height: 844 },
      },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
```

- [ ] **Step 2: 写登录 E2E**

`frontend/tests/e2e/auth.spec.ts`：

```ts
import { expect, test } from '@playwright/test'

test('演示账号登录后看到双 Tab 空壳', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByRole('button', { name: '登录' }).click()

  await expect(page).toHaveURL('/')
  const tabs = page.locator('.van-tabbar-item')
  await expect(tabs.filter({ hasText: 'AI 找货' })).toBeVisible()
  await expect(tabs.filter({ hasText: '我的' })).toBeVisible()
  await expect(page.getByText('你好，小鹿')).toBeVisible()

  await tabs.filter({ hasText: '我的' }).click()
  await expect(page).toHaveURL('/me')
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
})
```

- [ ] **Step 3: 安装 Chromium**

```bash
cd /d/develop/graduation-project-new/frontend
npx playwright install chromium
```

Expected: `Chromium ... downloaded to ...`（若已安装则提示已存在）。

- [ ] **Step 4: 启动完整栈**

终端 1（数据库）：

```bash
cd /d/develop/graduation-project-new
docker compose -f deploy/docker-compose.dev.yml up -d
```

终端 2（后端，保持运行）：

```bash
cd /d/develop/graduation-project-new/backend
source .venv/Scripts/activate
python -m alembic upgrade head
python -m scripts.seed_demo_user
uvicorn app.main:app --port 8000
```

终端 3（前端测试，Playwright 会自动启动 Vite）：

```bash
cd /d/develop/graduation-project-new/frontend
npm run test:e2e
```

Expected: `1 passed`。

- [ ] **Step 5: 提交**

```bash
git add frontend/playwright.config.ts frontend/tests
git commit -m "test: add playwright login smoke test"
```

---

### Task 14: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: 写 README**

`README.md`：

```markdown
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
uvicorn app.main:app --reload --port 8000
```

健康检查：<http://localhost:8000/api/health>

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

前端 E2E（先确保数据库已迁移、演示账号已创建、后端已在 8000 端口运行）：

```bash
cd frontend
npx playwright install chromium   # 首次
npm run test:e2e
```

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
```

## 说明

- `backend/static/products/` 约 342MB，已在 `.gitignore` 中排除，需单独备份。
- 当前登录态为 7 天 JWT，存 localStorage；refresh token 留到后续安全增强。
```

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: add project readme and local setup guide"
```

---

### Task 15: 全量验收与进度记录

**Files:**
- Modify: `docs/progress.md`
- Modify: `docs/implementation-handoff.md`

- [ ] **Step 1: 后端全量测试**

```bash
cd /d/develop/graduation-project-new/backend
source .venv/Scripts/activate
python -m pytest -v
```

Expected: `19 passed`（health 1 + db schema 1 + security 4 + auth 11 + seed 2）。

- [ ] **Step 2: 前端类型检查与构建**

```bash
cd /d/develop/graduation-project-new/frontend
npm run build
```

Expected: `vue-tsc` 无报错，Vite 构建成功。

- [ ] **Step 3: E2E 验收**

按 Task 13 Step 4 启动数据库、后端与测试，运行：

```bash
npm run test:e2e
```

Expected: `1 passed`。

- [ ] **Step 4: 手工验收**

1. 打开 <http://localhost:5173>，未登录时被重定向到 `/login`。
2. 输入 `demo / demo123`，点击登录。
3. 页面进入 `/`，看到「AI 找货」标题、问候语「你好，小鹿」和底部两个 Tab。
4. 点击「我的」，进入 `/me`，看到用户卡片（172cm / 75kg · 常穿 M 码）与「退出登录」。
5. 点击「退出登录」并确认，回到 `/login`。
6. 刷新页面，仍停留在 `/login`（token 已清除）。

- [ ] **Step 5: 提交实现代码**

```bash
cd /d/develop/graduation-project-new
git add -A
git commit -m "feat: complete M0 project skeleton"
```

Expected: 提交成功；`git status --short` 为空。

- [ ] **Step 6: 取当前提交短哈希**

```bash
git rev-parse --short HEAD
```

Expected: 7 位短哈希，例如 `a1b2c3d`。

- [ ] **Step 7: 更新 `docs/progress.md`**

把「最后更新」保持为 `2026-11-13`，M0 行改为：

```markdown
| M0 | 项目骨架：配置、DB、认证、前端壳、测试基线 | 已完成 | <第 6 步的短哈希> |
```

在「模块记录」标题下方、记录模板上方加入：

```markdown
## 2026-11-13 · M0 项目骨架

- 状态：已完成
- 本次目标：搭好前后端骨架，打通登录链路，登录后显示「AI 找货 / 我的」两个 Tab。
- 完成内容：
  - 后端：FastAPI + PostgreSQL + Alembic；users 表；注册、登录、当前用户接口；健康检查；演示账号种子脚本。
  - 前端：Vue 3 + Vite + TypeScript + Vant 4；登录/注册页；双 Tab 布局；鉴权路由守卫；Axios 自动带 token 与 401 退出。
  - 测试：pytest 覆盖健康检查、迁移、密码/JWT、注册登录、种子脚本；Playwright 覆盖登录后双 Tab。
  - 工程：git 初始化；`.gitignore` 排除商品图与 node_modules；Docker 开发数据库；README。
- 改动文件 / 目录：
  - `backend/app/`、`backend/alembic/`、`backend/scripts/`、`backend/tests/`
  - `frontend/src/`、`frontend/tests/`
  - `deploy/docker-compose.dev.yml`、`deploy/initdb/`
  - `.gitignore`、`README.md`
- DB 迁移：`20261113_0001_create_users`
- 新增环境变量：`DATABASE_URL`、`TEST_DATABASE_URL`、`JWT_SECRET_KEY`、`JWT_ALGORITHM`、`JWT_EXPIRE_MINUTES`、`CORS_ORIGINS`
- 测试与验收：
  - 命令：`cd backend && python -m pytest -v`；`cd frontend && npm run build`；`cd frontend && npm run test:e2e`
  - 结果：后端 `19 passed`；前端构建成功；E2E `1 passed`；手工验收 6 步通过。
- 遗留问题：
  - 登录态为 localStorage JWT，无 refresh token；改密码/找回密码/OAuth/限流均未实现。
  - `PATCH /api/users/me` 个人资料编辑未实现。
  - 统一业务错误码、SSE/WebSocket 契约留到后续模块。
  - `backend/static/products` 本地备份仍未执行。
- 下一模块依赖：M1 可直接复用 users 表、`get_current_user` 依赖、Axios 客户端、Pinia 认证 store、双 Tab 布局。
- commit：`<第 6 步的短哈希>`
```

把上面两处 `<第 6 步的短哈希>` 替换为第 6 步输出的实际短哈希。

- [ ] **Step 8: 更新 `docs/implementation-handoff.md` 当前状态**

把「前置状态（2026-11-13）」一行改为：

```markdown
- 前置状态（2026-11-13）：`git` 已初始化；M0 已完成；商品图本地备份尚未执行。
```

把「主项目业务代码尚未开始；目前只有独立工具 `tools/image-batch`。」改为：

```markdown
- 主项目骨架已完成（M0）：认证、双 Tab 空壳、数据库迁移与测试基线可用；下一步进入 M1 商品域。
```

把「下一步」一节改为：

```markdown
## 下一步

新窗口先读：

- `docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md`（重点 §7、§8、§10.2、§11.1.3）
- `docs/superpowers/plans/2026-11-13-m0-project-skeleton.md`（已完成，作为基线参考）
- `docs/implementation-handoff.md`
- `docs/progress.md`（M0 记录）

然后为 M1「商品域 + 种子数据 + 商品详情」写实施计划：categories/products/product_skus/favorites 表、300 商品种子数据、商品列表/详情接口、商品详情页与收藏。
```

- [ ] **Step 9: 提交文档并打 tag**

```bash
cd /d/develop/graduation-project-new
git add docs/progress.md docs/implementation-handoff.md
git commit -m "docs: record M0 progress"
git tag -a m0 -m "M0 project skeleton"
git log --oneline -3
```

Expected: 最近两条为 `docs: record M0 progress` 与 `feat: complete M0 project skeleton`；`git tag` 列出 `m0`。

---

## 3. 完成标准自检

| 验收项 | 对应任务 |
|---|---|
| Git 仓库与忽略规则 | Task 1 |
| PostgreSQL 16 + pgvector 开发库 | Task 2 |
| FastAPI 骨架、配置、健康检查 | Task 3 |
| users 表与 Alembic 迁移 | Task 4 |
| bcrypt + JWT | Task 5 |
| 注册 / 登录 / 当前用户 | Task 6、7 |
| 演示账号 demo / demo123 | Task 8 |
| Vue 3 + Vite + TS + Vant 脚手架 | Task 9 |
| JWT 存储、Axios 拦截器、Pinia | Task 10 |
| 登录页 / 注册页（按 mockup 视觉、Vant 重写） | Task 11 |
| 双 Tab 空壳与路由守卫 | Task 12 |
| 只做 4 个页面，不提前实现其余页面 | Task 9~12 |
| Playwright 登录 E2E | Task 13 |
| README | Task 14 |
| 全量测试、进度记录、tag | Task 15 |
