"""商品图提示词构建：固定模板 + CSV 属性填充，不走 LLM，保证 300 张可复现。"""

from __future__ import annotations

import re

PRODUCT_COLUMNS = [
    "id",
    "category",
    "subcategory",
    "color",
    "color_hex",
    "material",
    "fit",
    "thickness",
    "style",
    "gender",
    "key_feature",
]

DEFAULT_TEMPLATE = (
    "电商商品目录图，{category}{subcategory}，{color}（{color_hex}），"
    "{material}，{fit}版型，{thickness}，{style}风格，{gender}款。"
    "关键特征：{key_feature}。构图：{composition}。{background}，"
    "柔和影棚光，轻微自然阴影，产品完整居中，正方形构图。"
    "无模特、无人物、无手部、无文字、无数字、无标签、无logo、无水印、"
    "无道具、无多商品同框。真实材质质感，颜色准确，电商目录图风格。"
)

LIGHT_COLORS = {"白色", "米白", "奶白", "浅灰"}
LIGHT_HEX = {"#F5F5F5", "#EFE8DA", "#FFFFFF", "#FAFAFA", "#F2F2F2"}


def composition_for(row: dict) -> str:
    """按品类/子品类给出构图描述。"""
    category = (row.get("category") or "").strip()
    subcategory = (row.get("subcategory") or "").strip()
    text = category + subcategory

    if "连衣裙" in text or "裙" in subcategory:
        return "隐形模特挂拍，裙摆完整，正面视角"
    if "裤" in text:
        return "正面平铺 flat lay，腰头朝上，裤腿自然展开"
    if category == "服装":
        return "正面平铺 flat lay，领口、袖口、下摆完整"
    if category == "鞋靴":
        return "45° 侧面视角，鞋头方向一致，鞋底纹路清晰"
    if category == "箱包":
        return "正面 3/4 视角，展示轮廓、提手和五金"
    if category == "配饰":
        return "平铺俯拍，单个主体"
    return "正面平铺或正面 3/4 视角，产品完整居中"


def background_for(row: dict) -> str:
    """白色/米白商品用浅灰背景，避免轮廓和背景融合。"""
    color = (row.get("color") or "").strip()
    color_hex = (row.get("color_hex") or "").strip().upper()
    if color in LIGHT_COLORS or color_hex in LIGHT_HEX:
        return "背景为极浅灰 #F2F2F2，保留产品轮廓阴影，避免浅色商品与背景融合"
    return "纯白背景 #FFFFFF"


def row_to_values(row: dict) -> dict[str, str]:
    values = {key: (row.get(key) or "").strip() for key in PRODUCT_COLUMNS}
    values["composition"] = composition_for(row)
    values["background"] = background_for(row)
    return values


_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def build_prompt(row: dict, template: str = DEFAULT_TEMPLATE) -> str:
    """把 CSV 行填进模板；未知占位符原样保留，方便用户排查。"""
    values = row_to_values(row)

    def replace(match: re.Match) -> str:
        return values.get(match.group(1), match.group(0))

    prompt = _PLACEHOLDER.sub(replace, template or "")
    return re.sub(r"\s+", " ", prompt).strip()


def validate_rows(rows: list[dict]) -> list[str]:
    """返回校验错误列表；空列表表示通过。"""
    if not rows:
        return ["CSV 没有数据行"]

    errors: list[str] = []
    missing_columns = [col for col in PRODUCT_COLUMNS if col not in rows[0]]
    if missing_columns:
        errors.append("CSV 缺少列：" + ", ".join(missing_columns))
        return errors

    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=2):
        row_id = (row.get("id") or "").strip()
        if not row_id:
            errors.append(f"第 {index} 行缺少 id")
        elif row_id in seen_ids:
            errors.append(f"第 {index} 行 id 重复：{row_id}")
        seen_ids.add(row_id)

        for key in ("category", "color"):
            if not (row.get(key) or "").strip():
                errors.append(f"第 {index} 行缺少 {key}")

    return errors
