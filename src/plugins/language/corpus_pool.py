import random
import re
from collections import OrderedDict
from typing import Callable

from src.utils.env import inject_env

from .corpus import Corpus, Entry, deserialize


def weighted_sample(entries: list[Entry], scorer: Callable[[Entry], float],
                    k: int) -> list[Entry]:
    """Sample k entries from entries with weights from scorer."""
    if len(entries) <= k:
        return entries

    weights = [scorer(entry) for entry in entries]
    if all(w == 0 for w in weights):
        weights = [1.0] * len(entries)
    return random.choices(entries, weights=weights, k=k)


@inject_env()
class CorpusPool:
    """Fetch corpus in batch for Ask random corpus entry."""

    CORPUS_CACHE_ENABLED: bool = True

    NUM_CORPUS_POOL: int = 16
    CORPUS_THRESH_LO: int = 32  # if lower, fetch more
    CORPUS_BATCH_SIZE: int = 128

    _pool: OrderedDict[tuple[int, int | tuple[int, int] | None, str],
                       list[Entry]] = OrderedDict()

    @classmethod
    async def fetch(
        cls,
        group_id: int,
        length: int | tuple[int, int] | None,
        startswith: str = "",
        count: int = 2,
    ) -> list[Entry]:
        if not cls.CORPUS_CACHE_ENABLED:
            return await cls._fetch_from_db(group_id, length, startswith,
                                            count)

        cache_key = (group_id, length, startswith)
        if len(cls._pool.get(cache_key, [])) < count + cls.CORPUS_THRESH_LO:
            # TODO: deduplicate of existing entries
            entries = await cls._fetch_from_db(group_id, length, startswith,
                                               count + cls.CORPUS_BATCH_SIZE)
            cls._pool.setdefault(cache_key, []).extend(entries)
            # evict if over size
            if len(cls._pool) > cls.NUM_CORPUS_POOL:
                cls._pool.popitem(last=False)  # remove the first (oldest)

        selected = weighted_sample(cls._pool[cache_key],
                                   lambda e: e.chinese_ratio, count)
        remaining = [e for e in cls._pool[cache_key] if e not in selected]
        cls._pool[cache_key] = remaining
        # result, cls._pool[cache_key] = (cls._pool[cache_key][:count],
        #                                 cls._pool[cache_key][count:])
        return selected

    @classmethod
    async def _fetch_from_db(
        cls,
        group_id: int,
        length: int | tuple[int, int] | None,
        startswith: str,
        count: int,
    ) -> list[Entry]:
        startswith = re.escape(startswith)
        cursor = await Corpus.find(
            group_id=group_id,
            length=length,
            sample=count,
            filter={"text": {
                "$regex": f"^{startswith}"
            }} if startswith else None)
        doc = await cursor.to_list()
        return [deserialize(d) for d in doc]
