from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AttributeType = Literal["enum", "multi_enum", "tags", "string", "number"]
SortOption = Literal["recommended", "price_asc", "price_desc"]


class AttributeDef(BaseModel):
    key: str
    label: str
    type: AttributeType = "enum"
    options: list[str] | None = None
    filterable: bool = False


class AttributeSchema(BaseModel):
    attributes: list[AttributeDef] = Field(default_factory=list)


class SizeChartRow(BaseModel):
    size: str
    height: list[int] | None = None
    weight: list[int] | None = None
    chest: list[int] | None = None
    waist: list[int] | None = None
    foot_length: list[int] | None = None


class SizeChart(BaseModel):
    type: Literal["clothing", "shoes"]
    unit: str
    rows: list[SizeChartRow]


class CategoryNode(BaseModel):
    id: int
    parent_id: int | None
    name: str
    slug: str
    level: int
    sort_order: int
    attribute_schema: AttributeSchema
    size_chart_template: SizeChart | None = None
    children: list[CategoryNode] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProductSummary(BaseModel):
    id: int
    product_code: str
    category_id: int
    title: str
    price: float
    original_price: float | None
    main_image: str | None
    brand: str | None
    sales_count: int

    model_config = ConfigDict(from_attributes=True)


class SkuOut(BaseModel):
    id: int
    color: str
    size: str
    stock: int
    price: float
    status: str


class ProductDetail(ProductSummary):
    description: str | None
    images: list[str]
    attributes: dict[str, Any]
    attribute_schema: AttributeSchema
    size_chart: SizeChart | None
    category_name: str
    parent_category_name: str | None
    skus: list[SkuOut]
    is_favorited: bool = False


class ProductPage(BaseModel):
    items: list[ProductSummary]
    total: int
    page: int
    page_size: int


class FavoriteState(BaseModel):
    favorited: bool


CategoryNode.model_rebuild()
