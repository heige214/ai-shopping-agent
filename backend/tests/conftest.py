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
# 测试永不请求真实 DashScope；fake 提供确定性 LLM 与 embedding
os.environ.setdefault("AI_PROVIDER", "fake")
os.environ["DASHSCOPE_API_KEY"] = ""

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
def guide_catalog(clean_catalog):
    """导购测试用商品集：衬衫 10、运动鞋 15、双肩包 15，含尺码表与 fake 向量。"""
    from decimal import Decimal

    from app.ai.embeddings import FakeEmbeddingClient
    from app.modules.catalog.models import Category, Product

    clothing_chart = {
        "type": "clothing",
        "unit": "cm",
        "rows": [
            {"size": "S", "height": [155, 165], "weight": [45, 55]},
            {"size": "M", "height": [165, 172], "weight": [55, 65]},
            {"size": "L", "height": [170, 178], "weight": [65, 75]},
            {"size": "XL", "height": [176, 184], "weight": [75, 85]},
        ],
    }
    shoes_chart = {
        "type": "shoes",
        "unit": "mm",
        "rows": [
            {"size": "39", "foot_length": [245, 250]},
            {"size": "40", "foot_length": [250, 255]},
            {"size": "41", "foot_length": [255, 260]},
        ],
    }
    shirt_specs = [
        ("G01", "蓝色纯棉薄款衬衫", "蓝色", "纯棉", "薄款", 109),
        ("G02", "蓝色亚麻薄款衬衫", "蓝色", "亚麻", "薄款", 129),
        ("G03", "黑色纯棉常规衬衫", "黑色", "纯棉", "常规", 169),
        ("G04", "白色亚麻薄款衬衫", "白色", "亚麻", "薄款", 199),
        ("G05", "蓝色聚酯纤维加厚衬衫", "蓝色", "聚酯纤维", "加厚", 259),
        ("G06", "米白棉麻薄款衬衫", "米白", "棉麻", "薄款", 149),
        ("G07", "藏青纯棉常规衬衫", "藏青", "纯棉", "常规", 189),
        ("G08", "浅蓝亚麻常规衬衫", "浅蓝", "亚麻", "常规", 139),
        ("G09", "卡其真丝薄款衬衫", "卡其", "真丝", "薄款", 309),
        ("G10", "棕色牛津纺常规衬衫", "棕色", "牛津纺", "常规", 389),
    ]
    colors = ["黑色", "白色", "灰色", "蓝色", "米白"]
    sneaker_specs = [
        (
            f"S{index:02d}",
            f"{colors[index % len(colors)]}运动鞋 {index}",
            colors[index % len(colors)],
            "网布+橡胶" if index % 2 else "皮革",
            159 + index * 20,
        )
        for index in range(1, 16)
    ]
    backpack_specs = [
        (
            f"B{index:02d}",
            f"{colors[index % len(colors)]}双肩包 {index}",
            colors[index % len(colors)],
            "帆布" if index % 2 else "尼龙",
            89 + index * 20,
        )
        for index in range(1, 16)
    ]

    async def _create() -> dict:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        embedder = FakeEmbeddingClient()
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                clothing = Category(
                    name="服装", slug="clothing", level=1, sort_order=1
                )
                footwear = Category(
                    name="鞋靴", slug="footwear", level=1, sort_order=2
                )
                bags = Category(
                    name="箱包", slug="bags", level=1, sort_order=3
                )
                session.add_all([clothing, footwear, bags])
                await session.flush()

                shirts = Category(
                    name="衬衫",
                    slug="shirts",
                    level=2,
                    parent_id=clothing.id,
                    sort_order=1,
                    size_chart_template=clothing_chart,
                )
                sneakers = Category(
                    name="运动鞋",
                    slug="sneakers",
                    level=2,
                    parent_id=footwear.id,
                    sort_order=1,
                )
                backpacks = Category(
                    name="双肩包",
                    slug="backpacks",
                    level=2,
                    parent_id=bags.id,
                    sort_order=1,
                )
                session.add_all([shirts, sneakers, backpacks])
                await session.flush()

                records: list[Product] = []
                for code, title, color, material, thickness, price in shirt_specs:
                    records.append(
                        Product(
                            product_code=code,
                            category_id=shirts.id,
                            title=title,
                            brand="测试品牌",
                            price=Decimal(str(price)),
                            main_image=f"/static/products/{code}.png",
                            attributes={
                                "color": color,
                                "material": material,
                                "thickness": thickness,
                            },
                            size_chart=clothing_chart,
                            status="on_sale",
                            sales_count=100,
                        )
                    )
                for code, title, color, material, price in sneaker_specs:
                    records.append(
                        Product(
                            product_code=code,
                            category_id=sneakers.id,
                            title=title,
                            brand="测试品牌",
                            price=Decimal(str(price)),
                            main_image=f"/static/products/{code}.png",
                            attributes={
                                "color": color,
                                "material": material,
                                "thickness": "常规",
                            },
                            size_chart=shoes_chart,
                            status="on_sale",
                            sales_count=80,
                        )
                    )
                for code, title, color, material, price in backpack_specs:
                    records.append(
                        Product(
                            product_code=code,
                            category_id=backpacks.id,
                            title=title,
                            brand="测试品牌",
                            price=Decimal(str(price)),
                            main_image=f"/static/products/{code}.png",
                            attributes={
                                "color": color,
                                "material": material,
                            },
                            status="on_sale",
                            sales_count=60,
                        )
                    )
                session.add_all(records)
                await session.flush()

                # 加购测试需要 SKU：衬衫 S/M/L/XL、运动鞋 39/40/41、双肩包均码
                skus = []
                for record in records:
                    if record.product_code.startswith("G"):
                        sizes = ["S", "M", "L", "XL"]
                    elif record.product_code.startswith("S"):
                        sizes = ["39", "40", "41"]
                    else:
                        sizes = ["均码"]
                    for size in sizes:
                        skus.append(
                            ProductSku(
                                product_id=record.id,
                                color=record.attributes.get("color", "黑色"),
                                size=size,
                                stock=10,
                                sku_code=f"{record.product_code}-{size}",
                            )
                        )
                session.add_all(skus)

                texts = [
                    (
                        f"{record.title} {record.brand or ''} "
                        + " ".join(
                            f"{key}{value}"
                            for key, value in (record.attributes or {}).items()
                        )
                    )
                    for record in records
                ]
                vectors = await embedder.embed_texts(texts)
                for record, vector in zip(records, vectors):
                    record.embedding = vector
                await session.commit()
                return {
                    "category_ids": {
                        "clothing": clothing.id,
                        "shirts": shirts.id,
                        "footwear": footwear.id,
                        "sneakers": sneakers.id,
                        "bags": bags.id,
                        "backpacks": backpacks.id,
                    },
                    "product_ids": {
                        record.product_code: record.id for record in records
                    },
                    "titles": {
                        record.product_code: record.title for record in records
                    },
                }
        finally:
            await engine.dispose()

    return asyncio.run(_create())


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


