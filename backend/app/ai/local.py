from __future__ import annotations

import re
from collections.abc import AsyncIterator

from app.ai.base import AnswerabilityResult, IntentResult

COMPLAINT_WORDS = ("投诉", "差评", "太差", "骗人", "气死", "垃圾", "恶心")
ORDER_WORDS = ("订单", "物流", "快递", "运单", "到货", "签收", "什么时候到", "发货")
SIZE_WORDS = (
    "尺码",
    "码数",
    "选码",
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
    if any(word in text for word in SIZE_WORDS):
        return "size_qa"
    if any(word in text for word in POLICY_WORDS):
        return "policy_qa"
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


def _facts_lines(facts_text: str) -> list[str]:
    return [line.strip() for line in facts_text.splitlines() if line.strip()]


def build_local_answer(
    question: str,
    facts_text: str,
    chunks_text: str,
    partial: bool,
) -> str:
    """从检索片段/商品事实拼接确定性回答，作为无 key 或测试降级。"""
    lines = _context_lines(chunks_text)
    if lines:
        body = "".join(lines)[:240].strip()
        answer = f"根据商品资料：{body}。"
    else:
        facts = _facts_lines(facts_text)[:3]
        body = "；".join(facts)[:200] if facts else "暂未找到对应商品资料"
        answer = f"根据商品信息：{body}。"
    if partial:
        answer += "其余部分建议转人工客服确认。"
    return answer


class LocalSupportLLM:
    """无 DashScope key 时的确定性实现：规则意图 + 片段拼接回答。"""

    async def route_intent(self, question: str, product_title: str) -> IntentResult:
        intent = detect_intent(question)
        topic = _extract_topic(question)
        return IntentResult(intent=intent, entities={"question_topic": topic})

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
