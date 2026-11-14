from __future__ import annotations

import re
from dataclasses import dataclass

LETTER_SIZE_ORDER = {
    "XS": 0,
    "S": 1,
    "M": 2,
    "L": 3,
    "XL": 4,
    "XXL": 5,
    "XXXL": 6,
}
STOCK_WORDS = ("有货", "现货", "库存", "缺货", "补货", "还有吗", "有吗", "有没有")
AVAILABILITY_HINTS = (
    "有没有",
    "有吗",
    "还有吗",
    "还有没有",
    "有货",
    "现货",
    "库存",
    "缺货",
    "补货",
)
SIZE_WORD_RE = re.compile(r"(?:尺码|码数|码|号)")
LETTER_SIZE_RE = re.compile(
    r"(?<![A-Za-z])(XXXL|XXL|XL|XS|S|M|L)(?![A-Za-z])",
    re.IGNORECASE,
)
NUMERIC_SIZE_WITH_WORD_RE = re.compile(r"(?<!\d)(\d{2,3})\s*(?:尺码|码数|码|号)")
BARE_NUMERIC_SIZE_RE = re.compile(r"(?<!\d)(\d{2})(?!\d)")


@dataclass(frozen=True)
class SizeQuery:
    requested_size: str | None
    is_availability: bool
    mentions_size: bool


def normalize_size(value: object) -> str:
    text = str(value).strip()
    return text if text.isdigit() else text.upper()


def collect_size_options(
    stock_by_size: dict[str, int],
    attribute_size: object = None,
    size_chart: dict | None = None,
) -> list[str]:
    """从库存、商品属性、尺码表中收集可选尺码，按优先级去重。"""
    options: list[str] = [normalize_size(size) for size in stock_by_size]
    if not options:
        if isinstance(attribute_size, list):
            options = [normalize_size(item) for item in attribute_size]
        elif isinstance(attribute_size, str):
            options = [
                normalize_size(item)
                for item in re.split(r"[、,，/]", attribute_size)
                if item.strip()
            ]
    if not options and size_chart:
        options = [
            normalize_size(row.get("size"))
            for row in size_chart.get("rows", [])
            if row.get("size")
        ]
    return list(dict.fromkeys(item for item in options if item))


def _letter_sort_key(size: str) -> tuple[int, float | str]:
    if size.isdigit():
        return (0, int(size))
    if size.upper() in LETTER_SIZE_ORDER:
        return (1, LETTER_SIZE_ORDER[size.upper()])
    return (2, size)


def sorted_sizes(sizes: list[str]) -> list[str]:
    return sorted(dict.fromkeys(normalize_size(size) for size in sizes), key=_letter_sort_key)


def format_sizes(sizes: list[str]) -> str:
    ordered = sorted_sizes(sizes)
    if not ordered:
        return ""
    if len(ordered) == 1:
        return ordered[0]
    if all(size.isdigit() for size in ordered):
        numbers = [int(size) for size in ordered]
        groups: list[tuple[int, int]] = []
        start = previous = numbers[0]
        for number in numbers[1:]:
            if number == previous + 1:
                previous = number
            else:
                groups.append((start, previous))
                start = previous = number
        groups.append((start, previous))
        return "、".join(
            str(low) if low == high else f"{low}-{high}"
            for low, high in groups
        )
    return "、".join(ordered)


def size_phrase(sizes: list[str]) -> str:
    text = format_sizes(sizes)
    return text if text.endswith("码") else f"{text} 码"


def _option_text(phrase: str) -> str:
    return phrase if phrase == "均码" else f" {phrase}"


def extract_requested_size(question: str, known_sizes: list[str] | None = None) -> str | None:
    known = [normalize_size(size) for size in (known_sizes or [])]
    upper_question = question.upper()

    # 先匹配商品已有的尺码，避免把 XL 里的 L 或 40 里的 4 识别错
    for size in sorted(known, key=len, reverse=True):
        if size.isdigit():
            pattern = rf"(?<!\d){re.escape(size)}(?!\d)"
        else:
            pattern = rf"(?<![A-Za-z]){re.escape(size)}(?![A-Za-z])"
        if re.search(pattern, upper_question):
            return size

    if "均码" in question:
        return "均码"

    numeric = NUMERIC_SIZE_WITH_WORD_RE.search(question)
    if numeric:
        return numeric.group(1)

    letter = LETTER_SIZE_RE.search(question)
    if letter:
        return normalize_size(letter.group(1))

    # 只有商品本身用数字尺码时，才允许“有40的吗”省略“码”字
    if any(size.isdigit() for size in known) or SIZE_WORD_RE.search(question):
        bare = BARE_NUMERIC_SIZE_RE.search(question)
        if bare:
            return bare.group(1)
    return None


def parse_size_query(question: str, known_sizes: list[str] | None = None) -> SizeQuery:
    requested = extract_requested_size(question, known_sizes)
    mentions_size = bool(
        requested
        or LETTER_SIZE_RE.search(question)
        or NUMERIC_SIZE_WITH_WORD_RE.search(question)
        or "均码" in question
    )
    is_availability = any(word in question for word in AVAILABILITY_HINTS) or (
        "有" in question and ("吗" in question or "么" in question)
    )
    return SizeQuery(
        requested_size=requested,
        is_availability=is_availability,
        mentions_size=mentions_size,
    )


def has_stock_word(question: str) -> bool:
    return any(word in question for word in STOCK_WORDS)


def build_size_availability_answer(
    stock_by_size: dict[str, int],
    size_options: list[str],
    query: SizeQuery,
) -> str | None:
    """用商品的尺码/库存事实回答“有没有某个尺码”；无法判断时返回 None。"""
    if not query.is_availability:
        return None
    stock = {
        normalize_size(size): int(count)
        for size, count in stock_by_size.items()
    }
    options = list(dict.fromkeys(normalize_size(size) for size in size_options))
    if not options:
        options = list(stock)
    if not options:
        return None

    requested = query.requested_size
    if requested:
        requested = normalize_size(requested)
        if requested in options:
            if requested not in stock:
                return None
            if stock[requested] > 0:
                return f"有的，{requested} 码目前有货。"
            available = [size for size in options if stock.get(size, 0) > 0]
            if available:
                return (
                    f"不好意思，{requested} 码暂时缺货，"
                    f"目前可选{_option_text(size_phrase(available))}。"
                )
            return f"不好意思，{requested} 码暂时缺货，这款目前全部尺码都没货。"

        available = [size for size in options if stock.get(size, 0) > 0]
        if available:
            return (
                f"不好意思，这款没有 {requested} 码，"
                f"可选尺码是{_option_text(size_phrase(available))}。"
            )
        return f"不好意思，这款没有 {requested} 码，目前也暂时缺货。"

    if not stock:
        return None
    available = [size for size in options if stock.get(size, 0) > 0]
    unavailable = [size for size in options if stock.get(size, 0) <= 0]
    if available:
        if unavailable:
            return (
                f"有的，目前{_option_text(size_phrase(available))}有货；"
                f"{size_phrase(unavailable)}暂时缺货。"
            )
        return f"有的，目前{_option_text(size_phrase(available))}都有货。"
    return "不好意思，这款目前暂时缺货。"