@pytest.fixture
def clean_support(migrated_database):
    """清空知识域与客服域五表，不影响 users/catalog。"""

    async def _clean() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE support_tickets, chat_messages, chat_sessions, "
                    "knowledge_chunks, knowledge_documents RESTART IDENTITY CASCADE"
                )
            )
        await engine.dispose()

    asyncio.run(_clean())
    yield


@pytest.fixture
def sample_knowledge(clean_support, sample_catalog):
    """为 sample_catalog 造最小知识集（商品/一级品类/平台/干扰项）。"""
    from app.ai.embeddings import FakeEmbeddingClient
    from app.modules.catalog.models import Category
    from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument
    from scripts.seed_knowledge import build_search_text

    async def _create() -> dict:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        embedder = FakeEmbeddingClient()
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                other_category = Category(
                    name="测试鞋靴",
                    slug="test-footwear",
                    level=1,
                    sort_order=1,
                )
                session.add(other_category)
                await session.flush()

                detail_doc = KnowledgeDocument(
                    scope="product",
                    product_id=sample_catalog["product_a_id"],
                    category_id=sample_catalog["category_id"],
                    doc_type="detail",
                    title="测试衬衫 · 商品详情",
                    source="seed",
                    status="active",
                )
                size_doc = KnowledgeDocument(
                    scope="product",
                    product_id=sample_catalog["product_a_id"],
                    category_id=sample_catalog["category_id"],
                    doc_type="size",
                    title="测试衬衫 · 尺码指南",
                    source="seed",
                    status="active",
                )
                faq_doc = KnowledgeDocument(
                    scope="product",
                    product_id=sample_catalog["product_a_id"],
                    category_id=sample_catalog["category_id"],
                    doc_type="faq",
                    title="测试衬衫 · 常见问题",
                    source="seed",
                    status="active",
                )
                category_doc = KnowledgeDocument(
                    scope="category",
                    product_id=None,
                    category_id=sample_catalog["category_id"],
                    doc_type="care",
                    title="测试服装 · 洗护指南",
                    source="seed",
                    status="active",
                )
                platform_doc = KnowledgeDocument(
                    scope="platform",
                    product_id=None,
                    category_id=None,
                    doc_type="policy",
                    title="平台规则 · 发货时效",
                    source="manual",
                    status="active",
                )
                other_product_doc = KnowledgeDocument(
                    scope="product",
                    product_id=sample_catalog["product_b_id"],
                    category_id=sample_catalog["category_id"],
                    doc_type="detail",
                    title="测试帽子 · 商品详情",
                    source="seed",
                    status="active",
                )
                other_category_doc = KnowledgeDocument(
                    scope="category",
                    product_id=None,
                    category_id=other_category.id,
                    doc_type="care",
                    title="测试鞋靴 · 洗护指南",
                    source="seed",
                    status="active",
                )
                session.add_all(
                    [
                        detail_doc,
                        size_doc,
                        faq_doc,
                        category_doc,
                        platform_doc,
                        other_product_doc,
                        other_category_doc,
                    ]
                )
                await session.flush()

                specs = [
                    (
                        detail_doc,
                        "测试衬衫的材质是纯棉，版型常规，适合春夏穿着。",
                        {"section": "概述", "doc_type": "detail"},
                    ),
                    (
                        size_doc,
                        "测试衬衫尺码表：M 码适合身高 165-172cm，体重 55-65kg。",
                        {"section": "尺码表", "doc_type": "size"},
                    ),
                    (
                        faq_doc,
                        "测试衬衫怎么洗？棉质建议 30℃ 以下冷水洗涤，反面晾晒。",
                        {
                            "question": "测试衬衫怎么洗？",
                            "section": "care",
                            "doc_type": "faq",
                        },
                    ),
                    (
                        category_doc,
                        "棉质服装建议 30℃ 以下冷水洗涤，反面晾晒，避免高温烘干。",
                        {"section": "通用洗护", "doc_type": "care"},
                    ),
                    (
                        platform_doc,
                        "平台商品付款后 48 小时内发货，支持 7 天无理由退换。",
                        {"section": "发货时效", "doc_type": "policy"},
                    ),
                    (
                        other_product_doc,
                        "测试帽子的材质是涤纶，适合夏季佩戴。",
                        {"section": "概述", "doc_type": "detail"},
                    ),
                    (
                        other_category_doc,
                        "鞋靴建议软刷清洁，阴干，避免暴晒。",
                        {"section": "通用洗护", "doc_type": "care"},
                    ),
                ]
                chunks = []
                for index, (document, content, meta) in enumerate(specs, start=1):
                    vectors = await embedder.embed_texts([content])
                    chunks.append(
                        KnowledgeChunk(
                            document_id=document.id,
                            product_id=document.product_id,
                            category_id=document.category_id,
                            content=content,
                            search_text=build_search_text(
                                content, meta.get("question")
                            ),
                            embedding=vectors[0],
                            meta={**meta, "seed_key": f"sample:{index}"},
                        )
                    )
                session.add_all(chunks)
                await session.commit()
                return {
                    **sample_catalog,
                    "other_category_id": other_category.id,
                    "detail_content": specs[0][1],
                    "size_content": specs[1][1],
                    "platform_content": specs[4][1],
                }
        finally:
            await engine.dispose()

    return asyncio.run(_create())
