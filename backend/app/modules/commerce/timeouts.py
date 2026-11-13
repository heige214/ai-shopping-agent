from __future__ import annotations

import asyncio
import logging

from app.db.session import AsyncSessionLocal
from app.modules.commerce import order_service

logger = logging.getLogger(__name__)


async def process_expired_orders() -> int:
    """扫描并取消过期待支付订单；异常只记录，不中断定时任务。"""
    async with AsyncSessionLocal() as db:
        try:
            return await order_service.expire_orders(db)
        except Exception:
            await db.rollback()
            logger.exception("扫描超时订单失败")
            return 0


async def order_timeout_loop(interval_seconds: int = 60) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        await process_expired_orders()
