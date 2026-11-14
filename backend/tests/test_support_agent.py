from app.modules.support.agent import citation_types_for_question


def test_citation_types_follow_question_topic():
    assert citation_types_for_question("这件衬衫是什么材质？") == {
        "detail",
        "faq",
    }
    assert citation_types_for_question("这个小孩子能带吗") == {
        "detail",
        "faq",
        "size",
    }
    assert citation_types_for_question("平台的退货政策是什么？") == {
        "policy",
        "faq",
    }
    assert citation_types_for_question("这件商品怎么洗护？") == {
        "care",
        "detail",
        "faq",
    }
