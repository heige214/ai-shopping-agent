from app.ai.local import build_local_answer

FACTS = """商品：粉色棉EVA鞋身拖鞋
价格：¥129.00
材质：棉
颜色：粉色
可选尺码：35、36、37、38、39
库存：35 12 件；36 46 件；37 2 件；38 6 件；39 45 件
尺码表：35：脚长220-225mm；36：脚长225-230mm；37：脚长230-235mm；38：脚长235-240mm；39：脚长240-245mm"""

CLOTHING_FACTS = """商品：测试衬衫
可选尺码：S、M、L
尺码表：S：身高155-165cm，体重45-55kg；M：身高165-172cm，体重55-65kg；L：身高170-178cm，体重65-75kg"""

CARE_CHUNKS = (
    "[1] 洗护指南\n"
    "洗护提示：棉质建议 30℃ 以下冷水机洗，深浅色分开，反面晾晒，"
    "不要长时间浸泡，避免高温烘干导致缩水。"
)

POLICY_CHUNKS = (
    "[1] 平台规则｜退货退款\n"
    "退款原路退回，审核通过后 1~3 个工作日到账，具体到账时间以支付渠道为准。"
    "未发货订单可直接取消并退款；已发货订单需先申请退货，仓库验收后发起退款。"
)


def test_missing_size_is_polite_and_direct():
    answer = build_local_answer("有40尺码的吗", FACTS, "", False)

    assert answer.startswith("不好意思")
    assert "没有 40 码" in answer
    assert "35-39" in answer
    assert len(answer) < 60


def test_in_stock_size_answers_yes_warmly():
    answer = build_local_answer("有37码吗", FACTS, "", False)

    assert answer == "有的，37 码目前有货。"


def test_zero_stock_size_says_temporarily_unavailable():
    facts = FACTS.replace("库存：", "库存：40 0 件；")
    answer = build_local_answer("有40码吗", facts, "", False)

    assert "不好意思" in answer
    assert "40 码暂时缺货" in answer
    assert "35-39" in answer


def test_general_availability_is_one_short_sentence():
    answer = build_local_answer("有货吗", FACTS, "", False)

    assert answer == "有的，目前 35-39 码都有货。"


def test_letter_sizes_keep_natural_order():
    facts = (
        "商品：测试T恤\n可选尺码：S、M、L、XL\n"
        "库存：S 2 件；M 3 件；L 4 件；XL 5 件"
    )
    answer = build_local_answer("有XS尺码的吗", facts, "", False)

    assert "S、M、L、XL 码" in answer


def test_child_suitability_does_not_dump_product_detail():
    answer = build_local_answer(
        "这个小孩子能带吗",
        FACTS.replace("材质：棉", "材质：棉\n适用人群：女"),
        "",
        False,
    )

    assert "适用人群" in answer
    assert "儿童" in answer
    assert "转人工" in answer


def test_material_answer_does_not_dump_product_facts():
    answer = build_local_answer("这件是什么材质？", FACTS, "", False)

    assert answer == "这件商品的材质是棉。"


def test_care_answer_keeps_only_relevant_sentence():
    answer = build_local_answer("这件商品怎么洗护？", FACTS, CARE_CHUNKS, False)

    assert answer.startswith("棉质建议")
    assert "30℃" in answer
    assert "洗护提示" not in answer
    assert len(answer) < 80


def test_size_recommendation_picks_one_size():
    answer = build_local_answer(
        "我身高170体重65，应该选什么尺码？", CLOTHING_FACTS, "", False
    )

    assert answer.startswith("建议选 M 码")
    assert "165-172" in answer
    assert len(answer) < 60


def test_policy_answer_keeps_one_relevant_sentence():
    answer = build_local_answer("平台的退货政策是什么？", "", POLICY_CHUNKS, False)

    assert "退货" in answer or "退款" in answer
    assert len(answer) < 80
