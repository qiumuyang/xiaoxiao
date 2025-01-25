import re
from collections import OrderedDict

from src.utils.env import inject_env

from .corpus import Corpus, Entry, deserialize


@inject_env()
class CorpusPool:
    """Fetch corpus in batch for Ask random corpus entry."""

    CORPUS_CACHE_ENABLED: bool = True

    NUM_CORPUS_POOL: int = 16
    CORPUS_THRESH_LO: int = 10  # if lower, fetch more
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
            if len(cls._pool) > cls.NUM_CORPUS_POOL:
                cls._pool.popitem(last=False)  # remove the first (oldest)

        result, cls._pool[cache_key] = (cls._pool[cache_key][:count],
                                        cls._pool[cache_key][count:])
        return result

    @classmethod
    async def _fetch_from_db(
        cls,
        group_id: int,
        length: int | tuple[int, int] | None,
        startswith: str,
        count: int,
    ) -> list[Entry]:
        startswith = re.escape(startswith)
        cursor = Corpus.find(group_id=group_id,
                             length=length,
                             sample=count,
                             filter={"text": {
                                 "$regex": f"^{startswith}"
                             }} if startswith else None)
        return [deserialize(doc) async for doc in cursor]
