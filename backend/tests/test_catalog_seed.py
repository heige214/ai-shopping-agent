import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import asyncpg

BACKEND_DIR = Path(__file__).resolve().parents[1]
CATEGORY_FILE = BACKEND_DIR / "seeds" / "catalog" / "categories.json"
PRODUCT_FILE = BACKEND_DIR / "seeds" / "catalog" / "products.json"


def run_seed() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.seed_catalog"],
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def fetch_counts() -> dict[str, int]:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def _fetch():
        connection = await asyncpg.connect(dsn)
        try:
            return {
                "categories": await connection.fetchval(
                    "SELECT count(*) FROM categories"
                ),
                "parents": await connection.fetchval(
                    "SELECT count(*) FROM categories WHERE level = 1"
                ),
                "leaves": await connection.fetchval(
                    "SELECT count(*) FROM categories WHERE level = 2"
                ),
                "products": await connection.fetchval(
                    "SELECT count(*) FROM products"
                ),
                "skus": await connection.fetchval(
                    "SELECT count(*) FROM product_skus"
                ),
            }
        finally:
            await connection.close()

    return asyncio.run(_fetch())


def test_seed_counts_and_image_files(clean_catalog):
    result = run_seed()
    assert result.returncode == 0, result.stderr
    assert "品类：4 个一级 + 34 个叶子" in result.stdout
    assert "商品：300" in result.stdout
    assert "SKU：1108" in result.stdout
    counts = fetch_counts()
    assert counts == {
        "categories": 38,
        "parents": 4,
        "leaves": 34,
        "products": 300,
        "skus": 1108,
    }

    data = json.loads(PRODUCT_FILE.read_text(encoding="utf-8"))
    products = data["products"]
    assert len(products) == 300
    assert all(product["original_price"] >= product["price"] for product in products)
    assert all(product["images"] == [product["main_image"]] for product in products)
    for product in products:
        image = (
            BACKEND_DIR
            / "static"
            / product["main_image"].removeprefix("/static/")
        )
        assert image.exists(), image
        assert len({sku["color"] for sku in product["skus"]}) == 1


def test_seed_leaf_attributes_match_schema():
    categories = json.loads(CATEGORY_FILE.read_text(encoding="utf-8"))["categories"]
    leaves = {item["slug"]: item for item in categories if item["level"] == 2}
    products = json.loads(PRODUCT_FILE.read_text(encoding="utf-8"))["products"]

    for product in products:
        leaf = leaves[product["category_slug"]]
        assert product["attributes"]["key_features"]
        for attribute in leaf["attribute_schema"]["attributes"]:
            value = product["attributes"].get(attribute["key"])
            assert value in attribute["options"], (
                product["product_code"],
                attribute["key"],
                value,
            )


def test_seed_is_idempotent_and_keeps_favorites(client, clean_catalog):
    first = run_seed()
    assert first.returncode == 0, first.stderr

    client.post(
        "/api/auth/register",
        json={"username": "seed_user", "password": "secret123"},
    )
    token = client.post(
        "/api/auth/login",
        json={"username": "seed_user", "password": "secret123"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    product = client.get("/api/products?page_size=1").json()["items"][0]
    client.post(f"/api/products/{product['id']}/favorite", headers=headers)

    second = run_seed()
    assert second.returncode == 0, second.stderr
    counts = fetch_counts()
    assert counts["products"] == 300
    assert counts["skus"] == 1108
    favorites = client.get("/api/favorites", headers=headers).json()
    assert [item["id"] for item in favorites] == [product["id"]]
