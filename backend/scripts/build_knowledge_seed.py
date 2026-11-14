"""从商品/品类种子生成知识库种子 JSON 与审核 CSV。

规则化内容标 approved；品类 FAQ 草稿标 pending，不写入 knowledge.json。
默认拒绝覆盖已有文件；确需重建时加 --force。测试可用 --output-dir 指定临时目录。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any, Callable

BACKEND_DIR = Path(__file__).resolve().parents[1]
CATEGORY_FILE = BACKEND_DIR / "seeds" / "catalog" / "categories.json"
PRODUCT_FILE = BACKEND_DIR / "seeds" / "catalog" / "products.json"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "seeds" / "knowledge"

CARE_RULES: list[tuple[tuple[str, ...], str]] = [
    (
        ("羊绒", "羊毛", "毛呢", "毛混纺", "牦牛绒"),
        "羊毛/羊绒类建议 30℃ 以下冷水手洗或干洗，使用中性洗涤剂，平铺阴干，"
        "不要高温烘干和暴晒，减少与粗糙表面摩擦以降低起球。",
    ),
    (
        ("真丝", "桑蚕丝"),
        "真丝建议冷水手洗或干洗，使用中性洗涤剂，不要拧干和暴晒，"
        "阴干后低温熨烫，避免接触香水和尖锐物。",
    ),
    (
        ("亚麻", "棉麻"),
        "亚麻/棉麻建议 30℃ 以下冷水机洗或手洗，反面晾晒，不要高温烘干，"
        "初次清洗可单独洗涤，穿着前可低温熨烫。",
    ),
    (
        ("纯棉", "棉混纺", "棉"),
        "棉质建议 30℃ 以下冷水机洗，深浅色分开，反面晾晒，不要长时间浸泡，"
        "避免高温烘干导致缩水。",
    ),
    (
        ("牛仔",),
        "牛仔建议反面冷水洗涤，减少掉色，不要漂白，阴干；首次清洗可加少量盐固色。",
    ),
    (
        ("皮革", "PU", "漆皮", "绒面"),
        "皮革/PU 类不建议水洗，用湿布轻擦并定期使用专用护理剂，"
        "避免暴晒、雨淋和高温烘烤。",
    ),
    (
        ("飞织", "网布", "EVA", "橡胶"),
        "鞋面可软刷蘸清水局部清洁，鞋垫取出阴干，不要机洗、暴晒或长时间浸泡；"
        "EVA/橡胶底避免高温。",
    ),
    (
        ("帆布", "尼龙", "牛津纺", "涤纶", "聚酯纤维", "锦纶", "腈纶", "莫代尔", "雪纺"),
        "建议 30℃ 以下轻柔机洗或手洗，使用洗衣袋，反面晾晒，不要高温烘干；"
        "雪纺/针织类注意避免勾挂。",
    ),
    (
        ("针织", "抓绒", "织物"),
        "针织/织物建议反面轻柔洗涤，平铺阴干，不要悬挂拉扯，避免与魔术贴等粗糙面摩擦。",
    ),
    (
        ("925银", "钛钢", "不锈钢", "合金", "金属"),
        "金属/银饰避免接触香水、汗液和化学品，佩戴后用软布擦拭，密封干燥保存。",
    ),
    (
        ("ABS", "TR90", "聚碳酸酯", "板材", "硅胶"),
        "用清水或中性清洁剂轻擦，避免酒精、高温和硬物刮擦。",
    ),
    (
        ("草编",),
        "草编建议干布擦拭，避免水洗和长时间暴晒，受潮后阴干。",
    ),
]

CATEGORY_CARE = {
    "clothing": (
        "服装类通用洗护：先查看商品成分标签。棉/亚麻可 30℃ 以下冷水洗涤、反面晾晒；"
        "羊毛/羊绒建议冷水手洗或干洗、平铺阴干；真丝建议中性洗涤剂冷水手洗或干洗；"
        "深浅色分开洗涤，避免高温烘干和长时间浸泡。"
    ),
    "footwear": (
        "鞋靴类通用保养：新鞋可先穿厚袜短时间试穿适应；皮革鞋用湿布擦拭并定期护理，"
        "网布/飞织鞋用软刷局部清洁，帆布鞋可冷水手洗但需阴干；"
        "不要机洗、暴晒或长时间浸泡，鞋垫取出单独晾干。"
    ),
    "bags": (
        "箱包类通用保养：帆布包可冷水轻柔手洗、阴干；皮革包用湿布擦拭并定期使用护理剂，"
        "避免雨淋和暴晒；行李箱用湿布清洁外壳，五金件保持干燥；"
        "存放时填充定型物，避免重压和尖锐物刮擦。"
    ),
    "accessories": (
        "配饰类通用保养：银饰/合金饰品避免接触香水、汗液和化学品，佩戴后软布擦拭并密封保存；"
        "帽子/围巾按材质轻柔手洗、平铺阴干；皮带避免水洗和暴晒，定期使用皮革护理剂。"
    ),
}

PLATFORM_POLICIES: list[tuple[str, str]] = [
    (
        "发货时效",
        "平台商品一般在付款后 48 小时内发货，节假日顺延。发货后可在订单详情查看物流单号，"
        "通常 2~5 天送达；偏远地区可能延迟。预售商品以商品页标注的发货时间为准。",
    ),
    (
        "退换货政策",
        "支持 7 天无理由退换货，商品需保持吊牌完整、不影响二次销售；"
        "贴身衣物、定制商品等特殊品类不支持无理由退换。质量问题请在签收后 48 小时内联系客服并提供照片。",
    ),
    (
        "退款说明",
        "退款原路退回，审核通过后 1~3 个工作日到账，具体到账时间以支付渠道为准。"
        "未发货订单可直接取消并退款；已发货订单需先申请退货，仓库验收后发起退款。",
    ),
    (
        "支付方式",
        "当前演示环境支持模拟支付，正式环境支持微信支付和支付宝。"
        "下单后请在 15 分钟内完成支付，超时订单会自动取消并恢复库存。",
    ),
    (
        "发票说明",
        "支持开具电子普通发票，可在订单完成后 30 天内联系客服提供抬头和税号。"
        "发票金额以实付金额为准，优惠券抵扣部分不重复开票。",
    ),
    (
        "优惠券使用",
        "优惠券需在有效期内使用，单笔订单限用一张，是否可叠加以券面说明为准。"
        "使用优惠券的订单发生退款时，优惠券按平台规则退回或作废。",
    ),
    (
        "运费说明",
        "单笔订单实付满 99 元包邮，偏远地区除外；未满 99 元收取基础运费 8 元。"
        "退换货产生的运费按责任方承担：质量问题由平台承担，无理由退换由用户承担。",
    ),
    (
        "订单取消与修改",
        "待支付订单可在订单详情直接取消；已支付未发货订单可联系客服取消。"
        "订单一旦发货，无法修改收货地址或商品，建议拒收后按退货流程处理。",
    ),
    (
        "客服服务时间",
        "AI 客服 7×24 小时在线，人工客服服务时间为每日 9:00~21:00。"
        "非服务时间可留言转人工，客服上线后会按排队顺序处理。",
    ),
]

CATEGORY_FAQ_DRAFTS = {
    "clothing": [
        ("棉质衣服第一次洗会缩水吗？", "棉质首次清洗建议冷水、反面、短时间洗涤，避免高温烘干，通常不会明显缩水。"),
        ("羊毛衫怎么洗才不起球？", "建议冷水手洗或干洗，使用中性洗涤剂，平铺阴干，减少摩擦和长时间悬挂。"),
        ("衬衫尺码应该怎么选？", "可参考商品尺码表的身高、体重、胸围和腰围范围，介于两个尺码之间时偏宽松选小一码、偏合身选大一码。"),
        ("深色衣服会掉色吗？", "首次清洗建议单独冷水洗涤，不要长时间浸泡；深浅色分开可减少串色。"),
        ("外套可以机洗吗？", "需查看成分标签和商品详情洗护说明，羊毛/皮革类不建议机洗，棉/涤纶类可轻柔机洗。"),
        ("针织衫变形了怎么恢复？", "可冷水浸湿后轻轻整形，平铺阴干，不要悬挂或高温烘干。"),
    ],
    "footwear": [
        ("新鞋磨脚怎么办？", "可先穿厚袜短时间适应，或在磨脚处贴防磨贴；皮革鞋可适当软化，不要暴力撑大。"),
        ("皮鞋淋雨了怎么处理？", "先用干布吸干水分，塞入纸团定型，阴干后使用皮革护理剂，不要暴晒或烘烤。"),
        ("运动鞋可以机洗吗？", "不建议机洗，可用软刷蘸清水局部清洁，鞋垫取出阴干，避免长时间浸泡。"),
        ("鞋码偏大偏小怎么选？", "参考商品页脚长范围，脚背高或喜欢厚袜可适当选大半码，介于两码之间建议选大一码。"),
        ("帆布鞋怎么防止发黄？", "清洗后用纸巾包裹鞋面阴干，避免阳光直射和高温烘干。"),
        ("鞋底发黄怎么清洁？", "可用软刷和中性清洁剂轻刷，避免漂白剂，清洁后阴干。"),
    ],
    "bags": [
        ("帆布包怎么清洗？", "可冷水轻柔手洗，使用中性洗涤剂，阴干，不要机洗甩干和暴晒。"),
        ("皮革包怎么保养？", "用湿布轻擦，定期使用皮革护理剂，避免雨淋、暴晒和重压。"),
        ("行李箱尺寸怎么选？", "20 寸适合短途登机，24 寸适合 3~5 天出行，28 寸适合长途或家庭出行，具体以航司规定为准。"),
        ("包包五金掉色怎么办？", "避免接触汗液和化学品，使用后软布擦拭并保持干燥；轻微掉色可使用专用护理布。"),
        ("双肩包可以放电脑吗？", "请查看商品详情中的电脑夹层尺寸，建议电脑尺寸不超过夹层标注上限。"),
        ("包包有异味怎么处理？", "放在通风处阴干，可放入活性炭包，避免暴晒和喷香水。"),
    ],
    "accessories": [
        ("银饰变黑怎么清洗？", "可用软布蘸少量银饰清洁剂轻擦，避免用力刮擦，清洁后保持干燥密封。"),
        ("帽子怎么清洗？", "按材质轻柔手洗，使用中性洗涤剂，平铺阴干，避免高温烘干变形。"),
        ("围巾起球正常吗？", "羊毛/羊绒围巾摩擦后可能有轻微起球，可用毛球修剪器轻轻处理。"),
        ("腰带尺码怎么选？", "参考商品页腰围范围，通常选比平时裤装腰围大一档的尺寸，具体以尺码表为准。"),
        ("手表可以戴着洗澡吗？", "除标注防水的款式外，不建议佩戴洗澡、游泳或蒸桑拿，避免水汽进入。"),
        ("墨镜镜片怎么保养？", "用镜布和中性清洁剂擦拭，避免用纸巾干擦和高温暴晒。"),
    ],
}

FAQ_BANK: list[tuple[str, Callable[[dict[str, Any], str], tuple[str, str]]]] = []


def _range_text(value: Any, unit: str = "") -> str:
    if isinstance(value, list) and len(value) == 2:
        return f"{value[0]}-{value[1]}{unit}"
    return ""


def care_for(material: str) -> str:
    for keywords, text in CARE_RULES:
        if any(keyword in material for keyword in keywords):
            return text
    return (
        "建议按商品洗护标签护理，优先冷水、轻柔洗涤、反面晾晒，"
        "避免高温烘干和长时间浸泡。"
    )


def _season_text(attributes: dict[str, Any]) -> str:
    season = attributes.get("season")
    if isinstance(season, list) and season:
        return "、".join(str(item) for item in season)
    return "四季"


def _faq_material(product: dict[str, Any], care: str) -> tuple[str, str]:
    attributes = product["attributes"]
    question = f"{product['title']}是什么材质？"
    answer = (
        f"{product['title']}的材质是{attributes.get('material', '未标注')}，"
        f"版型为{attributes.get('fit', '常规')}，厚薄为{attributes.get('thickness', '常规')}。"
        f"洗护建议：{care}"
    )
    return question, answer


def _faq_care(product: dict[str, Any], care: str) -> tuple[str, str]:
    question = f"{product['title']}怎么清洗和保养？"
    return question, f"{product['title']}的洗护方式：{care}"


def _faq_thickness(product: dict[str, Any], care: str) -> tuple[str, str]:
    attributes = product["attributes"]
    question = f"{product['title']}厚薄怎么样，适合什么季节？"
    answer = (
        f"{product['title']}为{attributes.get('thickness', '常规')}，"
        f"适合{_season_text(attributes)}穿着，风格偏{attributes.get('style', '日常')}。"
    )
    return question, answer


def _faq_fit(product: dict[str, Any], care: str) -> tuple[str, str]:
    attributes = product["attributes"]
    question = f"{product['title']}版型偏大还是偏小？"
    answer = (
        f"{product['title']}的版型为{attributes.get('fit', '常规')}，"
        "建议参考商品尺码表的身高、体重和围度范围选择；介于两个尺码之间时可按穿着偏好调整。"
    )
    return question, answer


def _faq_pilling(product: dict[str, Any], care: str) -> tuple[str, str]:
    material = product["attributes"].get("material", "")
    question = f"{product['title']}会起球吗？"
    if any(word in material for word in ("羊毛", "羊绒", "针织", "抓绒", "毛混纺")):
        answer = (
            f"{product['title']}含{material}成分，摩擦较多时可能出现轻微起球，"
            "建议减少与粗糙表面摩擦，按洗护说明打理，必要时使用毛球修剪器。"
        )
    else:
        answer = (
            f"{product['title']}的材质为{material}，正常穿着和按说明洗护时不易起球。"
        )
    return question, answer


def _faq_color(product: dict[str, Any], care: str) -> tuple[str, str]:
    attributes = product["attributes"]
    question = f"{product['title']}实物颜色和图片会有色差吗？"
    answer = (
        f"{product['title']}的颜色为{attributes.get('color', '如图')}，"
        "商品图尽量还原实物，但不同屏幕和光线可能有轻微色差，属正常现象。"
    )
    return question, answer


def _faq_size(product: dict[str, Any], care: str) -> tuple[str, str]:
    chart = product.get("size_chart") or {}
    rows = chart.get("rows") or []
    question = f"{product['title']}怎么选尺码？"
    if rows:
        first, last = rows[0], rows[-1]
        if chart.get("type") == "shoes":
            answer = (
                f"{product['title']}可选尺码 {first['size']}~{last['size']}，"
                f"脚长参考 {_range_text(first.get('foot_length'))} 到 "
                f"{_range_text(last.get('foot_length'))}。"
            )
        else:
            answer = (
                f"{product['title']}可选尺码 {first['size']}~{last['size']}，"
                f"身高参考 {_range_text(first.get('height'))} 到 "
                f"{_range_text(last.get('height'))}，"
                f"体重参考 {_range_text(first.get('weight'))} 到 "
                f"{_range_text(last.get('weight'))}。"
            )
    else:
        sizes = product["attributes"].get("size") or []
        answer = f"{product['title']}可选尺码：{'、'.join(sizes)}，请结合尺码表选择。"
    return question, answer


def _faq_stock(product: dict[str, Any], care: str) -> tuple[str, str]:
    stock = sum(int(sku.get("stock", 0)) for sku in product.get("skus", []))
    question = f"{product['title']}现在有现货吗？"
    if stock > 0:
        answer = (
            f"{product['title']}当前总库存约 {stock} 件，具体尺码库存以商品详情页为准。"
        )
    else:
        answer = f"{product['title']}当前暂时缺货，建议关注补货或咨询客服。"
    return question, answer


FAQ_BANK = [
    ("material", _faq_material),
    ("care", _faq_care),
    ("thickness", _faq_thickness),
    ("fit", _faq_fit),
    ("pilling", _faq_pilling),
    ("color", _faq_color),
    ("size", _faq_size),
    ("stock", _faq_stock),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_int(key: str) -> int:
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)


def build_detail_chunks(product: dict[str, Any], care: str) -> list[dict[str, Any]]:
    attributes = product["attributes"]
    title = product["title"]
    brand = product.get("brand") or "平台自有品牌"
    original = product.get("original_price")
    price_text = f"¥{product['price']:.2f}"
    if original:
        price_text += f"（划线价 ¥{original:.2f}）"
    overview = (
        f"{title}，商品编码 {product['product_code']}，品牌 {brand}。"
        f"材质：{attributes.get('material', '未标注')}；版型：{attributes.get('fit', '常规')}；"
        f"厚薄：{attributes.get('thickness', '常规')}；风格：{attributes.get('style', '日常')}；"
        f"适用人群：{attributes.get('gender', '通用')}；适用季节：{_season_text(attributes)}。"
        f"价格：{price_text}。"
    )
    features = attributes.get("key_features") or []
    feature_text = "、".join(str(item) for item in features) if features else "按商品设计"
    detail = (
        f"{title}的设计细节：{feature_text}。"
        f"{product.get('description') or ''}"
        f"适合{attributes.get('style', '日常')}风格的日常穿着。"
        f"洗护提示：{care}"
    )
    return [
        {
            "seed_key": f"product:{product['product_code']}:detail:1",
            "section": "概述与参数",
            "content": overview,
            "meta": {
                "section": "概述与参数",
                "doc_type": "detail",
                "seed_key": f"product:{product['product_code']}:detail:1",
            },
        },
        {
            "seed_key": f"product:{product['product_code']}:detail:2",
            "section": "设计细节与洗护",
            "content": detail,
            "meta": {
                "section": "设计细节与洗护",
                "doc_type": "detail",
                "seed_key": f"product:{product['product_code']}:detail:2",
            },
        },
    ]


def build_size_chunk(product: dict[str, Any]) -> list[dict[str, Any]]:
    chart = product.get("size_chart") or {}
    rows = chart.get("rows") or []
    unit = chart.get("unit", "cm")
    if rows:
        pieces: list[str] = []
        for row in rows:
            parts: list[str] = []
            for key, label in (
                ("height", "身高"),
                ("weight", "体重"),
                ("chest", "胸围"),
                ("waist", "腰围"),
                ("foot_length", "脚长"),
            ):
                value = row.get(key)
                if isinstance(value, list) and len(value) == 2:
                    parts.append(f"{label} {value[0]}-{value[1]}{unit}")
            if parts:
                pieces.append(f"{row['size']}：" + "，".join(parts))
        content = (
            f"{product['title']}的尺码指南。"
            + "；".join(pieces)
            + "。测量说明：身高体重为参考范围，介于两个尺码之间时，"
            "喜欢宽松可选大一码，喜欢合身可选小一码；脚长建议测量净脚长后加 0.5~1cm 余量。"
        )
    else:
        sizes = product["attributes"].get("size") or []
        content = (
            f"{product['title']}可选尺码：{'、'.join(str(item) for item in sizes)}。"
            "该商品为均码或固定尺码，建议结合商品详情中的尺寸说明选择。"
        )
    return [
        {
            "seed_key": f"product:{product['product_code']}:size:1",
            "section": "尺码表",
            "content": content,
            "meta": {
                "section": "尺码表",
                "doc_type": "size",
                "seed_key": f"product:{product['product_code']}:size:1",
            },
        }
    ]


def build_faq_chunks(product: dict[str, Any], care: str) -> list[dict[str, Any]]:
    rng = random.Random(_seed_int(f"{product['product_code']}:faq"))
    selected = sorted(rng.sample(range(len(FAQ_BANK)), 3))
    chunks: list[dict[str, Any]] = []
    for index, bank_index in enumerate(selected, start=1):
        key, builder = FAQ_BANK[bank_index]
        question, answer = builder(product, care)
        seed_key = f"product:{product['product_code']}:faq:{index}"
        chunks.append(
            {
                "seed_key": seed_key,
                "question": question,
                "section": key,
                "content": answer,
                "meta": {
                    "question": question,
                    "section": key,
                    "doc_type": "faq",
                    "seed_key": seed_key,
                },
            }
        )
    return chunks


def build_documents(
    categories: list[dict[str, Any]], products: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parent_by_slug = {item["slug"]: item for item in categories if item["level"] == 1}
    leaf_by_slug = {item["slug"]: item for item in categories if item["level"] == 2}
    documents: list[dict[str, Any]] = []
    draft_rows: list[dict[str, Any]] = []

    for product in products:
        care = care_for(product["attributes"].get("material", ""))
        leaf = leaf_by_slug[product["category_slug"]]
        parent_slug = leaf["parent_slug"]
        common = {
            "scope": "product",
            "product_code": product["product_code"],
            "parent_category_slug": parent_slug,
            "source": "seed",
        }
        documents.append(
            {
                **common,
                "seed_key": f"product:{product['product_code']}:detail",
                "doc_type": "detail",
                "title": f"{product['product_code']} {product['title']} · 商品详情",
                "chunks": build_detail_chunks(product, care),
            }
        )
        documents.append(
            {
                **common,
                "seed_key": f"product:{product['product_code']}:size",
                "doc_type": "size",
                "title": f"{product['product_code']} {product['title']} · 尺码指南",
                "chunks": build_size_chunk(product),
            }
        )
        documents.append(
            {
                **common,
                "seed_key": f"product:{product['product_code']}:faq",
                "doc_type": "faq",
                "title": f"{product['product_code']} {product['title']} · 常见问题",
                "chunks": build_faq_chunks(product, care),
            }
        )

    for parent_slug, parent in parent_by_slug.items():
        documents.append(
            {
                "scope": "category",
                "category_slug": parent_slug,
                "parent_category_slug": parent_slug,
                "seed_key": f"category:{parent_slug}:care",
                "doc_type": "care",
                "title": f"{parent['name']} · 通用洗护指南",
                "source": "seed",
                "chunks": [
                    {
                        "seed_key": f"category:{parent_slug}:care:1",
                        "section": "通用洗护",
                        "content": CATEGORY_CARE[parent_slug],
                        "meta": {
                            "section": "通用洗护",
                            "doc_type": "care",
                            "seed_key": f"category:{parent_slug}:care:1",
                        },
                    }
                ],
            }
        )
        for index, (question, answer) in enumerate(
            CATEGORY_FAQ_DRAFTS[parent_slug], start=1
        ):
            draft_rows.append(
                {
                    "scope": "category",
                    "category_slug": parent_slug,
                    "doc_type": "faq",
                    "title": f"{parent['name']} · 品类 FAQ 草稿",
                    "question": question,
                    "answer": answer,
                    "source": "seed",
                    "status": "pending",
                }
            )

    for index, (title, content) in enumerate(PLATFORM_POLICIES, start=1):
        documents.append(
            {
                "scope": "platform",
                "seed_key": f"platform:policy:{index}",
                "doc_type": "policy",
                "title": f"平台规则 · {title}",
                "source": "manual",
                "chunks": [
                    {
                        "seed_key": f"platform:policy:{index}:1",
                        "section": title,
                        "content": content,
                        "meta": {
                            "section": title,
                            "doc_type": "policy",
                            "seed_key": f"platform:policy:{index}:1",
                        },
                    }
                ],
            }
        )

    return documents, draft_rows


def validate(documents: list[dict[str, Any]], drafts: list[dict[str, Any]]) -> None:
    doc_counts: dict[str, int] = {}
    chunk_counts: dict[str, int] = {}
    for document in documents:
        doc_counts[document["doc_type"]] = doc_counts.get(document["doc_type"], 0) + 1
        for _ in document["chunks"]:
            chunk_counts[document["doc_type"]] = (
                chunk_counts.get(document["doc_type"], 0) + 1
            )
    expected_docs = {"detail": 300, "size": 300, "faq": 300, "care": 4, "policy": 9}
    expected_chunks = {"detail": 600, "size": 300, "faq": 900, "care": 4, "policy": 9}
    if doc_counts != expected_docs:
        raise SystemExit(f"文档数量错误：{doc_counts} != {expected_docs}")
    if chunk_counts != expected_chunks:
        raise SystemExit(f"chunk 数量错误：{chunk_counts} != {expected_chunks}")
    if len(drafts) != 24:
        raise SystemExit(f"品类 FAQ 草稿应为 24 条，实际 {len(drafts)}")
    seed_keys = [document["seed_key"] for document in documents]
    if len(set(seed_keys)) != len(seed_keys):
        raise SystemExit("文档 seed_key 重复")


def write_outputs(
    output_dir: Path,
    documents: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    knowledge = {
        "version": 1,
        "generated_from": "seeds/catalog/categories.json + products.json",
        "documents": documents,
    }
    (output_dir / "knowledge.json").write_text(
        json.dumps(knowledge, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "category_faq_drafts.json").write_text(
        json.dumps(
            {"version": 1, "status": "pending", "drafts": drafts},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with (output_dir / "review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "层级",
                "文档类型",
                "商品编码",
                "品类",
                "标题",
                "问题",
                "答案",
                "来源",
                "状态",
            ]
        )
        for document in documents:
            for chunk in document["chunks"]:
                writer.writerow(
                    [
                        document["scope"],
                        document["doc_type"],
                        document.get("product_code", ""),
                        document.get("category_slug", ""),
                        document["title"],
                        chunk.get("question", ""),
                        chunk["content"][:500],
                        document["source"],
                        "approved",
                    ]
                )
        for draft in drafts:
            writer.writerow(
                [
                    draft["scope"],
                    draft["doc_type"],
                    "",
                    draft["category_slug"],
                    draft["title"],
                    draft["question"],
                    draft["answer"],
                    draft["source"],
                    "pending",
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="覆盖已有种子文件")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="输出目录，测试可用临时目录",
    )
    args = parser.parse_args()

    output_file = args.output_dir / "knowledge.json"
    if output_file.exists() and not args.force:
        print(f"已存在 {output_file}，跳过生成（加 --force 重建）")
        return

    categories = load_json(CATEGORY_FILE)["categories"]
    products = load_json(PRODUCT_FILE)["products"]
    documents, drafts = build_documents(categories, products)
    validate(documents, drafts)
    write_outputs(args.output_dir, documents, drafts)
    chunk_total = sum(len(document["chunks"]) for document in documents)
    print(
        f"知识种子：{len(documents)} 文档 / {chunk_total} chunk；"
        f"品类 FAQ 草稿 {len(drafts)} 条（pending，不导入）"
    )
    print(f"输出目录：{args.output_dir}")


if __name__ == "__main__":
    main()
