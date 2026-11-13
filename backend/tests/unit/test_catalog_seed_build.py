from scripts.build_catalog_seed import (
    assign_leaf_attributes,
    build_products,
    deterministic_price,
    sizes_for,
)


def test_sizes_for_rules():
    assert sizes_for("clothing", "男", "衬衫") == ["S", "M", "L", "XL", "XXL"]
    assert sizes_for("footwear", "女", "高跟鞋") == ["35", "36", "37", "38", "39"]
    assert sizes_for("footwear", "男", "运动鞋") == ["39", "40", "41", "42", "43"]
    assert sizes_for("bags", "中性", "钱包") == ["短款", "长款"]
    assert sizes_for("bags", "中性", "腰包") == ["均码"]
    assert sizes_for("accessories", "女", "腰带") == ["S", "M", "L", "XL"]
    assert sizes_for("accessories", "中性", "墨镜") == ["均码"]


def test_price_is_deterministic_and_within_range():
    first = deterministic_price("C001", "clothing")
    second = deterministic_price("C001", "clothing")
    assert first == second
    assert 99 <= first <= 399
    assert first % 10 == 9


def test_assign_leaf_attributes_uses_token_and_default():
    leaf = {
        "slug": "shirts",
        "attribute_rules": {
            "collar_type": {"tokens": {"翻领": "翻领"}, "default": "立领"},
            "sleeve_length": {"tokens": {"短袖": "短袖"}, "default": "长袖"},
            "pattern": {
                "tokens": {"条纹": "条纹", "格纹": "格纹"},
                "default": "纯色",
            },
        },
    }
    assert assign_leaf_attributes(leaf, "翻领、单排扣、左胸口袋") == {
        "collar_type": "翻领",
        "sleeve_length": "长袖",
        "pattern": "纯色",
    }


def test_build_products_returns_300_products_and_1108_skus():
    products = build_products()
    assert len(products) == 300
    assert sum(len(product["skus"]) for product in products) == 1108
    assert {product["product_code"][0] for product in products} == {
        "C",
        "S",
        "B",
        "A",
    }
    assert all(product["original_price"] >= product["price"] for product in products)
    assert all(product["images"] == [product["main_image"]] for product in products)
    assert all(product["attributes"]["key_features"] for product in products)
    assert all(
        len({sku["color"] for sku in product["skus"]}) == 1 for product in products
    )
