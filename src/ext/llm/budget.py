import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from pymongo.errors import PyMongoError

from src.utils.log import logger_wrapper
from src.utils.persistence.mongo import Collection, Mongo

logger = logger_wrapper(__name__)
_CST = ZoneInfo("Asia/Shanghai")

_budget_collection: Collection = Mongo.collection("llm_budget")


class DailyCostBudget:
    """每日 LLM 预算，按日期持久化到 Mongo（重启不丢、跨天自动归零）。

    Mongo 文档：{_id: "YYYY-MM-DD", consumed_fen: int}
    Mongo 故障时 fail-closed：consume 拒绝、settle/refund/status 仅记日志，
    绝不向调用方抛异常（预算读取失败不阻塞回复管线）。
    """

    __slots__ = ("_consumed_fen", "_date", "_limit_fen", "_loaded", "_lock")

    def __init__(self, daily_limit_yuan: float) -> None:
        self._limit_fen = round(daily_limit_yuan * 100)
        self._consumed_fen = 0
        self._date = datetime.now(_CST).date()
        self._lock = asyncio.Lock()
        self._loaded = False

    async def ensure_loaded(self) -> None:
        async with self._lock:
            await self._ensure_loaded()

    async def _ensure_loaded(self) -> bool:
        today = datetime.now(_CST).date()
        if self._date != today:
            self._date = today
            self._consumed_fen = 0
            self._loaded = False
        if not self._loaded:
            try:
                doc = await _budget_collection.find_one({"_id": today.isoformat()})
            except PyMongoError as e:
                logger.warning(
                    "Budget load failed, treating as budget unavailable", exception=e
                )
                return False
            if doc is not None:
                self._consumed_fen = doc["consumed_fen"]
            self._loaded = True
        return True

    async def _persist(self) -> None:
        try:
            await _budget_collection.update_one(
                {"_id": self._date.isoformat()},
                {"$set": {"consumed_fen": self._consumed_fen}},
                upsert=True,
            )
        except PyMongoError as e:
            logger.warning("Budget persist failed", exception=e)

    async def consume(self, cost_fen: int) -> bool:
        async with self._lock:
            if not await self._ensure_loaded():
                return False
            if self._consumed_fen + cost_fen > self._limit_fen:
                return False
            self._consumed_fen += cost_fen
            await self._persist()
            return True

    async def settle(self, delta_fen: int) -> None:
        async with self._lock:
            await self._ensure_loaded()
            self._consumed_fen = max(0, self._consumed_fen + delta_fen)
            await self._persist()

    async def refund(self, cost_fen: int) -> None:
        async with self._lock:
            await self._ensure_loaded()
            self._consumed_fen = max(0, self._consumed_fen - cost_fen)
            await self._persist()

    @property
    def consumed_fen(self) -> int:
        return self._consumed_fen
