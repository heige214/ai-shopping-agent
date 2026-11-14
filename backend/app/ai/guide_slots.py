from __future__ import annotations

import re
from typing import Any

from app.ai.base import (
    GuideCartQuery,
    GuidePrice,
    GuideQuery,
    GuideSizeProfile,
)

ALLOWED_FILTER_KEYS = ("color", "material", "thickness")

CHITCHAT_WORDS = (
    "你好",
    "您好",
    "在吗",
    "谢谢",
    "再见",
    "拜拜",
    "嗨",
    "hello",
    "hi",
)
REFINE_WORDS = (
    "再",
    "换",
    "改成",
    "改到",
    "别的",
    "还有",
    "更",
    "便宜",
    "贵",
    "不要",
    "放宽",
)
RESET_WORDS = (
    "重新找",
    "重新推荐",
    "随便看看",
    "都可以",
    "看看热门",
    "热门商品",
    "换一批",
    "不用了",
    "从头",
)
PRICE_CLEAR_WORDS = ("不限预算", "价格不限", "预算不限", "不限价格")

CART_WORDS = (
    "加入购物车",
    "加到购物车",
    "放入购物车",
    "放到购物车",
    "加购",
    "购物车",
)
CART_DEICTIC_WORDS = ("这个", "这件", "这款", "它", "那个", "那件")
ORDINAL_PATTERN = re.compile(
    r"第\s*([0-9一二两三四五六七八九十]+)\s*(?:件|个|款)"
)
SIZE_PATTERN = re.compile(
    r"(?:尺码|码数)?\s*(XXXL|XXL|XL|XS|S|M|L|均码|\d{2,3})\s*码",
    re.IGNORECASE,
)
QUANTITY_PATTERN = re.compile(
    r"(?:要|买|加|来|共|总共)?\s*([0-9一二两三四五六七八九十]+)\s*"
    r"(?:件|个|双|条|只)"
)
CHINESE_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _to_number(text: str) -> int | None:
    text = text.strip()
    if text.isdigit():
        return int(text)
    if not text:
        return None
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = CHINESE_DIGITS.get(left, 1) if left else 1
        ones = CHINESE_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    if len(text) == 1:
        return CHINESE_DIGITS.get(text)
    return None


def _parse_cart_command(text: str) -> GuideCartQuery | None:
    """解析“把第二件 L 码加入购物车，要两件”这类加购指令。"""
    lowered = text.lower()
    if not any(word in lowered for word in CART_WORDS):
        return None

    ordinal: int | None = None
    ordinal_match = ORDINAL_PATTERN.search(text)
    if ordinal_match:
        ordinal = _to_number(ordinal_match.group(1))

    size_match = SIZE_PATTERN.search(text)
    size = size_match.group(1) if size_match else None

    remaining = ORDINAL_PATTERN.sub(" ", text)
    if size_match:
        remaining = remaining.replace(size_match.group(0), " ")
    quantity_match = QUANTITY_PATTERN.search(remaining)
    quantity = 1
    if quantity_match:
        parsed = _to_number(quantity_match.group(1))
        if parsed is not None:
            quantity = max(1, min(parsed, 99))
        remaining = remaining.replace(quantity_match.group(0), " ")

    if ordinal is not None:
        return GuideCartQuery(
            reference="ordinal",
            ordinal=ordinal,
            size=size,
            quantity=quantity,
        )

    name = remaining
    for word in CART_WORDS:
        name = name.replace(word, " ")
    for word in CART_DEICTIC_WORDS:
        name = name.replace(word, " ")
    name = name.strip(" ，,。.!！?？、；;：:\t\r\n")
    for prefix in (
        "请帮我",
        "帮我",
        "麻烦",
        "我想要",
        "我要",
        "想要",
        "把",
        "将",
        "给",
        "想",
        "要",
        "买",
    ):
        if name.startswith(prefix):
            name = name[len(prefix) :].strip()
    name = re.sub(r"[，,。.!！?？、；;：:\s]+", "", name)
    if name:
        return GuideCartQuery(
            reference="name",
            product_name=name,
            size=size,
            quantity=quantity,
        )

    if any(word in text for word in CART_DEICTIC_WORDS):
        return GuideCartQuery(
            reference="deictic", size=size, quantity=quantity
        )
    return GuideCartQuery(reference="none", size=size, quantity=quantity)

