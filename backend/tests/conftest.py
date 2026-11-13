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
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.main import app
from app.modules.catalog.models import Category, Product, ProductSku

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


@pytest.fixture
def sample_catalog(clean_catalog):
    """创建一个最小商品集（2 商品、3 SKU），供交易域测试使用。"""
    from decimal import Decimal

    async def _create() -> dict:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                category = Category(
                    name="测试服装",
                    slug="test-clothing",
                    level=1,
                    sort_order=0,
                )
                session.add(category)
                await session.flush()

                product_a = Product(
                    product_code="TEST-A",
                    category_id=category.id,
                    title="测试衬衫",
                    price=Decimal("100.00"),
                    main_image="/static/products/test-a.png",
                    status="on_sale",
                    attributes={},
                    images=[],
                )
                product_b = Product(
                    product_code="TEST-B",
                    category_id=category.id,
                    title="测试帽子",
                    price=Decimal("50.00"),
                    main_image="/static/products/test-b.png",
                    status="on_sale",
                    attributes={},
                    images=[],
                )
                session.add_all([product_a, product_b])
                await session.flush()

                sku_a = ProductSku(
                    product_id=product_a.id,
                    color="蓝色",
                    size="M",
                    stock=10,
                    sku_code="TEST-A-BLUE-M",
                )
                sku_a_alt = ProductSku(
                    product_id=product_a.id,
                    color="蓝色",
                    size="L",
                    stock=3,
                    sku_code="TEST-A-BLUE-L",
                )
                sku_b = ProductSku(
                    product_id=product_b.id,
                    color="黑色",
                    size="均码",
                    stock=5,
                    sku_code="TEST-B-BLACK-F",
                )
                session.add_all([sku_a, sku_a_alt, sku_b])
                await session.commit()
                return {
                    "category_id": category.id,
                    "product_a_id": product_a.id,
                    "product_b_id": product_b.id,
                    "sku_a_id": sku_a.id,
                    "sku_a_alt_id": sku_a_alt.id,
                    "sku_b_id": sku_b.id,
                }
        finally:
            await engine.dispose()

    data = asyncio.run(_create())
    yield data


@pytest.fixture
def execute_sql():
    """在测试库执行一条 SQL，用于构造库存/超时等边界状态。"""

    def _execute(query: str, params: dict | None = None) -> None:
        async def _run() -> None:
            engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
            try:
                async with engine.begin() as connection:
                    await connection.execute(text(query), params or {})
            finally:
                await engine.dispose()

        asyncio.run(_run())

    return _execute


@pytest.fixture
def agent_token(client, execute_sql):
    """注册测试用户并把角色改为 agent，返回登录 token。"""
    username = "agent_test"
    payload = {"username": username, "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    execute_sql(
        "UPDATE users SET role = 'agent' WHERE username = :username",
        {"username": username},
    )
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return response.json()["access_token"]
