import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

_CST = ZoneInfo("Asia/Shanghai")


class DailyCostBudget:
    __slots__ = ("_consumed_fen", "_date", "_limit_fen", "_lock")

    def __init__(self, daily_limit_yuan: float) -> None:
        self._limit_fen = round(daily_limit_yuan * 100)
        self._consumed_fen = 0
        self._date = datetime.now(_CST).date()
        self._lock = asyncio.Lock()

    async def consume(self, cost_fen: int) -> bool:
        async with self._lock:
            self._reset_if_new_day()
            if self._consumed_fen + cost_fen > self._limit_fen:
                return False
            self._consumed_fen += cost_fen
            return True

    async def settle(self, delta_fen: int) -> None:
        async with self._lock:
            self._reset_if_new_day()
            self._consumed_fen = max(0, self._consumed_fen + delta_fen)

    async def refund(self, cost_fen: int) -> None:
        async with self._lock:
            self._reset_if_new_day()
            self._consumed_fen = max(0, self._consumed_fen - cost_fen)

    @property
    def consumed_fen(self) -> int:
        return self._consumed_fen

    def _reset_if_new_day(self) -> None:
        today = datetime.now(_CST).date()
        if self._date != today:
            self._date = today
            self._consumed_fen = 0
