from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.size_rules import LETTER_SIZE_ORDER, normalize_size
from app.modules.auth.models import User
from app.modules.catalog.models import Category, Product


@dataclass
class SizeRecommendation:
    """按用户档案与商品尺码表得到的推荐尺码。"""

    recommended_size: str | None
    size_reason: str
    source: str | None = None


def _rows(size_chart: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [
        row
        for row in (size_chart or {}).get("rows") or []
        if isinstance(row, dict) and row.get("size")
    ]


def _size_rank(size: str) -> int:
    normalized = normalize_size(size)
    if normalized.isdigit():
        return 100 + int(normalized)
    return LETTER_SIZE_ORDER.get(normalized.upper(), -1)


def _axis_distance(value: float, bounds: list[int] | None) -> float:
    if not bounds or len(bounds) != 2:
        return 0.0
    low, high = float(bounds[0]), float(bounds[1])
    half = max((high - low) / 2, 1.0)
    center = (low + high) / 2
    if low <= value <= high:
        return abs(value - center) / half
    nearest = low if value < low else high
    return abs(value - nearest) / half + 1.0


def _distance(row: dict[str, Any], height_cm: int, weight_kg: int) -> float:
    return _axis_distance(height_cm, row.get("height")) + _axis_distance(
        weight_kg, row.get("weight")
    )


def _within(row: dict[str, Any], height_cm: int, weight_kg: int) -> bool:
    height = row.get("height") or []
    weight = row.get("weight") or []
    return (
        len(height) == 2
        and len(weight) == 2
        and height[0] <= height_cm <= height[1]
        and weight[0] <= weight_kg <= weight[1]
    )


def _range_text(row: dict[str, Any], unit: str) -> str:
    parts: list[str] = []
    for key, label, suffix in (
        ("height", "身高", unit),
        ("weight", "体重", "kg"),
        ("foot_length", "脚长", "mm"),
    ):
        bounds = row.get(key)
        if isinstance(bounds, list) and len(bounds) == 2:
            parts.append(f"{label}{bounds[0]}-{bounds[1]}{suffix}")
    return "，".join(parts)


def recommend_size(
    size_chart: dict[str, Any] | None,
    height_cm: int | None,
    weight_kg: int | None,
    usual_size: str | None = None,
) -> SizeRecommendation:
    """按设计文档 §9.2.5：精确命中 → 中心距离最小；否则最近行并建议试穿。"""
    rows = _rows(size_chart)
    if not rows:
        return SizeRecommendation(None, "该商品暂未提供尺码表。")

    chart_type = (size_chart or {}).get("type")
    if chart_type == "shoes":
        sizes = [normalize_size(row["size"]) for row in rows]
        usual = normalize_size(usual_size) if usual_size else None
        if usual and usual in sizes:
            return SizeRecommendation(
                usual,
                f"按你常穿的 {usual} 码推荐，建议结合脚长确认。",
                "usual_size",
            )
        return SizeRecommendation(
            None,
            "鞋款需要脚长才能推荐尺码，可参考尺码表或咨询客服。",
        )

    if height_cm is None or weight_kg is None:
        return SizeRecommendation(
            None,
            "补充身高体重后可获得更准确的尺码推荐。",
        )

    usable = [
        row
        for row in rows
        if isinstance(row.get("height"), list)
        and len(row["height"]) == 2
        and isinstance(row.get("weight"), list)
        and len(row["weight"]) == 2
    ]
    if not usable:
        return SizeRecommendation(
            None,
            "尺码表缺少身高体重区间，建议参考尺码表。",
        )

    exact = [row for row in usable if _within(row, height_cm, weight_kg)]
    pool = exact or usable
    best = min(
        pool,
        key=lambda row: (
            _distance(row, height_cm, weight_kg),
            -_size_rank(str(row["size"])),
            str(row["size"]),
        ),
    )
    size = normalize_size(best["size"])
    detail = _range_text(best, str((size_chart or {}).get("unit", "cm")))
    if exact:
        reason = (
            f"身高 {height_cm}cm、体重 {weight_kg}kg 对应 {size} 码"
            f"（{detail}）。"
        )
    else:
        reason = f"最接近 {size} 码（{detail}），建议试穿确认。"
    return SizeRecommendation(size, reason, "profile")


async def resolve_size_chart(
    db: AsyncSession, product: Product
) -> dict[str, Any] | None:
    """商品自身尺码表优先，其次叶子品类，最后一级品类模板。"""
    if product.size_chart:
        return product.size_chart
    category = await db.get(Category, product.category_id)
    if category is None:
        return None
    if category.size_chart_template:
        return category.size_chart_template
    if category.parent_id is not None:
        parent = await db.get(Category, category.parent_id)
        if parent is not None and parent.size_chart_template:
            return parent.size_chart_template
    return None


async def recommend_product_size(
    db: AsyncSession, product: Product, user: User
) -> SizeRecommendation:
    chart = await resolve_size_chart(db, product)
    return recommend_size(
        chart,
        user.height_cm,
        user.weight_kg,
        user.usual_size,
    )
