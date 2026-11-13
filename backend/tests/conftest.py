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
