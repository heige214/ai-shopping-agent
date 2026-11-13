"""从 image-batch CSV 生成商品种子 JSON。

默认拒绝覆盖已存在的 products.json；确需重建时加 --force。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
CATEGORY_FILE = BACKEND_DIR / "seeds" / "catalog" / "categories.json"
OUTPUT_FILE = BACKEND_DIR / "seeds" / "catalog" / "products.json"
CSV_DIR = REPO_DIR / "tools" / "image-batch" / "data"
IMAGE_DIR = BACKEND_DIR / "static" / "products"

CSV_FILES = ["服装.csv", "鞋靴.csv", "箱包.csv", "配饰.csv"]
PRICE_RANGES = {
    "clothing": (99, 399),
    "footwear": (129, 499),
    "bags": (89, 599),
    "accessories": (29, 299),
}
BRANDS = {
    "clothing": "慕言 MUYAN",
    "footwear": "行步 XINGBU",
    "bags": "远行 YUANXING",
    "accessories": "点注 DIANZHU",
}
PARENT_BY_NAME = {
    "服装": "clothing",
    "鞋靴": "footwear",
    "箱包": "bags",
    "配饰": "accessories",
}
CLOTHING_SIZES = ["S", "M", "L", "XL", "XXL"]
BAG_SIZES = {
    "双肩包": ["小号", "中号", "大号"],
    "手提包": ["小号", "中号", "大号"],
    "单肩包": ["小号", "中号", "大号"],
    "斜挎包": ["小号", "中号", "大号"],
    "钱包": ["短款", "长款"],
    "行李箱": ["20寸", "24寸", "28寸"],
    "托特包": ["小号", "中号", "大号"],
    "腰包": ["均码"],
}
ACCESSORY_SIZES = {
    "帽子": ["均码"],
    "围巾": ["均码"],
    "腰带": ["S", "M", "L", "XL"],
    "袜子": ["S", "M", "L"],
    "手套": ["S", "M", "L", "XL"],
    "墨镜": ["均码"],
    "项链": ["均码"],
    "手表": ["均码"],
}


def load_categories() -> dict[str, Any]:
    return json.loads(CATEGORY_FILE.read_text(encoding="utf-8"))


def _seed_int(key: str) -> int:
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)


def deterministic_price(product_code: str, parent_slug: str) -> int:
    minimum, maximum = PRICE_RANGES[parent_slug]
    rng = random.Random(_seed_int(product_code))
    price = rng.randint(minimum // 10, maximum // 10) * 10 + 9
    if price > maximum:
        price -= 10
    return max(minimum, price)


def deterministic_original_price(product_code: str, price: int) -> float:
    rng = random.Random(_seed_int(f"{product_code}:original"))
    multiplier = rng.choice([1.2, 1.3, 1.4, 1.5])
    return round(price * multiplier, 2)


def deterministic_sales_count(product_code: str) -> int:
    return random.Random(_seed_int(f"{product_code}:sales")).randint(20, 800)


def deterministic_stock(sku_code: str) -> int:
    return random.Random(_seed_int(f"{sku_code}:stock")).randint(0, 50)


def sizes_for(parent_slug: str, gender: str, leaf_name: str) -> list[str]:
    if parent_slug == "clothing":
        return list(CLOTHING_SIZES)
    if parent_slug == "footwear":
        if gender == "女":
            return ["35", "36", "37", "38", "39"]
        return ["39", "40", "41", "42", "43"]
    if parent_slug == "bags":
        return list(BAG_SIZES[leaf_name])
    if parent_slug == "accessories":
        return list(ACCESSORY_SIZES[leaf_name])
    raise ValueError(parent_slug)


def assign_leaf_attributes(leaf: dict[str, Any], key_feature: str) -> dict[str, str]:
    tokens = [token.strip() for token in key_feature.split("、") if token.strip()]
    values: dict[str, str] = {}
    for key, rule in leaf.get("attribute_rules", {}).items():
        token_map = rule.get("tokens", {})
        value = rule["default"]
        for token in tokens:
            if token in token_map:
                value = token_map[token]
                break
        values[key] = value
    return values


def build_title(row: dict[str, str]) -> str:
    feature = row["key_feature"].split("、")[0]
    material = row["material"].split("+")[0]
    return f"{row['color']}{material}{feature}{row['subcategory']}"


def build_description(row: dict[str, str], title: str) -> str:
    if row["category"] == "服装":
        return (
            f"{title}。{row['material']}材质，{row['fit']}版型，{row['thickness']}，"
            f"{row['style']}风格，适用性别：{row['gender']}。"
            f"设计细节：{row['key_feature']}。"
        )
    if row["category"] == "鞋靴":
        return (
            f"{title}。{row['material']}鞋面，{row['style']}风格，"
            f"适用性别：{row['gender']}。设计细节：{row['key_feature']}。"
        )
    return (
        f"{title}。{row['material']}材质，{row['style']}风格，"
        f"适用性别：{row['gender']}。设计细节：{row['key_feature']}。"
    )


def season_for(row: dict[str, str]) -> list[str]:
    if row["category"] != "服装":
        return []
    if row["thickness"] == "薄款":
        seasons = ["春", "夏"]
    elif row["thickness"] == "加厚":
        seasons = ["冬"]
    else:
        seasons = ["春", "秋"]
    if row["style"] == "度假" and "夏" not in seasons:
        seasons.append("夏")
    if row["style"] == "户外":
        for season in ("春", "秋"):
            if season not in seasons:
                seasons.append(season)
    return seasons


def size_chart_for(
    categories_by_slug: dict[str, dict[str, Any]],
    parent_slug: str,
    sizes: list[str],
) -> dict[str, Any] | None:
    if parent_slug not in {"clothing", "footwear"}:
        return None
    template = categories_by_slug[parent_slug]["size_chart_template"]
    rows = [row for row in template["rows"] if row["size"] in sizes]
    return {"type": template["type"], "unit": template["unit"], "rows": rows}


def build_products() -> list[dict[str, Any]]:
    data = load_categories()
    categories_by_slug = {item["slug"]: item for item in data["categories"]}
    leaves_by_parent_name = {
        (categories_by_slug[item["parent_slug"]]["name"], item["name"]): item
        for item in data["categories"]
        if item["level"] == 2
    }

    products: list[dict[str, Any]] = []
    missing_images: list[str] = []

    for csv_name in CSV_FILES:
        with (CSV_DIR / csv_name).open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        for row in rows:
            product_code = row["id"]
            parent_slug = PARENT_BY_NAME[row["category"]]
            leaf = leaves_by_parent_name[(row["category"], row["subcategory"])]
            image_name = f"{product_code}_{row['color']}.png"
            if not (IMAGE_DIR / image_name).exists():
                missing_images.append(image_name)
            image_url = f"/static/products/{image_name}"

            sizes = sizes_for(parent_slug, row["gender"], row["subcategory"])
            leaf_attributes = assign_leaf_attributes(leaf, row["key_feature"])
            attributes: dict[str, Any] = {
                "color": row["color"],
                "material": row["material"],
                "style": row["style"],
                "gender": row["gender"],
                "size": sizes,
                "key_features": [
                    token.strip()
                    for token in row["key_feature"].split("、")
                    if token.strip()
                ],
                **leaf_attributes,
            }
            if parent_slug == "clothing":
                attributes["fit"] = row["fit"]
                attributes["thickness"] = row["thickness"]
                attributes["season"] = season_for(row)

            price = deterministic_price(product_code, parent_slug)
            original_price = deterministic_original_price(product_code, price)
            if original_price <= price:
                original_price = float(price + 10)
            skus = []
            for size in sizes:
                sku_code = f"{product_code}-{row['color']}-{size}"
                skus.append(
                    {
                        "color": row["color"],
                        "size": size,
                        "stock": deterministic_stock(sku_code),
                        "sku_code": sku_code,
                        "price_override": None,
                    }
                )

            title = build_title(row)
            products.append(
                {
                    "product_code": product_code,
                    "category_slug": leaf["slug"],
                    "title": title,
                    "description": build_description(row, title),
                    "brand": BRANDS[parent_slug],
                    "price": float(price),
                    "original_price": float(original_price),
                    "main_image": image_url,
                    "images": [image_url],
                    "attributes": attributes,
                    "size_chart": size_chart_for(categories_by_slug, parent_slug, sizes),
                    "status": "on_sale",
                    "sales_count": deterministic_sales_count(product_code),
                    "skus": skus,
                }
            )

    if missing_images:
        raise SystemExit(
            "缺少商品图，请先补齐 backend/static/products：\n"
            + "\n".join(missing_images)
        )
    if len(products) != 300:
        raise SystemExit(f"商品数应为 300，实际 {len(products)}")
    total_skus = sum(len(product["skus"]) for product in products)
    if total_skus != 1108:
        raise SystemExit(f"SKU 数应为 1108，实际 {total_skus}")
    return products


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force", action="store_true", help="覆盖已存在的 products.json"
    )
    args = parser.parse_args()

    if OUTPUT_FILE.exists() and not args.force:
        print(f"{OUTPUT_FILE} 已存在，未覆盖；确需重建请加 --force")
        return

    products = build_products()
    OUTPUT_FILE.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_from": "tools/image-batch/data/*.csv",
                "products": products,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"已生成 {OUTPUT_FILE}")
    print(f"商品：{len(products)}")
    print(f"SKU：{sum(len(product['skus']) for product in products)}")
    print(f"图片：{len(products)} 张校验通过")


if __name__ == "__main__":
    main()
