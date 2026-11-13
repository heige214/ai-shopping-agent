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

# 防止误把开发库当成测试库：clean_users 会清空 users 表
_test_database_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
if not _test_database_name.endswith("_test"):
    raise RuntimeError(
        f"TEST_DATABASE_URL 必须指向名称以 _test 结尾的测试库，当前为 {_test_database_name!r}"
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-key-for-pytest-only-0123456789abcdef"
)
os.environ.setdefault("JWT_EXPIRE_MINUTES", "10080")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5175")

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


@pytest.fixture
def clean_users(migrated_database):
    """数据库/API 测试开始前清空 users 表；纯单元测试不依赖此 fixture。"""

    async def _clean() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE TABLE users RESTART IDENTITY CASCADE")
            )
        await engine.dispose()

    asyncio.run(_clean())
    yield


@pytest.fixture
def client(clean_users):
    """每个测试使用独立 TestClient；会先清空 users 表。"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def clean_catalog(migrated_database):
    """清空商品域四表；不影响 users。"""

    async def _clean() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE favorites, product_skus, products, categories "
                    "RESTART IDENTITY CASCADE"
                )
            )
        await engine.dispose()

    asyncio.run(_clean())
    yield


@pytest.fixture
def seeded_catalog(clean_catalog):
    """导入已提交的商品种子 JSON。"""
    result = subprocess.run(
        [sys.executable, "-m", "scripts.seed_catalog"],
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    yield
