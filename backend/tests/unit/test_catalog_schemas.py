from app.modules.catalog.schemas import AttributeSchema, ProductPage
from app.modules.catalog.service import merge_attribute_schema


def test_merge_attribute_schema_leaf_overrides_parent():
    parent = {
        "attributes": [
            {
                "key": "color",
                "label": "颜色",
                "type": "enum",
                "options": ["黑"],
                "filterable": True,
            },
            {
                "key": "material",
                "label": "材质",
                "type": "enum",
                "options": ["棉"],
                "filterable": True,
            },
        ]
    }
    leaf = {
        "attributes": [
            {
                "key": "material",
                "label": "材质",
                "type": "enum",
                "options": ["亚麻"],
                "filterable": True,
            },
            {
                "key": "collar_type",
                "label": "领型",
                "type": "enum",
                "options": ["翻领"],
                "filterable": True,
            },
        ]
    }
    merged = merge_attribute_schema(parent, leaf)
    assert [item["key"] for item in merged["attributes"]] == [
        "color",
        "material",
        "collar_type",
    ]
    assert merged["attributes"][1]["options"] == ["亚麻"]
    assert AttributeSchema.model_validate(merged).attributes[2].label == "领型"


def test_product_page_shape():
    page = ProductPage(items=[], total=0, page=1, page_size=20)
    assert page.model_dump() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
    }
