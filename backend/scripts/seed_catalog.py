"""把 seeds/catalog/*.json 导入数据库；重复执行幂等。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import AsyncSessionLocal, engine
from app.modules.catalog.models import Category, Product, ProductSku

BACKEND_DIR = Path(__file__).resolve().parents[1]
CATEGORY_FILE = BACKEND_DIR / "seeds" / "catalog" / "categories.json"
PRODUCT_FILE = BACKEND_DIR / "seeds" / "catalog" / "products.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(categories: list[dict[str, Any]], products: list[dict[str, Any]]) -> None:
    parents = [item for item in categories if item["level"] == 1]
    leaves = [item for item in categories if item["level"] == 2]
    if len(parents) != 4 or len(leaves) != 34:
        raise SystemExit(f"品类数错误：{len(parents)} 一级 / {len(leaves)} 叶子")

    slugs = [item["slug"] for item in categories]
    if len(set(slugs)) != len(slugs):
        raise SystemExit("品类 slug 重复")
    parent_slugs = {item["slug"] for item in parents}
    leaf_slugs = {item["slug"] for item in leaves}
    for leaf in leaves:
        if leaf["parent_slug"] not in parent_slugs:
            raise SystemExit(f"叶子父级不存在：{leaf['slug']}")

    if len(products) != 300:
        raise SystemExit(f"商品数应为 300，实际 {len(products)}")
    codes = [item["product_code"] for item in products]
    if len(set(codes)) != len(codes):
        raise SystemExit("product_code 重复")

    seen_image_names: set[str] = set()
    total_skus = 0
    for product in products:
        if product["category_slug"] not in leaf_slugs:
            raise SystemExit(f"商品品类不是叶子：{product['product_code']}")
        if product["original_price"] < product["price"]:
            raise SystemExit(f"original_price 小于 price：{product['product_code']}")
        image_path = (
            BACKEND_DIR / "static" / product["main_image"].removeprefix("/static/")
        )
        if not image_path.exists():
            raise SystemExit(f"商品图不存在：{image_path}")
        if image_path.name in seen_image_names:
            raise SystemExit(f"商品图重复引用：{image_path.name}")
        seen_image_names.add(image_path.name)
        if not product["skus"]:
            raise SystemExit(f"商品没有 SKU：{product['product_code']}")
        if len(product["skus"]) != len(product["attributes"].get("size", [])):
            raise SystemExit(f"SKU 数与 size 不一致：{product['product_code']}")
        colors = {sku["color"] for sku in product["skus"]}
        if len(colors) != 1:
            raise SystemExit(f"一商品只能有一个颜色：{product['product_code']}")
        sku_codes = [sku["sku_code"] for sku in product["skus"]]
        if len(set(sku_codes)) != len(sku_codes):
            raise SystemExit(f"sku_code 重复：{product['product_code']}")
        total_skus += len(product["skus"])

    if total_skus != 1108:
        raise SystemExit(f"SKU 数应为 1108，实际 {total_skus}")
    if len(seen_image_names) != 300:
        raise SystemExit(f"图片数应为 300，实际 {len(seen_image_names)}")


async def upsert_categories(
    session, categories: list[dict[str, Any]]
) -> dict[str, int]:
    parents = [item for item in categories if item["level"] == 1]
    leaves = [item for item in categories if item["level"] == 2]
    ids: dict[str, int] = {}

    for item in parents:
        stmt = (
            pg_insert(Category)
            .values(
                slug=item["slug"],
                name=item["name"],
                parent_id=None,
                level=item["level"],
                attribute_schema=item["attribute_schema"],
                size_chart_template=item.get("size_chart_template"),
                sort_order=item.get("sort_order", 0),
            )
            .on_conflict_do_update(
                index_elements=[Category.slug],
                set_={
                    "name": item["name"],
                    "parent_id": None,
                    "level": item["level"],
                    "attribute_schema": item["attribute_schema"],
                    "size_chart_template": item.get("size_chart_template"),
                    "sort_order": item.get("sort_order", 0),
                    "updated_at": func.now(),
                },
            )
            .returning(Category.id)
        )
        ids[item["slug"]] = int(await session.scalar(stmt))

    for item in leaves:
        stmt = (
            pg_insert(Category)
            .values(
                slug=item["slug"],
                name=item["name"],
                parent_id=ids[item["parent_slug"]],
                level=item["level"],
                attribute_schema=item["attribute_schema"],
                size_chart_template=item.get("size_chart_template"),
                sort_order=item.get("sort_order", 0),
            )
            .on_conflict_do_update(
                index_elements=[Category.slug],
                set_={
                    "name": item["name"],
                    "parent_id": ids[item["parent_slug"]],
                    "level": item["level"],
                    "attribute_schema": item["attribute_schema"],
                    "size_chart_template": item.get("size_chart_template"),
                    "sort_order": item.get("sort_order", 0),
                    "updated_at": func.now(),
                },
            )
            .returning(Category.id)
        )
        ids[item["slug"]] = int(await session.scalar(stmt))

    return ids


async def upsert_products(
    session, products: list[dict[str, Any]], category_ids: dict[str, int]
) -> dict[str, int]:
    values = [
        {
            "product_code": product["product_code"],
            "category_id": category_ids[product["category_slug"]],
            "title": product["title"],
            "description": product["description"],
            "brand": product["brand"],
            "price": product["price"],
            "original_price": product["original_price"],
            "main_image": product["main_image"],
            "images": product["images"],
            "attributes": product["attributes"],
            "size_chart": product["size_chart"],
            "status": product["status"],
            "sales_count": product["sales_count"],
        }
        for product in products
    ]
    stmt = pg_insert(Product).values(values)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=[Product.product_code],
        set_={
            "category_id": excluded.category_id,
            "title": excluded.title,
            "description": excluded.description,
            "brand": excluded.brand,
            "price": excluded.price,
            "original_price": excluded.original_price,
            "main_image": excluded.main_image,
            "images": excluded.images,
            "attributes": excluded.attributes,
            "size_chart": excluded.size_chart,
            "status": excluded.status,
            "sales_count": excluded.sales_count,
            "updated_at": func.now(),
        },
    ).returning(Product.id, Product.product_code)
    rows = (await session.execute(stmt)).all()
    return {row.product_code: row.id for row in rows}


async def upsert_skus(
    session, products: list[dict[str, Any]], product_ids: dict[str, int]
) -> None:
    values = []
    all_sku_codes: list[str] = []
    for product in products:
        product_id = product_ids[product["product_code"]]
        for sku in product["skus"]:
            all_sku_codes.append(sku["sku_code"])
            values.append(
                {
                    "product_id": product_id,
                    "color": sku["color"],
                    "size": sku["size"],
                    "stock": sku["stock"],
                    "price_override": sku["price_override"],
                    "sku_code": sku["sku_code"],
                    "status": "active",
                }
            )
    stmt = pg_insert(ProductSku).values(values)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProductSku.sku_code],
        set_={
            "product_id": excluded.product_id,
            "color": excluded.color,
            "size": excluded.size,
            "stock": excluded.stock,
            "price_override": excluded.price_override,
            "status": "active",
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.execute(
        update(ProductSku)
        .where(
            ProductSku.product_id.in_(product_ids.values()),
            ProductSku.sku_code.notin_(all_sku_codes),
        )
        .values(status="inactive", updated_at=func.now())
    )


async def seed_catalog() -> None:
    category_data = load_json(CATEGORY_FILE)["categories"]
    product_data = load_json(PRODUCT_FILE)["products"]
    validate(category_data, product_data)

    async with AsyncSessionLocal() as session:
        category_ids = await upsert_categories(session, category_data)
        product_ids = await upsert_products(session, product_data, category_ids)
        await upsert_skus(session, product_data, product_ids)
        await session.commit()

    parents = sum(1 for item in category_data if item["level"] == 1)
    leaves = sum(1 for item in category_data if item["level"] == 2)
    print(f"品类：{parents} 个一级 + {leaves} 个叶子")
    print(f"商品：{len(product_data)}")
    print(f"SKU：{sum(len(product['skus']) for product in product_data)}")
    print(f"图片：{len(product_data)} 张校验通过")


async def main() -> None:
    try:
        await seed_catalog()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