COLOR_WORDS = (
    "浅蓝",
    "浅灰",
    "深灰",
    "米白",
    "藏青",
    "酒红",
    "驼色",
    "黑色",
    "白色",
    "蓝色",
    "红色",
    "绿色",
    "灰色",
    "棕色",
    "卡其",
    "粉色",
    "黄色",
    "紫色",
    "橙色",
    "杏色",
    "咖色",
    "银色",
    "金色",
)
MATERIAL_WORDS = (
    "聚酯纤维",
    "羊绒混纺",
    "棉混纺",
    "牛津纺",
    "莫代尔",
    "聚碳酸酯",
    "不锈钢",
    "925银",
    "纯棉",
    "棉麻",
    "亚麻",
    "真丝",
    "羊毛",
    "羊绒",
    "雪纺",
    "牛仔",
    "涤纶",
    "尼龙",
    "锦纶",
    "帆布",
    "皮革",
    "绒面",
    "针织",
    "抓绒",
    "腈纶",
    "网布",
    "飞织",
    "EVA",
    "PU",
    "ABS",
    "棉",
)
CATEGORY_SYNONYMS = {
    "衣服": ["服装"],
    "上衣": ["服装"],
    "鞋子": ["鞋靴"],
    "鞋": ["鞋靴"],
    "包包": ["箱包"],
    "包": ["箱包"],
    "饰品": ["配饰"],
    "首饰": ["配饰"],
}


def normalize_filters(filters: dict[str, list[str]] | None) -> dict[str, list[str]]:
    """只保留导购支持的筛选键，去空、去重。"""
    result: dict[str, list[str]] = {}
    for key in ALLOWED_FILTER_KEYS:
        values = (filters or {}).get(key) or []
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        if cleaned:
            result[key] = list(dict.fromkeys(cleaned))
    return result


def _match_category(text: str, category_hint: str) -> list[str]:
    lowered = text.lower()
    candidates: list[list[str]] = []
    for line in (category_hint or "").splitlines():
        parts = [part.strip() for part in line.split(">") if part.strip()]
        if parts and parts[-1].lower() in lowered:
            candidates.append(parts)
    if not candidates:
        for word, path in CATEGORY_SYNONYMS.items():
            if word in text:
                candidates.append(list(path))
    if not candidates:
        return []
    candidates.sort(key=lambda path: len(path[-1]), reverse=True)
    return candidates[0]


def _match_known(text: str, words: tuple[str, ...]) -> str | None:
    for word in sorted(words, key=len, reverse=True):
        if word.lower() in text.lower():
            return word
    return None


def _match_thickness(text: str) -> str | None:
    if "加厚" in text or "厚款" in text:
        return "加厚"
    if "薄款" in text or "薄" in text:
        return "薄款"
    if "常规" in text or "适中" in text:
        return "常规"
    if "厚" in text:
        return "加厚"
    return None


def _parse_price(text: str) -> GuidePrice:
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:元|块)?\s*[-~到至]\s*(\d+(?:\.\d+)?)",
        text,
    )
    if range_match:
        return GuidePrice(
            min=float(range_match.group(1)),
            max=float(range_match.group(2)),
        )

    min_value: float | None = None
    max_value: float | None = None
    max_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:元|块)?\s*(?:以内|以下|之内|内)", text
    )
    if max_match:
        max_value = float(max_match.group(1))
    budget_match = re.search(
        r"(?:不超过|低于|少于|预算)\s*(\d+(?:\.\d+)?)", text
    )
    if budget_match and max_value is None:
        max_value = float(budget_match.group(1))
    min_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块)?\s*(?:以上|起)", text)
    if min_match:
        min_value = float(min_match.group(1))
    around_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块)?\s*左右", text)
    if around_match and max_value is None and min_value is None:
        value = float(around_match.group(1))
        min_value = round(value * 0.8, 2)
        max_value = round(value * 1.2, 2)
    return GuidePrice(min=min_value, max=max_value)


def _parse_height(text: str) -> int | None:
    match = re.search(r"身高\s*(\d{2,3})", text) or re.search(
        r"(\d{3})\s*(?:cm|厘米)", text, re.IGNORECASE
    )
    if not match:
        return None
    value = int(match.group(1))
    return value if 100 <= value <= 250 else None


def _parse_weight(text: str) -> int | None:
    match = re.search(r"体重\s*(\d{2,3})", text) or re.search(
        r"(\d{2,3})\s*(?:kg|公斤)", text, re.IGNORECASE
    )
    if not match:
        return None
    value = int(match.group(1))
    return value if 20 <= value <= 300 else None


