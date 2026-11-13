def register_and_login(client, username: str = "cart_user") -> dict:
    payload = {"username": username, "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def add_item(client, headers, sku_id: int, quantity: int = 1):
    return client.post(
        "/api/cart/items",
        json={"sku_id": sku_id, "quantity": quantity},
        headers=headers,
    )


def test_cart_add_accumulates_and_computes_totals(client, sample_catalog):
    headers = register_and_login(client)
    sku_id = sample_catalog["sku_a_id"]

    first = add_item(client, headers, sku_id, 1)
    assert first.status_code == 200
    assert first.json()["quantity"] == 1

    second = add_item(client, headers, sku_id, 2)
    assert second.status_code == 200
    body = second.json()
    assert body["quantity"] == 3
    assert body["title"] == "测试衬衫"
    assert body["price"] == 100.0
    assert body["stock"] == 10
    assert body["available"] is True

    cart = client.get("/api/cart", headers=headers).json()
    assert cart["total_quantity"] == 3
    assert cart["selected_count"] == 1
    assert cart["selected_amount"] == 300.0
    assert cart["all_selected"] is True
    assert len(cart["items"]) == 1


def test_cart_add_over_stock_returns_409_without_truncation(
    client, sample_catalog
):
    headers = register_and_login(client)
    sku_id = sample_catalog["sku_a_alt_id"]

    assert add_item(client, headers, sku_id, 3).status_code == 200
    response = add_item(client, headers, sku_id, 1)
    assert response.status_code == 409
    assert "库存不足" in response.json()["detail"]

    cart = client.get("/api/cart", headers=headers).json()
    assert cart["items"][0]["quantity"] == 3


def test_cart_update_quantity_and_selected(client, sample_catalog):
    headers = register_and_login(client)
    item = add_item(client, headers, sample_catalog["sku_a_id"], 2).json()

    response = client.patch(
        f"/api/cart/items/{item['id']}",
        json={"quantity": 4, "selected": False},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 4
    assert response.json()["selected"] is False

    cart = client.get("/api/cart", headers=headers).json()
    assert cart["total_quantity"] == 4
    assert cart["selected_count"] == 0
    assert cart["selected_amount"] == 0.0
    assert cart["all_selected"] is False


def test_cart_update_over_stock_returns_409(client, sample_catalog):
    headers = register_and_login(client)
    item = add_item(client, headers, sample_catalog["sku_a_alt_id"], 1).json()

    response = client.patch(
        f"/api/cart/items/{item['id']}",
        json={"quantity": 4},
        headers=headers,
    )
    assert response.status_code == 409
    cart = client.get("/api/cart", headers=headers).json()
    assert cart["items"][0]["quantity"] == 1


def test_cart_is_isolated_between_users(client, sample_catalog):
    owner = register_and_login(client, "cart_owner")
    other = register_and_login(client, "cart_other")
    item = add_item(client, owner, sample_catalog["sku_a_id"]).json()

    assert (
        client.patch(
            f"/api/cart/items/{item['id']}",
            json={"quantity": 2},
            headers=other,
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/cart/items/{item['id']}", headers=other
        ).status_code
        == 403
    )
    cart = client.get("/api/cart", headers=owner).json()
    assert len(cart["items"]) == 1


def test_cart_missing_item_returns_404(client, sample_catalog):
    headers = register_and_login(client)
    assert (
        client.patch(
            "/api/cart/items/999999", json={"quantity": 2}, headers=headers
        ).status_code
        == 404
    )
    assert (
        client.delete("/api/cart/items/999999", headers=headers).status_code
        == 404
    )


def test_cart_delete_item(client, sample_catalog):
    headers = register_and_login(client)
    item = add_item(client, headers, sample_catalog["sku_a_id"]).json()

    response = client.delete(f"/api/cart/items/{item['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get("/api/cart", headers=headers).json()["items"] == []


def test_cart_rejects_off_sale_product(client, sample_catalog, execute_sql):
    headers = register_and_login(client)
    execute_sql(
        "UPDATE products SET status = 'off_sale' WHERE id = :product_id",
        {"product_id": sample_catalog["product_a_id"]},
    )

    response = add_item(client, headers, sample_catalog["sku_a_id"])
    assert response.status_code == 409
    assert "已下架" in response.json()["detail"]


def test_cart_rejects_missing_sku(client, sample_catalog):
    headers = register_and_login(client)
    response = add_item(client, headers, 999999)
    assert response.status_code == 404
