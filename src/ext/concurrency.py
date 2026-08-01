import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager


class KeyedConcurrency:
    """按 key 分片的并发准入控制，非阻塞：拿不到槽位返回 False，调用方跳过。

    acquire() 内没有真正的挂起点（sem/global 有空闲时立即成功，已用
    locked() 预先检查），因此 check-then-act 是原子的——请勿在
    sem.acquire() 前插入 await，否则会引入竞态。
    """

    __slots__ = ("_acquired", "_global", "_keyed", "_max_keys", "_per_key")

    def __init__(
        self,
        per_key: int = 1,
        global_limit: int | None = None,
        max_keys: int = 4096,
    ) -> None:
        """per_key: 同一 key 最多并发数。global_limit: 全局最多并发数，None 不设限。

        max_keys: key 表上限，超过后惰性淘汰最久未用的空闲条目（防 key 无界增长）。
        """
        self._per_key = per_key
        self._global = (
            asyncio.Semaphore(global_limit) if global_limit is not None else None
        )
        self._keyed: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(per_key)
        )
        self._acquired: set[str] = set()
        self._max_keys = max_keys

    async def acquire(self, key: str) -> bool:
        sem = self._keyed[key]
        if sem.locked():
            return False
        if self._global is not None and self._global.locked():
            return False
        await sem.acquire()
        if self._global is not None:
            await self._global.acquire()
        self._acquired.add(key)
        # 清理必须在 key 创建之后：先清再访问会在"删一个建一个"间震荡
        self._evict_idle()
        return True

    def release(self, key: str) -> None:
        """释放 key 的槽位。未持有该 key 槽位时调用是安全的（no-op）。"""
        if key not in self._acquired:
            return
        self._acquired.discard(key)
        sem = self._keyed.get(key)
        if sem is not None:
            sem.release()
        if self._global is not None:
            self._global.release()

    @asynccontextmanager
    async def slot(self, key: str):
        acquired = await self.acquire(key)
        try:
            yield acquired
        finally:
            if acquired:
                self.release(key)

    def _evict_idle(self) -> None:
        """淘汰空闲 key：只在超出上限时扫描，删除未被持有的 semaphore。"""
        if len(self._keyed) <= self._max_keys:
            return
        idle = [
            k
            for k, sem in self._keyed.items()
            if k not in self._acquired and not sem.locked()
        ]
        excess = len(self._keyed) - self._max_keys
        for key in idle[:excess]:
            del self._keyed[key]
