from app.modules.guide.size import recommend_size

CLOTHING_CHART = {
    "type": "clothing",
    "unit": "cm",
    "rows": [
        {
            "size": "S",
            "height": [155, 165],
            "weight": [45, 55],
            "chest": [82, 88],
            "waist": [68, 74],
        },
        {
            "size": "M",
            "height": [165, 172],
            "weight": [55, 65],
            "chest": [88, 94],
            "waist": [74, 80],
        },
        {
            "size": "L",
            "height": [170, 178],
            "weight": [65, 75],
            "chest": [94, 100],
            "waist": [80, 86],
        },
        {
            "size": "XL",
            "height": [176, 184],
            "weight": [75, 85],
            "chest": [100, 106],
            "waist": [86, 92],
        },
    ],
}

SHOES_CHART = {
    "type": "shoes",
    "unit": "mm",
    "rows": [
        {"size": "39", "foot_length": [245, 250]},
        {"size": "40", "foot_length": [250, 255]},
    ],
}


def test_exact_height_weight_returns_size():
    result = recommend_size(CLOTHING_CHART, 172, 75)

    assert result.recommended_size == "L"
    assert "L 码" in result.size_reason
    assert result.source == "profile"


def test_overlapping_rows_tie_breaks_to_larger_size():
    result = recommend_size(CLOTHING_CHART, 165, 55)

    assert result.recommended_size == "M"


def test_no_exact_match_returns_nearest_with_try_on_hint():
    result = recommend_size(CLOTHING_CHART, 180, 90)

    assert result.recommended_size == "XL"
    assert "建议试穿" in result.size_reason


def test_missing_weight_does_not_recommend():
    result = recommend_size(CLOTHING_CHART, 172, None)

    assert result.recommended_size is None
    assert "身高体重" in result.size_reason


def test_shoes_use_usual_size_when_foot_length_is_unknown():
    result = recommend_size(SHOES_CHART, 172, 75, usual_size="40")

    assert result.recommended_size == "40"
    assert result.source == "usual_size"
    assert "脚长" in result.size_reason


def test_shoes_without_usual_size_or_foot_length_does_not_recommend():
    result = recommend_size(SHOES_CHART, 172, 75, usual_size="42")

    assert result.recommended_size is None
    assert "脚长" in result.size_reason


def test_missing_size_chart_returns_reason():
    result = recommend_size(None, 172, 75)

    assert result.recommended_size is None
    assert "尺码表" in result.size_reason


def test_clothing_without_profile_does_not_use_usual_size():
    result = recommend_size(CLOTHING_CHART, None, None, usual_size="M")

    assert result.recommended_size is None
    assert "身高体重" in result.size_reason
