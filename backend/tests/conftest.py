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
