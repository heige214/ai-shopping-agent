"""生成四个品类各 75 条的商品清单，供 image-batch 批量生图。

用法：
    python make_catalog.py

输出：
    data/服装.csv  data/鞋靴.csv  data/箱包.csv  data/配饰.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

import prompts

DATA_DIR = Path(__file__).resolve().parent / "data"
COLUMNS = [
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

# 每个属性都按条数轮转，同一子品类内颜色/材质/版型/风格/性别各不相同；
# 特征每次取 3 个不重复项，保证同子品类内不会千篇一律。
CATALOG = [
    {
        "category": "服装",
        "prefix": "C",
        "colors": [
            ("黑色", "#111111"),
            ("白色", "#F5F5F5"),
            ("米白", "#EFE8DA"),
            ("浅灰", "#C8C8C8"),
            ("深灰", "#555555"),
            ("藏青", "#1F2A44"),
            ("蓝色", "#2F5FAF"),
            ("浅蓝", "#A8C4E0"),
            ("卡其", "#C3B091"),
            ("棕色", "#6B4A2F"),
            ("绿色", "#3E6B4F"),
            ("酒红", "#6E2639"),
            ("驼色", "#B08D62"),
            ("粉色", "#E8B4B8"),
            ("黄色", "#D9A441"),
        ],
        "subcategories": [
            (
                "衬衫",
                10,
                dict(
                    materials=["纯棉", "亚麻", "棉麻", "真丝", "牛津纺"],
                    fits=["常规", "宽松", "修身"],
                    thicknesses=["薄款", "常规"],
                    styles=["休闲", "通勤", "基础", "复古"],
                    genders=["男", "女", "中性"],
                    features=["翻领", "单排扣", "左胸口袋", "落肩", "弧形下摆", "后背褶裥"],
                ),
            ),
            (
                "T恤",
                10,
                dict(
                    materials=["纯棉", "莫代尔", "聚酯纤维", "棉混纺"],
                    fits=["常规", "宽松", "修身"],
                    thicknesses=["薄款", "常规"],
                    styles=["基础", "休闲", "运动", "复古"],
                    genders=["男", "女", "中性"],
                    features=["圆领", "短袖", "纯色", "落肩", "下摆开衩", "侧缝细节"],
                ),
            ),
            (
                "裤装",
                12,
                dict(
                    materials=["纯棉", "牛仔", "棉麻", "聚酯纤维"],
                    fits=["直筒", "修身", "宽松", "锥形"],
                    thicknesses=["薄款", "常规", "加厚"],
                    styles=["休闲", "通勤", "运动", "基础"],
                    genders=["男", "女", "中性"],
                    features=["高腰", "斜插袋", "拉链门襟", "九分", "翻边裤脚", "后口袋"],
                ),
            ),
            (
                "连衣裙",
                8,
                dict(
                    materials=["真丝", "雪纺", "棉麻", "聚酯纤维"],
                    fits=["常规", "宽松", "修身"],
                    thicknesses=["薄款", "常规"],
                    styles=["通勤", "休闲", "复古", "度假"],
                    genders=["女"],
                    features=["V领", "收腰", "中长款", "A字摆", "系带", "隐形拉链"],
                ),
            ),
            (
                "外套",
                10,
                dict(
                    materials=["羊毛", "涤纶", "棉", "锦纶"],
                    fits=["常规", "宽松", "修身"],
                    thicknesses=["常规", "加厚"],
                    styles=["通勤", "休闲", "复古", "户外"],
                    genders=["男", "女", "中性"],
                    features=["翻领", "双排扣", "中长款", "侧口袋", "后背开衩", "可拆卸帽"],
                ),
            ),
            (
                "针织衫",
                8,
                dict(
                    materials=["羊毛", "羊绒混纺", "棉", "腈纶"],
                    fits=["常规", "宽松", "修身"],
                    thicknesses=["薄款", "常规", "加厚"],
                    styles=["通勤", "休闲", "基础", "复古"],
                    genders=["男", "女", "中性"],
                    features=["圆领", "罗纹下摆", "长袖", "麻花纹理", "撞色条纹", "下摆开衩"],
                ),
            ),
            (
                "卫衣",
                6,
                dict(
                    materials=["纯棉", "棉混纺", "抓绒"],
                    fits=["常规", "宽松"],
                    thicknesses=["常规", "加厚"],
                    styles=["休闲", "运动", "基础"],
                    genders=["男", "女", "中性"],
                    features=["连帽", "抽绳", "袋鼠口袋", "落肩", "加绒", "罗纹袖口"],
                ),
            ),
            (
                "半身裙",
                5,
                dict(
                    materials=["纯棉", "牛仔", "聚酯纤维", "羊毛"],
                    fits=["A字", "直筒", "包臀"],
                    thicknesses=["薄款", "常规", "加厚"],
                    styles=["通勤", "休闲", "复古"],
                    genders=["女"],
                    features=["高腰", "A字摆", "中长款", "侧拉链", "开衩", "内衬"],
                ),
            ),
            (
                "西装",
                3,
                dict(
                    materials=["羊毛", "涤纶", "棉麻"],
                    fits=["修身", "常规", "宽松"],
                    thicknesses=["常规"],
                    styles=["通勤", "正式"],
                    genders=["男", "女"],
                    features=["平驳领", "单排扣", "双口袋", "后开衩", "内衬", "修身剪裁"],
                ),
            ),
            (
                "风衣",
                3,
                dict(
                    materials=["棉", "涤纶", "锦纶"],
                    fits=["常规", "宽松"],
                    thicknesses=["薄款", "常规"],
                    styles=["通勤", "休闲", "复古"],
                    genders=["男", "女", "中性"],
                    features=["翻领", "双排扣", "腰带", "中长款", "肩章", "斜插袋"],
                ),
            ),
        ],
    },
    {
        "category": "鞋靴",
        "prefix": "S",
        "colors": [
            ("黑色", "#111111"),
            ("白色", "#F5F5F5"),
            ("米白", "#EFE8DA"),
            ("灰色", "#8A8A8A"),
            ("藏青", "#1F2A44"),
            ("棕色", "#6B4A2F"),
            ("卡其", "#C3B091"),
            ("绿色", "#4F5B3A"),
            ("酒红", "#6E2639"),
            ("粉色", "#E8B4B8"),
        ],
        "subcategories": [
            (
                "运动鞋",
                15,
                dict(
                    materials=["网布+橡胶", "飞织+EVA", "皮革+橡胶", "网布+EVA"],
                    styles=["运动", "休闲", "跑步"],
                    genders=["男", "女", "中性"],
                    features=["低帮", "系带", "厚底", "透气网面", "防滑大底", "缓震中底"],
                ),
            ),
            (
                "休闲鞋",
                10,
                dict(
                    materials=["皮革+橡胶", "帆布+橡胶", "绒面+橡胶"],
                    styles=["休闲", "通勤", "复古"],
                    genders=["男", "女", "中性"],
                    features=["圆头", "系带", "平底", "软底", "撞色鞋带", "橡胶大底"],
                ),
            ),
            (
                "皮鞋",
                10,
                dict(
                    materials=["皮革", "漆皮", "绒面"],
                    styles=["通勤", "正式"],
                    genders=["男", "女"],
                    features=["圆头", "系带", "皮革鞋面", "沿条缝线", "橡胶鞋底"],
                ),
            ),
            (
                "靴子",
                10,
                dict(
                    materials=["皮革", "绒面", "漆皮"],
                    styles=["休闲", "通勤", "复古"],
                    genders=["女", "中性", "男"],
                    features=["短筒", "松紧侧片", "皮革鞋面", "粗跟", "缝线细节"],
                ),
            ),
            (
                "帆布鞋",
                10,
                dict(
                    materials=["帆布+橡胶"],
                    styles=["休闲", "运动", "复古"],
                    genders=["男", "女", "中性"],
                    features=["低帮", "系带", "硫化底", "撞色鞋带", "帆布鞋面"],
                ),
            ),
            (
                "凉鞋",
                8,
                dict(
                    materials=["皮革+橡胶", "EVA", "织物"],
                    styles=["休闲", "度假"],
                    genders=["女", "中性", "男"],
                    features=["一字带", "搭扣", "露趾", "轻便鞋底", "软垫"],
                ),
            ),
            (
                "拖鞋",
                6,
                dict(
                    materials=["EVA", "棉", "皮革"],
                    styles=["休闲", "居家"],
                    genders=["男", "女", "中性"],
                    features=["包头", "防滑", "轻便", "软底", "EVA鞋身"],
                ),
            ),
            (
                "高跟鞋",
                6,
                dict(
                    materials=["皮革", "漆皮", "绒面"],
                    styles=["通勤", "正式"],
                    genders=["女"],
                    features=["尖头", "浅口", "细跟", "皮革鞋面", "软垫"],
                ),
            ),
        ],
    },
    {
        "category": "箱包",
        "prefix": "B",
        "colors": [
            ("黑色", "#111111"),
            ("棕色", "#6B4A2F"),
            ("卡其", "#C3B091"),
            ("灰色", "#8A8A8A"),
            ("藏青", "#1F2A44"),
            ("米白", "#EFE8DA"),
            ("酒红", "#6E2639"),
            ("绿色", "#4F5B3A"),
            ("驼色", "#B08D62"),
        ],
        "subcategories": [
            (
                "双肩包",
                15,
                dict(
                    materials=["帆布", "尼龙", "聚酯纤维"],
                    styles=["休闲", "通勤", "旅行"],
                    genders=["中性", "男", "女"],
                    features=["大容量", "多隔层", "可调节肩带", "拉链主袋", "电脑夹层", "防泼水"],
                ),
            ),
            (
                "手提包",
                12,
                dict(
                    materials=["皮革", "PU", "帆布"],
                    styles=["通勤", "休闲", "正式"],
                    genders=["女", "中性"],
                    features=["手提", "拉链", "金属五金", "定型包身", "可拆卸肩带"],
                ),
            ),
            (
                "单肩包",
                12,
                dict(
                    materials=["皮革", "PU", "尼龙"],
                    styles=["通勤", "休闲", "复古"],
                    genders=["女", "中性"],
                    features=["单肩", "磁扣", "可调节肩带", "轻量", "多隔层"],
                ),
            ),
            (
                "斜挎包",
                10,
                dict(
                    materials=["皮革", "PU", "帆布"],
                    styles=["休闲", "通勤", "旅行"],
                    genders=["中性", "女", "男"],
                    features=["斜挎", "拉链", "小号", "可调节肩带", "前置口袋"],
                ),
            ),
            (
                "钱包",
                8,
                dict(
                    materials=["皮革", "PU"],
                    styles=["通勤", "基础"],
                    genders=["中性", "男", "女"],
                    features=["对折", "卡位", "RFID", "零钱袋", "轻薄"],
                ),
            ),
            (
                "行李箱",
                8,
                dict(
                    materials=["聚碳酸酯", "ABS", "铝框"],
                    styles=["旅行", "商务"],
                    genders=["中性"],
                    features=["20寸", "万向轮", "TSA锁", "静音轮", "耐磨箱面"],
                ),
            ),
            (
                "托特包",
                6,
                dict(
                    materials=["帆布", "皮革", "尼龙"],
                    styles=["通勤", "休闲", "购物"],
                    genders=["女", "中性"],
                    features=["大容量", "开口", "肩带", "内袋", "轻量"],
                ),
            ),
            (
                "腰包",
                4,
                dict(
                    materials=["尼龙", "皮革", "聚酯纤维"],
                    styles=["运动", "休闲", "旅行"],
                    genders=["中性", "男"],
                    features=["腰包", "搭扣", "轻量", "多隔层", "防泼水"],
                ),
            ),
        ],
    },
    {
        "category": "配饰",
        "prefix": "A",
        "colors": [
            ("黑色", "#111111"),
            ("白色", "#F5F5F5"),
            ("米白", "#EFE8DA"),
            ("灰色", "#8A8A8A"),
            ("棕色", "#6B4A2F"),
            ("卡其", "#C3B091"),
            ("红色", "#B33A3A"),
            ("酒红", "#6E2639"),
            ("藏青", "#1F2A44"),
            ("绿色", "#4F5B3A"),
        ],
        "subcategories": [
            (
                "帽子",
                15,
                dict(
                    materials=["纯棉", "羊毛", "涤纶", "草编"],
                    styles=["休闲", "运动", "度假"],
                    genders=["中性", "男", "女"],
                    features=["可调节后扣", "弯檐", "透气孔", "帽檐缝线", "刺绣细节"],
                ),
            ),
            (
                "围巾",
                12,
                dict(
                    materials=["羊毛", "羊绒混纺", "棉", "真丝"],
                    styles=["休闲", "通勤", "复古"],
                    genders=["女", "中性", "男"],
                    features=["长款", "流苏", "格纹", "加厚", "柔软手感"],
                ),
            ),
            (
                "腰带",
                10,
                dict(
                    materials=["皮革", "PU", "帆布"],
                    styles=["通勤", "休闲", "正式"],
                    genders=["中性", "男", "女"],
                    features=["针扣", "可调节", "宽3.5cm", "打孔", "皮革边缘油边"],
                ),
            ),
            (
                "袜子",
                10,
                dict(
                    materials=["纯棉", "棉混纺", "羊毛"],
                    styles=["休闲", "运动", "通勤"],
                    genders=["中性", "男", "女"],
                    features=["中筒", "纯色", "罗纹袜口", "加厚", "足弓支撑"],
                ),
            ),
            (
                "手套",
                8,
                dict(
                    materials=["皮革", "羊毛", "针织", "绒面"],
                    styles=["通勤", "休闲", "户外"],
                    genders=["中性", "男", "女"],
                    features=["分指", "触屏", "加绒", "防风", "腕口收口"],
                ),
            ),
            (
                "墨镜",
                8,
                dict(
                    materials=["板材", "金属", "TR90"],
                    styles=["休闲", "度假", "复古"],
                    genders=["中性", "男", "女"],
                    features=["偏光", "UV400", "轻量镜架", "防滑鼻托", "全框"],
                ),
            ),
            (
                "项链",
                6,
                dict(
                    materials=["925银", "合金", "钛钢"],
                    styles=["通勤", "休闲", "复古"],
                    genders=["女", "中性"],
                    features=["锁骨链", "吊坠", "细链", "可调节", "简约"],
                ),
            ),
            (
                "手表",
                6,
                dict(
                    materials=["不锈钢", "皮革", "硅胶"],
                    styles=["通勤", "运动", "正式"],
                    genders=["中性", "男", "女"],
                    features=["石英机芯", "圆形表盘", "30米防水", "夜光指针", "简约刻度"],
                ),
            ),
        ],
    },
]


def pick_features(pool: list[str], start: int, count: int = 3) -> str:
    """从特征池里按起点取 count 个不重复项。"""
    picked: list[str] = []
    for offset in range(len(pool)):
        item = pool[(start + offset) % len(pool)]
        if item not in picked:
            picked.append(item)
        if len(picked) == count:
            break
    return "、".join(picked)


def build_rows(category: dict) -> list[dict]:
    rows: list[dict] = []
    colors = category["colors"]
    seq = 0

    for sub_index, (subcategory, count, spec) in enumerate(category["subcategories"]):
        offset = sub_index * 3
        for i in range(count):
            seq += 1
            fits = spec.get("fits") or ["标准"]
            thicknesses = spec.get("thicknesses") or ["常规"]
            color, color_hex = colors[(i + offset) % len(colors)]
            rows.append(
                {
                    "id": f"{category['prefix']}{seq:03d}",
                    "category": category["category"],
                    "subcategory": subcategory,
                    "color": color,
                    "color_hex": color_hex,
                    "material": spec["materials"][(i + offset) % len(spec["materials"])],
                    "fit": fits[(i + offset) % len(fits)],
                    "thickness": thicknesses[(i + offset) % len(thicknesses)],
                    "style": spec["styles"][(i + offset) % len(spec["styles"])],
                    "gender": spec["genders"][(i + offset) % len(spec["genders"])],
                    "key_feature": pick_features(spec["features"], i + offset),
                }
            )
    return rows


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for category in CATALOG:
        rows = build_rows(category)
        errors = prompts.validate_rows(rows)
        assert not errors, errors
        assert len(rows) == 75, f"{category['category']}: {len(rows)}"
        assert len({row['id'] for row in rows}) == 75

        path = DATA_DIR / f"{category['category']}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

        total += len(rows)
        print(f"{path.name}: {len(rows)} 条（{rows[0]['id']} ~ {rows[-1]['id']}）")

    print(f"合计：{total} 条")


if __name__ == "__main__":
    main()