def extract_local_guide_query(
    message: str,
    slot_state: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    category_hint: str = "",
) -> GuideQuery:
    """无 key / Fake 模式下的确定性槽位解析。"""
    text = (message or "").strip()
    lowered = text.lower()
    cart = _parse_cart_command(text)
    if cart is not None:
        return GuideQuery(
            intent="add_to_cart", semantic=text or None, cart=cart
        )
    if any(word in lowered for word in CHITCHAT_WORDS):
        return GuideQuery(intent="chitchat", semantic=text or None)

    category_path = _match_category(text, category_hint)
    filters: dict[str, list[str]] = {}
    color = _match_known(text, COLOR_WORDS)
    if color:
        filters["color"] = [color]
    material = _match_known(text, MATERIAL_WORDS)
    if material:
        filters["material"] = [material]
    thickness = _match_thickness(text)
    if thickness:
        filters["thickness"] = [thickness]

    previous = bool((slot_state or {}).get("query"))
    intent = (
        "refine"
        if previous and any(word in text for word in REFINE_WORDS)
        else "search"
    )
    return GuideQuery(
        intent=intent,
        semantic=text or None,
        category_path=category_path,
        filters=filters,
        price=_parse_price(text),
        size_profile=GuideSizeProfile(
            height_cm=_parse_height(text),
            weight_kg=_parse_weight(text),
            usual_size=None,
        ),
    )


def _profile_int(value: object, low: int, high: int) -> int | None:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def merge_guide_query(
    previous: GuideQuery | None,
    new: GuideQuery,
    profile: dict[str, Any] | None = None,
) -> GuideQuery:
    """合并多轮槽位：新条件覆盖旧条件，切换品类时清空旧筛选。"""
    profile = profile or {}
    if new.intent == "add_to_cart":
        return new.model_copy(deep=True)
    if previous is None or new.intent == "chitchat":
        merged = new.model_copy(deep=True)
    else:
        semantic = new.semantic or ""
        reset = any(word in semantic for word in RESET_WORDS)
        if (
            new.category_path
            and previous.category_path
            and new.category_path[-1] != previous.category_path[-1]
        ):
            reset = True
        if reset:
            merged = new.model_copy(deep=True)
        else:
            filters = {
                key: list(values)
                for key, values in previous.filters.items()
                if values
            }
            for key, values in new.filters.items():
                if values:
                    filters[key] = list(values)
            price = previous.price.model_copy()
            if new.price.min is not None:
                price.min = new.price.min
            if new.price.max is not None:
                price.max = new.price.max
            if any(word in semantic for word in PRICE_CLEAR_WORDS):
                price = GuidePrice()
            size_profile = previous.size_profile.model_copy()
            for field in ("height_cm", "weight_kg", "usual_size"):
                value = getattr(new.size_profile, field)
                if value is not None:
                    setattr(size_profile, field, value)
            merged = GuideQuery(
                intent=new.intent,
                semantic=new.semantic or previous.semantic,
                category_path=new.category_path or list(previous.category_path),
                filters=normalize_filters(filters),
                price=price,
                size_profile=size_profile,
            )

    if merged.size_profile.height_cm is None:
        merged.size_profile.height_cm = _profile_int(
            profile.get("height_cm"), 100, 250
        )
    if merged.size_profile.weight_kg is None:
        merged.size_profile.weight_kg = _profile_int(
            profile.get("weight_kg"), 20, 300
        )
    if merged.size_profile.usual_size is None:
        merged.size_profile.usual_size = profile.get("usual_size")
    merged.filters = normalize_filters(merged.filters)
    return merged


def default_reason(candidate: dict[str, Any]) -> str:
    """重排不可用时的兜底推荐理由。"""
    attributes = candidate.get("attributes") or {}
    parts: list[str] = []
    for key, label in (("color", "颜色"), ("material", "材质"), ("thickness", "厚薄")):
        value = attributes.get(key)
        if value:
            parts.append(f"{label}{value}")
    return "、".join(parts) or "符合你的需求"


def query_condition_text(query: GuideQuery) -> str:
    """把槽位拼成一句简短条件，用于本地总结。"""
    parts: list[str] = []
    if query.category_path:
        parts.append(query.category_path[-1])
    for key, label in (("color", "颜色"), ("material", "材质"), ("thickness", "厚薄")):
        values = query.filters.get(key) or []
        if values:
            parts.append(f"{label}{'、'.join(values)}")
    if query.price.min is not None:
        parts.append(f"{query.price.min:g} 元以上")
    if query.price.max is not None:
        parts.append(f"{query.price.max:g} 元以内")
    return "、".join(parts)
