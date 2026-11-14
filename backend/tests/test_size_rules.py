from app.ai.size_rules import (
    build_size_availability_answer,
    collect_size_options,
    parse_size_query,
)

LETTER_STOCK = {"S": 2, "M": 3, "L": 4, "XL": 5, "XXL": 6}
NUMERIC_STOCK = {"35": 12, "36": 46, "37": 0, "38": 6, "39": 45}


def test_bare_letter_size_is_recognized_without_size_word():
    query = parse_size_query("有XS的吗", list(LETTER_STOCK))

    assert query.requested_size == "XS"
    assert query.is_availability is True
    assert query.mentions_size is True


def test_missing_letter_size_answers_directly():
    query = parse_size_query("有XS的吗", list(LETTER_STOCK))
    answer = build_size_availability_answer(LETTER_STOCK, list(LETTER_STOCK), query)

    assert answer == (
        "不好意思，这款没有 XS 码，可选尺码是 S、M、L、XL、XXL 码。"
    )


def test_available_numeric_size_answers_yes():
    query = parse_size_query("有36码吗", list(NUMERIC_STOCK))
    answer = build_size_availability_answer(
        NUMERIC_STOCK, list(NUMERIC_STOCK), query
    )

    assert answer == "有的，36 码目前有货。"


def test_zero_stock_numeric_size_says_temporarily_unavailable():
    query = parse_size_query("有37码吗", list(NUMERIC_STOCK))
    answer = build_size_availability_answer(
        NUMERIC_STOCK, list(NUMERIC_STOCK), query
    )

    assert answer == "不好意思，37 码暂时缺货，目前可选 35-36、38-39 码。"


def test_missing_numeric_size_answers_directly():
    query = parse_size_query("有40尺码的吗", list(NUMERIC_STOCK))
    answer = build_size_availability_answer(
        NUMERIC_STOCK, list(NUMERIC_STOCK), query
    )

    assert answer == "不好意思，这款没有 40 码，可选尺码是 35-36、38-39 码。"


def test_generic_stock_question_summarizes_availability():
    query = parse_size_query("有货吗", list(NUMERIC_STOCK))
    answer = build_size_availability_answer(
        NUMERIC_STOCK, list(NUMERIC_STOCK), query
    )

    assert answer == (
        "有的，目前 35-36、38-39 码有货；37 码暂时缺货。"
    )


def test_ambiguous_number_on_letter_product_is_not_a_size():
    query = parse_size_query("有40的吗", list(LETTER_STOCK))

    assert query.requested_size is None
    assert query.mentions_size is False


def test_collect_size_options_falls_back_to_attributes_and_chart():
    options = collect_size_options(
        {},
        ["S", "M"],
        {"rows": [{"size": "L"}]},
    )
    assert options == ["S", "M"]
    assert collect_size_options({}, None, {"rows": [{"size": "XL"}]}) == ["XL"]
