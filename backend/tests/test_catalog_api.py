def login(client, username: str = "catalog_user") -> str:
    client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123", "nickname": "测试"},
    )
    response = client.post(
        "/api/auth/login", json={"username": username, "password": "secret123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def first_product(client) -> dict:
    return client.get("/api/products?page_size=1").json()["items"][0]


def first_clothing_product(client) -> dict:
    roots = client.get("/api/categories").json()
    clothing_id = roots[0]["id"]
    return client.get(
        f"/api/products?category_id={clothing_id}&page_size=1"
    ).json()["items"][0]


def test_categories_tree_has_merged_schema(client, seeded_catalog):
    response = client.get("/api/categories")
    assert response.status_code == 200
    roots = response.json()
    assert [item["name"] for item in roots] == ["服装", "鞋靴", "箱包", "配饰"]
    assert all(len(item["children"]) >= 8 for item in roots)

    clothing = roots[0]
    shirts = next(item for item in clothing["children"] if item["name"] == "衬衫")
    keys = [item["key"] for item in shirts["attribute_schema"]["attributes"]]
    assert "color" in keys
    assert "material" in keys
    assert "collar_type" in keys
    assert "key_features" in keys
    assert shirts["size_chart_template"]["type"] == "clothing"

    key_features = next(
        item
        for item in shirts["attribute_schema"]["attributes"]
        if item["key"] == "key_features"
    )
    assert key_features["type"] == "tags"
    assert key_features["filterable"] is False


def test_products_pagination_and_parent_category_include_children(
    client, seeded_catalog
):
    roots = client.get("/api/categories").json()
    clothing_id = roots[0]["id"]
    shirts_id = next(
        item["id"] for item in roots[0]["children"] if item["name"] == "衬衫"
    )

    page = client.get("/api/products?page=1&page_size=10").json()
    assert page["total"] == 300
    assert page["page"] == 1
    assert page["page_size"] == 10
    assert len(page["items"]) == 10

    by_parent = client.get(
        f"/api/products?category_id={clothing_id}&page_size=50"
    ).json()
    assert by_parent["total"] == 75

    by_leaf = client.get(
        f"/api/products?category_id={shirts_id}&page_size=50"
    ).json()
    assert by_leaf["total"] == 10
    assert all(item["category_id"] == shirts_id for item in by_leaf["items"])


def test_products_search_and_sort(client, seeded_catalog):
    search = client.get("/api/products?q=衬衫&page_size=50").json()
    assert search["total"] > 0
    assert all("衬衫" in item["title"] for item in search["items"])

    empty = client.get("/api/products?q=不存在的商品").json()
    assert empty["total"] == 0
    assert empty["items"] == []

    price_asc = client.get("/api/products?sort=price_asc&page_size=50").json()
    prices = [item["price"] for item in price_asc["items"]]
    assert prices == sorted(prices)

    price_desc = client.get("/api/products?sort=price_desc&page_size=50").json()
    prices = [item["price"] for item in price_desc["items"]]
    assert prices == sorted(prices, reverse=True)

    recommended = client.get("/api/products?sort=recommended&page_size=50").json()
    sales = [item["sales_count"] for item in recommended["items"]]
    assert sales == sorted(sales, reverse=True)

    invalid_sort = client.get("/api/products?sort=unknown")
    assert invalid_sort.status_code == 422


def test_products_unknown_category_returns_404(client, seeded_catalog):
    response = client.get("/api/products?category_id=999999")
    assert response.status_code == 404


def test_product_detail_is_public_and_contains_skus_and_size_chart(
    client, seeded_catalog
):
    product = first_clothing_product(client)
    response = client.get(f"/api/products/{product['id']}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == product["id"]
    assert detail["product_code"] == product["product_code"]
    assert detail["is_favorited"] is False
    assert len(detail["skus"]) == 5
    assert detail["attribute_schema"]["attributes"]
    assert "key_features" in detail["attributes"]
    assert detail["attributes"]["key_features"]
    assert detail["size_chart"]["type"] == "clothing"
    assert detail["images"] == [detail["main_image"]]
    assert detail["category_name"]


def test_product_detail_invalid_token_is_treated_as_anonymous(
    client, seeded_catalog
):
    product = first_product(client)
    response = client.get(
        f"/api/products/{product['id']}",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 200
    assert response.json()["is_favorited"] is False


def test_product_detail_returns_is_favorited_when_logged_in(
    client, seeded_catalog
):
    token = login(client)
    product = first_product(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(f"/api/products/{product['id']}/favorite", headers=headers)
    detail = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert detail["is_favorited"] is True


def test_product_detail_missing_returns_404(client, seeded_catalog):
    assert client.get("/api/products/999999").status_code == 404


def test_static_product_image_is_served(client, seeded_catalog):
    product = first_product(client)
    image_path = product["main_image"]
    assert image_path.startswith("/static/products/")
    response = client.get(image_path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")


def test_favorites_require_login(client, seeded_catalog):
    assert client.get("/api/favorites").status_code == 401
    product = first_product(client)
    assert client.post(f"/api/products/{product['id']}/favorite").status_code == 401
    assert client.delete(f"/api/products/{product['id']}/favorite").status_code == 401


def test_favorites_add_delete_are_idempotent(client, seeded_catalog):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}
    product = first_product(client)

    first = client.post(f"/api/products/{product['id']}/favorite", headers=headers)
    assert first.status_code == 200
    assert first.json() == {"favorited": True}

    second = client.post(f"/api/products/{product['id']}/favorite", headers=headers)
    assert second.status_code == 200
    assert second.json() == {"favorited": True}

    favorites = client.get("/api/favorites", headers=headers).json()
    assert [item["id"] for item in favorites] == [product["id"]]

    first_delete = client.delete(
        f"/api/products/{product['id']}/favorite", headers=headers
    )
    assert first_delete.status_code == 200
    assert first_delete.json() == {"favorited": False}

    second_delete = client.delete(
        f"/api/products/{product['id']}/favorite", headers=headers
    )
    assert second_delete.status_code == 200
    assert second_delete.json() == {"favorited": False}

    assert client.get("/api/favorites", headers=headers).json() == []


def test_favorite_missing_product_returns_404(client, seeded_catalog):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert (
        client.post("/api/products/999999/favorite", headers=headers).status_code
        == 404
    )
    assert (
        client.delete("/api/products/999999/favorite", headers=headers).status_code
        == 404
    )
