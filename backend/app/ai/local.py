from __future__ import annotations

import re
from collections.abc import AsyncIterator

from app.ai.base import AnswerabilityResult, IntentResult, SupportPlan
from app.ai.size_rules import (
    build_size_availability_answer,
    has_stock_word,
    parse_size_query,
    size_phrase,
)

COMPLAINT_WORDS = ("投诉", "差评", "太差", "骗人", "气死", "垃圾", "恶心")
ORDER_WORDS = ("订单", "物流", "快递", "运单", "到货", "签收", "什么时候到", "发货")
SIZE_WORDS = (
    "尺码",
    "码数",
    "选码",
    "码",
    "号",
    "穿多大",
    "身高",
    "体重",
    "脚长",
    "偏大",
    "偏小",
    "均码",
)
POLICY_WORDS = (
    "退换",
    "退货",
    "退款",
    "发票",
    "优惠券",
    "运费",
    "包邮",
    "支付",
    "售后",
    "政策",
)
PRODUCT_WORDS = (
    "材质",
    "面料",
    "成分",
    "起球",
    "缩水",
    "掉色",
    "洗",
    "护理",
    "厚薄",
    "版型",
    "透气",
    "适合",
    "颜色",
    "色差",
    "羊毛",
    "棉",
    "亚麻",
    "真丝",
    "牛仔",
    "库存",
    "现货",
    "有货",
)
SUITABILITY_WORDS = (
    "小孩子",
    "小孩",
    "儿童",
    "孩子",
    "宝宝",
    "年龄",
    "送礼",
    "送人",
    "长辈",
    "学生",
    "孕妇",
    "敏感肌",
)
CHILD_WORDS = ("小孩子", "小孩", "儿童", "孩子", "宝宝")
CHITCHAT_WORDS = ("你好", "您好", "在吗", "谢谢", "辛苦", "拜拜", "嗨", "hello", "hi")

FACT_TOPICS = {
    "价格": ("价格", "多少钱", "贵", "便宜", "售价"),
    "材质": ("材质", "面料", "成分", "什么料"),
    "颜色": ("颜色", "色差", "配色"),
    "尺码": ("尺码", "码数", "身高", "体重", "脚长", "偏大", "偏小", "选码"),
    "品牌": ("品牌", "牌子"),
    "库存": ("库存", "现货", "有货", "缺货"),
}


def detect_intent(question: str) -> str:
    """无 key 时的规则意图；顺序保证投诉/订单优先于商品问题。"""
    text = question.lower()
    if any(word in text for word in COMPLAINT_WORDS):
        return "complaint"
    if any(word in text for word in ORDER_WORDS):
        return "order_qa"
    if any(word in text for word in SIZE_WORDS) or parse_size_query(
        question
    ).mentions_size:
        return "size_qa"
    if any(word in text for word in POLICY_WORDS):
        return "policy_qa"
    if any(word in text for word in SUITABILITY_WORDS):
        return "product_qa"
    if any(word in text for word in PRODUCT_WORDS):
        return "product_qa"
    if any(word in text for word in CHITCHAT_WORDS):
        return "chitchat"
    return "unknown"


def _extract_topic(question: str) -> str | None:
    for word in (
        *COMPLAINT_WORDS,
        *ORDER_WORDS,
        *SIZE_WORDS,
        *POLICY_WORDS,
        *SUITABILITY_WORDS,
        *PRODUCT_WORDS,
    ):
        if word in question:
            return word
    return None


def _context_lines(chunks_text: str) -> list[str]:
    lines: list[str] = []
    for raw in chunks_text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("[", "【", "（", "(")):
            continue
        lines.append(line)
    return lines


