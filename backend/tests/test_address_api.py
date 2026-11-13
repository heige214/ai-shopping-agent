ADDRESS = {
    "receiver_name": "小鹿",
    "phone": "13800000000",
    "province": "上海市",
    "city": "上海市",
    "district": "浦东新区",
    "detail": "世纪大道 100 号 8 栋 1201 室",
}


def register_and_login(client, username: str = "address_user") -> dict:
    payload = {"username": username, "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_address(client, headers, **overrides):
    payload = {**ADDRESS, **overrides}
    return client.post("/api/addresses", json=payload, headers=headers)


def test_first_address_is_default(client, sample_catalog):
    headers = register_and_login(client)
    response = create_address(client, headers)

    assert response.status_code == 201
    address = response.json()
    assert address["is_default"] is True
    assert address["receiver_name"] == "小鹿"

    listed = client.get("/api/addresses", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["is_default"] is True


def test_new_default_clears_old_default(client, sample_catalog):
    headers = register_and_login(client)
    first = create_address(client, headers).json()
    second = create_address(
        client, headers, receiver_name="小林", is_default=True
    ).json()

    listed = client.get("/api/addresses", headers=headers).json()
    by_id = {item["id"]: item for item in listed}
    assert by_id[first["id"]]["is_default"] is False
    assert by_id[second["id"]]["is_default"] is True
    assert sum(item["is_default"] for item in listed) == 1


def test_non_default_address_keeps_existing_default(client, sample_catalog):
    headers = register_and_login(client)
    first = create_address(client, headers).json()
    second = create_address(client, headers, receiver_name="小林").json()

    listed = client.get("/api/addresses", headers=headers).json()
    by_id = {item["id"]: item for item in listed}
    assert by_id[first["id"]]["is_default"] is True
    assert by_id[second["id"]]["is_default"] is False


def test_update_to_default_clears_old_default(client, sample_catalog):
    headers = register_and_login(client)
    first = create_address(client, headers).json()
    second = create_address(client, headers, receiver_name="小林").json()

    response = client.patch(
        f"/api/addresses/{second['id']}",
        json={"is_default": True, "detail": "新地址 1 号"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["is_default"] is True
    assert response.json()["detail"] == "新地址 1 号"

    listed = client.get("/api/addresses", headers=headers).json()
    by_id = {item["id"]: item for item in listed}
    assert by_id[first["id"]]["is_default"] is False
    assert sum(item["is_default"] for item in listed) == 1


def test_delete_default_promotes_remaining_address(client, sample_catalog):
    headers = register_and_login(client)
    first = create_address(client, headers).json()
    second = create_address(
        client, headers, receiver_name="小林", is_default=True
    ).json()

    assert (
        client.delete(
            f"/api/addresses/{second['id']}", headers=headers
        ).status_code
        == 204
    )
    listed = client.get("/api/addresses", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["id"] == first["id"]
    assert listed[0]["is_default"] is True


def test_address_is_isolated_between_users(client, sample_catalog):
    owner = register_and_login(client, "address_owner")
    other = register_and_login(client, "address_other")
    address = create_address(client, owner).json()

    assert (
        client.patch(
            f"/api/addresses/{address['id']}",
            json={"receiver_name": "越权"},
            headers=other,
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/addresses/{address['id']}", headers=other
        ).status_code
        == 403
    )
    assert (
        client.delete("/api/addresses/999999", headers=owner).status_code
        == 404
    )


def test_cannot_unset_the_only_default_address(client, sample_catalog):
    headers = register_and_login(client)
    address = create_address(client, headers).json()

    response = client.patch(
        f"/api/addresses/{address['id']}",
        json={"is_default": False},
        headers=headers,
    )
    assert response.status_code == 400
    assert "默认地址" in response.json()["detail"]
