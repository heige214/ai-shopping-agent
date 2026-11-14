from app.ai.guide_slots import extract_local_guide_query, merge_guide_query

CATEGORY_HINT = "\n".join(
    [
        "服装",
        "服装 > 衬衫",
        "服装 > T恤",
        "服装 > 外套",
        "鞋靴",
        "鞋靴 > 运动鞋",
        "箱包",
        "箱包 > 双肩包",
    ]
)


def parse(
    text: str,
    previous=None,
    profile: dict | None = None,
    hint: str = CATEGORY_HINT,
):
    slot_state = {"query": previous.model_dump()} if previous else {}
    return extract_local_guide_query(text, slot_state, profile, hint)


def test_parse_color_material_thickness_price_and_profile():
    query = parse("找一件蓝色薄款纯棉衬衫，200元以内，身高172，体重75")

    assert query.category_path == ["服装", "衬衫"]
    assert query.filters["color"] == ["蓝色"]
    assert query.filters["material"] == ["纯棉"]
    assert query.filters["thickness"] == ["薄款"]
    assert query.price.max == 200
    assert query.price.min is None
    assert query.size_profile.height_cm == 172
    assert query.size_profile.weight_kg == 75


def test_parse_price_range_and_shoe_category():
    query = parse("300-500元的运动鞋")

    assert query.category_path == ["鞋靴", "运动鞋"]
    assert query.price.min == 300
    assert query.price.max == 500


def test_parse_compound_color_and_thickness():
    query = parse("深灰色加厚外套")

    assert query.category_path == ["服装", "外套"]
    assert query.filters["color"] == ["深灰"]
    assert query.filters["thickness"] == ["加厚"]


def test_merge_refine_keeps_color_and_overrides_price():
    first = parse("蓝色衬衫")
    second = parse("要150元以内的", previous=first)
    merged = merge_guide_query(
        first,
        second,
        {"height_cm": 172, "weight_kg": 75, "usual_size": "M"},
    )

    assert merged.category_path == ["服装", "衬衫"]
    assert merged.filters["color"] == ["蓝色"]
    assert merged.price.max == 150
    assert merged.size_profile.height_cm == 172
    assert merged.size_profile.weight_kg == 75


def test_merge_new_category_resets_old_filters():
    first = parse("蓝色衬衫")
    second = parse("找运动鞋", previous=first)
    merged = merge_guide_query(first, second, None)

    assert merged.category_path == ["鞋靴", "运动鞋"]
    assert "color" not in merged.filters
    assert merged.price.min is None and merged.price.max is None


def test_profile_fills_missing_height_weight():
    merged = merge_guide_query(
        None,
        parse("衬衫"),
        {"height_cm": 172, "weight_kg": 75},
    )

    assert merged.size_profile.height_cm == 172
    assert merged.size_profile.weight_kg == 75


def test_browse_without_conditions_does_not_clarify():
    query = parse("随便看看")

    assert query.intent == "search"
    assert query.category_path == []
    assert query.filters == {}
    assert query.price.min is None and query.price.max is None


def test_greeting_is_chitchat():
    assert parse("你好").intent == "chitchat"


def test_reset_words_clear_previous_slots():
    first = parse("蓝色衬衫")
    second = parse("看看热门商品", previous=first)
    merged = merge_guide_query(first, second, None)

    assert merged.category_path == []
    assert merged.filters == {}


def test_unlimited_budget_clears_previous_price():
    first = parse("蓝色衬衫200元以内")
    second = parse("不限预算", previous=first)
    merged = merge_guide_query(first, second, None)

    assert merged.filters["color"] == ["蓝色"]
    assert merged.price.min is None
    assert merged.price.max is None