def _fact_map(facts_text: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for raw in facts_text.splitlines():
        line = raw.strip()
        if not line or "：" not in line:
            continue
        key, value = line.split("：", 1)
        facts[key.strip()] = value.strip()
    return facts


def _stock_map(facts_text: str) -> dict[str, int]:
    stock: dict[str, int] = {}
    for part in re.split(r"[；;]", _fact_map(facts_text).get("库存", "")):
        match = re.match(r"\s*(.+?)\s+(\d+)\s*件", part)
        if match:
            stock[match.group(1).strip()] = int(match.group(2))
    return stock


def _known_sizes(facts_text: str) -> list[str]:
    stock = _stock_map(facts_text)
    if stock:
        return list(stock)
    raw = _fact_map(facts_text).get("可选尺码", "")
    return [item.strip() for item in re.split(r"[、,，/]", raw) if item.strip()]


def _availability_answer(question: str, facts_text: str) -> str | None:
    stock = _stock_map(facts_text)
    sizes = list(stock) or _known_sizes(facts_text)
    query = parse_size_query(question, sizes)
    if not query.requested_size and not has_stock_word(question):
        return None
    return build_size_availability_answer(stock, sizes, query)


def _size_chart(facts_text: str) -> dict[str, dict[str, tuple[float, float]]]:
    chart: dict[str, dict[str, tuple[float, float]]] = {}
    raw = _fact_map(facts_text).get("尺码表", "")
    for part in raw.split("；"):
        match = re.match(r"\s*([^：:]+)[：:](.+)", part)
        if not match:
            continue
        size = match.group(1).strip()
        fields: dict[str, tuple[float, float]] = {}
        for key, label in (
            ("height", "身高"),
            ("weight", "体重"),
            ("chest", "胸围"),
            ("waist", "腰围"),
            ("foot", "脚长"),
        ):
            found = re.search(rf"{label}\s*(\d+)-(\d+)", match.group(2))
            if found:
                fields[key] = (float(found.group(1)), float(found.group(2)))
        if fields:
            chart[size] = fields
    return chart


def _number_after(question: str, label: str) -> float | None:
    match = re.search(rf"{label}\s*(\d{{2,3}}(?:\.\d+)?)", question)
    return float(match.group(1)) if match else None


def _range_detail(fields: dict[str, tuple[float, float]]) -> str:
    parts: list[str] = []
    if "height" in fields:
        low, high = fields["height"]
        parts.append(f"身高 {int(low)}-{int(high)}cm")
    if "weight" in fields:
        low, high = fields["weight"]
        parts.append(f"体重 {int(low)}-{int(high)}kg")
    return "、".join(parts)


def _size_recommendation_answer(question: str, facts_text: str) -> str:
    chart = _size_chart(facts_text)
    sizes = list(chart) or _known_sizes(facts_text)
    if not chart:
        if sizes:
            return f"这款可选 {size_phrase(sizes)}；告诉我身高体重，我可以帮你参考。"
        return "这款的尺码信息暂时不全，建议转人工确认。"

    has_foot = any("foot" in fields for fields in chart.values())
    foot = _number_after(question, "脚长")
    if foot is not None and has_foot:
        if foot < 100:
            foot *= 10
        for size, fields in chart.items():
            foot_range = fields.get("foot")
            if foot_range and foot_range[0] <= foot <= foot_range[1]:
                return (
                    f"建议选 {size} 码，适合脚长 "
                    f"{int(foot_range[0])}-{int(foot_range[1])}mm。"
                )
        return "这个脚长没有完全对应的尺码，建议转人工客服确认一下。"

    if has_foot:
        return (
            f"鞋款建议按脚长选码，目前可选 {size_phrase(sizes)}；"
            "方便告诉我脚长吗？"
        )

    height = _number_after(question, "身高")
    weight = _number_after(question, "体重")
    if height is not None or weight is not None:
        best_size: str | None = None
        best_score: float | None = None
        for size, fields in chart.items():
            score = 0.0
            usable = True
            for key, value in (("height", height), ("weight", weight)):
                if value is None:
                    continue
                value_range = fields.get(key)
                if not value_range:
                    usable = False
                    break
                if not value_range[0] <= value <= value_range[1]:
                    score += min(
                        abs(value - value_range[0]),
                        abs(value - value_range[1]),
                    )
            if usable and (best_score is None or score < best_score):
                best_size, best_score = size, score
        if best_size:
            detail = _range_detail(chart[best_size])
            suffix = f"（适合{detail}）" if detail else ""
            return f"建议选 {best_size} 码{suffix}。"

    return f"这款可选 {size_phrase(sizes)}；告诉我身高体重，我可以帮你参考。"


def _sentences(chunks_text: str) -> list[str]:
    sentences: list[str] = []
    for line in _context_lines(chunks_text):
        sentences.extend(
            sentence.strip()
            for sentence in re.split(r"(?<=[。！？!?；;])", line)
            if sentence.strip()
        )
    return sentences


def _best_sentence(chunks_text: str, keywords: tuple[str, ...]) -> str:
    best = ""
    best_score = -1
    for sentence in _sentences(chunks_text):
        score = sum(1 for keyword in keywords if keyword in sentence)
        if score > best_score:
            best = sentence
            best_score = score
    return best


def _clean_sentence(sentence: str) -> str:
    text = sentence.strip()
    for prefix in ("洗护提示：", "洗护建议：", "护理建议：", "洗涤说明："):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text


def _trim(text: str, limit: int = 100) -> str:
    text = _clean_sentence(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip("，、；;：:") + "。"


def _care_answer(question: str, chunks_text: str) -> str | None:
    sentence = _best_sentence(
        chunks_text, ("洗护", "清洗", "护理", "洗涤", "清洁", "机洗", "手洗")
    )
    return _trim(sentence) if sentence else None


def _policy_answer(question: str, chunks_text: str) -> str:
    keywords = tuple(
        word
        for word in (
            "退货",
            "退款",
            "退换",
            "发票",
            "优惠券",
            "运费",
            "包邮",
            "发货",
            "物流",
            "支付",
            "售后",
        )
        if word in question
    ) or ("退货", "退款", "发货", "售后")
    sentence = _best_sentence(chunks_text, keywords)
    return _trim(sentence) if sentence else "平台政策方面，建议转人工客服确认。"


def _product_answer(question: str, facts_text: str, chunks_text: str) -> str:
    facts = _fact_map(facts_text)
    if any(word in question for word in CHILD_WORDS):
        audience = facts.get("适用人群")
        if audience:
            return (
                f"商品资料标注适用人群为{audience}，没有标注儿童年龄信息，"
                "建议转人工客服进一步确认。"
            )
        return "知识库暂未检索到儿童适用信息，建议转人工客服进一步确认。"
    if any(word in question for word in ("材质", "面料", "成分", "什么料")):
        if facts.get("材质"):
            return f"这件商品的材质是{facts['材质']}。"
    for words, key, template in (
        (("颜色", "色差"), "颜色", "这款的颜色是{value}。"),
        (("厚薄", "厚"), "厚薄", "这款是{value}。"),
        (("版型", "修身", "宽松"), "版型", "这款版型是{value}。"),
        (("风格",), "风格", "这款偏{value}风格。"),
    ):
        if any(word in question for word in words) and facts.get(key):
            return template.format(value=facts[key])

    if any(word in question for word in ("洗", "护理", "清洁", "保养")):
        answer = _care_answer(question, chunks_text)
        if answer:
            return answer

    sentence = _best_sentence(
        chunks_text,
        tuple(
            word
            for word in (
                "起球",
                "缩水",
                "掉色",
                "透气",
                "厚薄",
                "版型",
                "适合",
                "洗护",
            )
            if word in question
        ),
    )
    if sentence:
        return _trim(sentence)
    sentences = _sentences(chunks_text)
    if sentences:
        return _trim(sentences[0])
    return "这件商品的资料暂时不完整，建议转人工客服确认。"


def build_local_answer(
    question: str,
    facts_text: str,
    chunks_text: str,
    partial: bool,
) -> str:
    """无 key 时的确定性回答：先直接回应，再给必要信息，避免整段复述资料。"""
    intent = detect_intent(question)
    size_answer = _availability_answer(question, facts_text)
    if size_answer:
        answer = size_answer
    elif intent == "size_qa":
        answer = _size_recommendation_answer(question, facts_text)
    elif intent == "policy_qa":
        answer = _policy_answer(question, chunks_text)
    else:
        answer = _product_answer(question, facts_text, chunks_text)
    if partial:
        answer += "其余部分建议转人工客服确认。"
    return answer


class LocalSupportLLM:
    """无 DashScope key 时的确定性实现：规则意图 + 片段拼接回答。"""

    async def route_intent(self, question: str, product_title: str) -> IntentResult:
        intent = detect_intent(question)
        topic = _extract_topic(question)
        return IntentResult(intent=intent, entities={"question_topic": topic})

    async def plan_support(
        self,
        question: str,
        product_title: str,
    ) -> SupportPlan:
        intent = detect_intent(question)
        if intent == "order_qa":
            return SupportPlan(action="handoff", handoff_kind="order")
        if intent == "complaint":
            return SupportPlan(action="handoff", handoff_kind="complaint")
        if intent == "chitchat":
            return SupportPlan(action="chitchat")
        if intent == "unknown":
            return SupportPlan(action="clarify")

        tools = ["product_facts", "search_knowledge"]
        if intent == "policy_qa":
            tools = ["search_knowledge"]
        size = parse_size_query(question).requested_size
        if intent == "size_qa" and size:
            tools.append("size_stock")
        search_query = question
        if any(word in question for word in SUITABILITY_WORDS):
            search_query = f"{question} 适用人群 儿童 年龄 是否适合"
        return SupportPlan(
            action="rag",
            tools=tools,
            search_query=search_query,
            size=size,
        )

    async def judge_answerable(
        self,
        question: str,
        facts_text: str,
        chunks_text: str,
        max_similarity: float,
    ) -> AnswerabilityResult:
        if _context_lines(chunks_text):
            confidence = max(0.8, min(0.95, max_similarity or 0.8))
            return AnswerabilityResult(
                can_answer=True, confidence=confidence, partial=False
            )
        for key, words in FACT_TOPICS.items():
            if key in facts_text and any(word in question for word in words):
                return AnswerabilityResult(
                    can_answer=True, confidence=0.7, partial=False
                )
        return AnswerabilityResult(
            can_answer=False, confidence=0.2, partial=False, missing="knowledge"
        )

    async def stream_answer(
        self,
        question: str,
        facts_text: str,
        chunks_text: str,
        partial: bool,
    ) -> AsyncIterator[str]:
        answer = build_local_answer(question, facts_text, chunks_text, partial)
        for index in range(0, len(answer), 8):
            yield answer[index : index + 8]


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
