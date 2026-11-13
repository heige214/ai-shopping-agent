from concurrent.futures import ThreadPoolExecutor

ADDRESS = {
    "receiver_name": "小鹿",
    "phone": "13800000000",
    "province": "上海市",
    "city": "上海市",
    "district": "浦东新区",
    "detail": "世纪大道 100 号 8 栋 1201 室",
}


def register_and_login(client, username: str = "order_user") -> dict:
    payload = {"username": username, "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_address(client, headers) -> dict:
    response = client.post("/api/addresses", json=ADDRESS, headers=headers)
    assert response.status_code == 201
    return response.json()


def add_cart(client, headers, sku_id: int, quantity: int = 1) -> dict:
    response = client.post(
        "/api/cart/items",
        json={"sku_id": sku_id, "quantity": quantity},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def submit_order(
    client, headers, address_id: int, item_ids: list[int] | None = None
):
    payload: dict = {"address_id": address_id}
    if item_ids is not None:
        payload["cart_item_ids"] = item_ids
    return client.post("/api/orders", json=payload, headers=headers)


def get_stock(client, product_id: int, sku_id: int) -> int:
    detail = client.get(f"/api/products/{product_id}").json()
    return next(sku["stock"] for sku in detail["skus"] if sku["id"] == sku_id)


def test_create_order_snapshots_deducts_stock_and_clears_cart(
    client, sample_catalog, execute_sql
):
    headers = register_and_login(client)
    address = create_address(client, headers)
    item_a = add_cart(client, headers, sample_catalog["sku_a_id"], 2)
    add_cart(client, headers, sample_catalog["sku_b_id"], 1)

    response = submit_order(client, headers, address["id"])
    assert response.status_code == 201
    order = response.json()

    assert order["status"] == "pending_payment"
    assert order["total_amount"] == 250.0
    assert order["payment_method"] == "simulated"
    assert order["address_snapshot"]["receiver_name"] == "小鹿"
    assert order["address_snapshot"]["detail"] == ADDRESS["detail"]
    assert len(order["items"]) == 2
    assert sum(item["quantity"] for item in order["items"]) == 3
    assert order["expires_at"] > order["created_at"]

    assert (
        get_stock(client, sample_catalog["product_a_id"], sample_catalog["sku_a_id"])
        == 8
    )
    assert (
        get_stock(client, sample_catalog["product_b_id"], sample_catalog["sku_b_id"])
        == 4
    )
    assert client.get("/api/cart", headers=headers).json()["items"] == []

    # 商品改价/改标题不影响历史订单快照
    execute_sql(
        "UPDATE products SET title = '改名后的商品', price = 999.00 "
        "WHERE id = :product_id",
        {"product_id": sample_catalog["product_a_id"]},
    )
    detail = client.get(f"/api/orders/{order['id']}", headers=headers).json()
    item = next(
        item for item in detail["items"] if item["sku_id"] == item_a["sku_id"]
    )
    assert item["title"] == "测试衬衫"
    assert item["price"] == 100.0
    assert detail["total_amount"] == 250.0


def test_create_order_defaults_to_selected_items_only(client, sample_catalog):
    headers = register_and_login(client)
    address = create_address(client, headers)
    add_cart(client, headers, sample_catalog["sku_a_id"], 1)
    item_b = add_cart(client, headers, sample_catalog["sku_b_id"], 1)
    client.patch(
        f"/api/cart/items/{item_b['id']}",
        json={"selected": False},
        headers=headers,
    )

    response = submit_order(client, headers, address["id"])
    assert response.status_code == 201
    order = response.json()
    assert len(order["items"]) == 1
    assert order["items"][0]["sku_id"] == sample_catalog["sku_a_id"]

    cart = client.get("/api/cart", headers=headers).json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["id"] == item_b["id"]
    assert cart["items"][0]["selected"] is False
    assert (
        get_stock(client, sample_catalog["product_b_id"], sample_catalog["sku_b_id"])
        == 5
    )


def test_create_order_with_explicit_item_ids_ignores_selection(
    client, sample_catalog
):
    """立即购买：指定购物车项结算，不改变其他项的勾选状态。"""
    headers = register_and_login(client)
    address = create_address(client, headers)
    item_a = add_cart(client, headers, sample_catalog["sku_a_id"], 1)
    item_b = add_cart(client, headers, sample_catalog["sku_b_id"], 1)
    client.patch(
        f"/api/cart/items/{item_a['id']}",
        json={"selected": False},
        headers=headers,
    )

    response = submit_order(
        client, headers, address["id"], [item_a["id"]]
    )
    assert response.status_code == 201
    order = response.json()
    assert [item["sku_id"] for item in order["items"]] == [
        sample_catalog["sku_a_id"]
    ]

    cart = client.get("/api/cart", headers=headers).json()
    assert [item["id"] for item in cart["items"]] == [item_b["id"]]
    assert cart["items"][0]["selected"] is True


def test_create_order_without_items_returns_400(client, sample_catalog):
    headers = register_and_login(client)
    address = create_address(client, headers)

    response = submit_order(client, headers, address["id"])
    assert response.status_code == 400
    assert "结算" in response.json()["detail"]

    item = add_cart(client, headers, sample_catalog["sku_a_id"], 1)
    client.patch(
        f"/api/cart/items/{item['id']}",
        json={"selected": False},
        headers=headers,
    )
    assert submit_order(client, headers, address["id"]).status_code == 400


def test_create_order_insufficient_stock_returns_409(
    client, sample_catalog, execute_sql
):
    headers = register_and_login(client)
    address = create_address(client, headers)
    add_cart(client, headers, sample_catalog["sku_a_id"], 2)
    execute_sql(
        "UPDATE product_skus SET stock = 1 WHERE id = :sku_id",
        {"sku_id": sample_catalog["sku_a_id"]},
    )

    response = submit_order(client, headers, address["id"])
    assert response.status_code == 409
    assert "库存不足" in response.json()["detail"]
    assert client.get("/api/cart", headers=headers).json()["items"][0]["quantity"] == 2
    assert (
        get_stock(client, sample_catalog["product_a_id"], sample_catalog["sku_a_id"])
        == 1
    )
    assert client.get("/api/orders", headers=headers).json() == []


def test_create_order_with_foreign_address_returns_403(client, sample_catalog):
    owner = register_and_login(client, "addr_owner")
    buyer = register_and_login(client, "addr_buyer")
    foreign_address = create_address(client, owner)
    add_cart(client, buyer, sample_catalog["sku_a_id"], 1)

    response = submit_order(client, buyer, foreign_address["id"])
    assert response.status_code == 403
    assert "无权" in response.json()["detail"]


def test_pay_is_idempotent_and_sales_count_increments_once(
    client, sample_catalog
):
    headers = register_and_login(client)
    address = create_address(client, headers)
    add_cart(client, headers, sample_catalog["sku_a_id"], 2)
    order = submit_order(client, headers, address["id"]).json()

    before = client.get(
        f"/api/products/{sample_catalog['product_a_id']}"
    ).json()["sales_count"]

    first = client.post(f"/api/orders/{order['id']}/pay", headers=headers)
    assert first.status_code == 200
    paid = first.json()
    assert paid["status"] == "paid"
    assert paid["payment_no"].startswith("PAY")
    assert paid["paid_at"] is not None

    after_first = client.get(
        f"/api/products/{sample_catalog['product_a_id']}"
    ).json()["sales_count"]
    assert after_first == before + 2

    second = client.post(f"/api/orders/{order['id']}/pay", headers=headers)
    assert second.status_code == 200
    assert second.json()["payment_no"] == paid["payment_no"]
    after_second = client.get(
        f"/api/products/{sample_catalog['product_a_id']}"
    ).json()["sales_count"]
    assert after_second == after_first


def test_cancel_restores_stock_only_once(client, sample_catalog):
    headers = register_and_login(client)
    address = create_address(client, headers)
    add_cart(client, headers, sample_catalog["sku_a_id"], 2)
    order = submit_order(client, headers, address["id"]).json()

    first = client.post(f"/api/orders/{order['id']}/cancel", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "cancelled"
    assert (
        get_stock(client, sample_catalog["product_a_id"], sample_catalog["sku_a_id"])
        == 10
    )

    second = client.post(f"/api/orders/{order['id']}/cancel", headers=headers)
    assert second.status_code == 200
    assert second.json()["status"] == "cancelled"
    assert (
        get_stock(client, sample_catalog["product_a_id"], sample_catalog["sku_a_id"])
        == 10
    )


def test_cancelled_order_cannot_be_paid_and_paid_order_cannot_be_cancelled(
    client, sample_catalog
):
    headers = register_and_login(client)
    address = create_address(client, headers)
    add_cart(client, headers, sample_catalog["sku_a_id"], 1)
    cancelled = submit_order(client, headers, address["id"]).json()
    client.post(f"/api/orders/{cancelled['id']}/cancel", headers=headers)
    response = client.post(
        f"/api/orders/{cancelled['id']}/pay", headers=headers
    )
    assert response.status_code == 409

    add_cart(client, headers, sample_catalog["sku_b_id"], 1)
    paid = submit_order(client, headers, address["id"]).json()
    assert (
        client.post(f"/api/orders/{paid['id']}/pay", headers=headers).status_code
        == 200
    )
    response = client.post(
        f"/api/orders/{paid['id']}/cancel", headers=headers
    )
    assert response.status_code == 409


def test_expired_order_is_cancelled_on_list_and_stock_restored(
    client, sample_catalog, execute_sql
):
    headers = register_and_login(client)
    address = create_address(client, headers)
    add_cart(client, headers, sample_catalog["sku_a_id"], 2)
    order = submit_order(client, headers, address["id"]).json()

    execute_sql(
        "UPDATE orders SET expires_at = now() - interval '1 minute' "
        "WHERE id = :order_id",
        {"order_id": order["id"]},
    )

    orders = client.get("/api/orders", headers=headers).json()
    assert orders[0]["status"] == "cancelled"
    assert orders[0]["cancelled_at"] is not None
    assert (
        get_stock(client, sample_catalog["product_a_id"], sample_catalog["sku_a_id"])
        == 10
    )


def test_pay_expired_order_returns_409_and_restores_stock(
    client, sample_catalog, execute_sql
):
    headers = register_and_login(client)
    address = create_address(client, headers)
    add_cart(client, headers, sample_catalog["sku_a_id"], 1)
    order = submit_order(client, headers, address["id"]).json()

    execute_sql(
        "UPDATE orders SET expires_at = now() - interval '1 minute' "
        "WHERE id = :order_id",
        {"order_id": order["id"]},
    )

    response = client.post(f"/api/orders/{order['id']}/pay", headers=headers)
    assert response.status_code == 409
    assert "取消" in response.json()["detail"]
    assert (
        get_stock(client, sample_catalog["product_a_id"], sample_catalog["sku_a_id"])
        == 10
    )


def test_order_is_isolated_between_users(client, sample_catalog):
    owner = register_and_login(client, "order_owner")
    other = register_and_login(client, "order_other")
    address = create_address(client, owner)
    add_cart(client, owner, sample_catalog["sku_a_id"], 1)
    order = submit_order(client, owner, address["id"]).json()

    assert (
        client.get(f"/api/orders/{order['id']}", headers=other).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/orders/{order['id']}/pay", headers=other
        ).status_code
        == 403
    )
    assert client.get("/api/orders", headers=other).json() == []


def test_agent_endpoints_require_agent_role(client, sample_catalog, agent_token):
    user = register_and_login(client, "not_agent")
    assert client.get("/api/agent/orders", headers=user).status_code == 403

    response = client.get(
        "/api/agent/orders",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_full_order_state_machine(client, sample_catalog, agent_token):
    agent = {"Authorization": f"Bearer {agent_token}"}
    headers = register_and_login(client)
    address = create_address(client, headers)
    add_cart(client, headers, sample_catalog["sku_a_id"], 1)
    order = submit_order(client, headers, address["id"]).json()

    # 待支付不能发货
    assert (
        client.post(
            f"/api/agent/orders/{order['id']}/ship", headers=agent
        ).status_code
        == 409
    )

    paid = client.post(f"/api/orders/{order['id']}/pay", headers=headers)
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"

    # 已支付未发货不能确认收货
    assert (
        client.post(
            f"/api/orders/{order['id']}/confirm", headers=headers
        ).status_code
        == 409
    )

    shipped = client.post(
        f"/api/agent/orders/{order['id']}/ship", headers=agent
    )
    assert shipped.status_code == 200
    assert shipped.json()["status"] == "shipped"
    assert shipped.json()["shipped_at"] is not None

    completed = client.post(
        f"/api/orders/{order['id']}/confirm", headers=headers
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    assert (
        client.post(
            f"/api/orders/{order['id']}/confirm", headers=headers
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/agent/orders/{order['id']}/ship", headers=agent
        ).status_code
        == 409
    )


def test_agent_order_list_filters_by_status(
    client, sample_catalog, agent_token
):
    agent = {"Authorization": f"Bearer {agent_token}"}
    headers = register_and_login(client)
    address = create_address(client, headers)
    add_cart(client, headers, sample_catalog["sku_a_id"], 1)
    order = submit_order(client, headers, address["id"]).json()
    client.post(f"/api/orders/{order['id']}/pay", headers=headers)

    paid = client.get("/api/agent/orders", headers=agent).json()
    assert [item["id"] for item in paid] == [order["id"]]
    assert paid[0]["buyer_username"] == "order_user"
    assert paid[0]["items"][0]["title"] == "测试衬衫"

    client.post(f"/api/agent/orders/{order['id']}/ship", headers=agent)

    assert client.get("/api/agent/orders", headers=agent).json() == []
    shipped = client.get(
        "/api/agent/orders?status=shipped", headers=agent
    ).json()
    assert [item["id"] for item in shipped] == [order["id"]]
    all_orders = client.get(
        "/api/agent/orders?status=all", headers=agent
    ).json()
    assert [item["id"] for item in all_orders] == [order["id"]]


def test_order_list_filters_by_status(client, sample_catalog):
    headers = register_and_login(client)
    address = create_address(client, headers)

    add_cart(client, headers, sample_catalog["sku_a_id"], 1)
    paid = submit_order(client, headers, address["id"]).json()
    client.post(f"/api/orders/{paid['id']}/pay", headers=headers)

    add_cart(client, headers, sample_catalog["sku_b_id"], 1)
    cancelled = submit_order(client, headers, address["id"]).json()
    client.post(f"/api/orders/{cancelled['id']}/cancel", headers=headers)

    paid_list = client.get("/api/orders?status=paid", headers=headers).json()
    assert [item["id"] for item in paid_list] == [paid["id"]]
    cancelled_list = client.get(
        "/api/orders?status=cancelled", headers=headers
    ).json()
    assert [item["id"] for item in cancelled_list] == [cancelled["id"]]
    assert len(client.get("/api/orders", headers=headers).json()) == 2


def test_concurrent_orders_with_stock_one_only_one_succeeds(
    client, sample_catalog, execute_sql
):
    first = register_and_login(client, "race_first")
    second = register_and_login(client, "race_second")
    first_address = create_address(client, first)
    second_address = create_address(client, second)
    first_item = add_cart(client, first, sample_catalog["sku_a_id"], 1)
    second_item = add_cart(client, second, sample_catalog["sku_a_id"], 1)

    execute_sql(
        "UPDATE product_skus SET stock = 1 WHERE id = :sku_id",
        {"sku_id": sample_catalog["sku_a_id"]},
    )

    def place(headers, address_id, item_id):
        return submit_order(client, headers, address_id, [item_id])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(place, first, first_address["id"], first_item["id"]),
            pool.submit(place, second, second_address["id"], second_item["id"]),
        ]
        results = [future.result() for future in futures]

    assert sorted(response.status_code for response in results) == [201, 409]
    assert (
        get_stock(client, sample_catalog["product_a_id"], sample_catalog["sku_a_id"])
        == 0
    )

    orders = (
        client.get("/api/orders", headers=first).json()
        + client.get("/api/orders", headers=second).json()
    )
    assert len(orders) == 1
