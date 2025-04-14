from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property
from typing import Any, Iterable

import jieba.posseg as pseg
from nonebot import get_driver

from src.utils.env import inject_env
from src.utils.message.receive import MessageData as RMD
from src.utils.message.receive import ReceivedMessageTracker as RMT
from src.utils.message.send import MessageData as SMD
from src.utils.message.send import SentMessageTracker as SMT
from src.utils.persistence import Collection, Mongo

from .keywords import Keyword


@dataclass
class Entry:
    group_id: int
    created: datetime
    used: datetime
    text: str
    length: int
    keywords: set[str]

    @cached_property
    def posseg(self) -> list[tuple[str, str]]:
        return [(word, tag) for word, tag in pseg.cut(self.text)]

    def remove_prefix(self, prefix: str) -> str:
        return self.text.removeprefix(prefix)

    def startswith_pos(self, *tag: str) -> list[str]:
        if not self.posseg:
            return []
        return [t for t in tag if self.posseg[0][1].startswith(t)]

    def cut_pos(
        self,
        start: str,
        end: str | list[str],
        keepend: bool = False,
    ) -> Iterable[list[tuple[str, str]]]:
        ends = tuple(end) if isinstance(end, list) else (end, )
        for i, (_, start_tag) in enumerate(self.posseg):
            if start_tag.startswith(start):
                for j, (_, end_tag) in enumerate(self.posseg[i:], start=i):
                    if end_tag.startswith(ends):
                        yield self.posseg[i:j + int(keepend)]


@inject_env()
class Corpus:

    MAX_CORPUS_TEXT_LENGTH: int

    SHARED_GROUP_ID = 1

    KEY = "corpus"
    corpus: Collection[dict, Entry] = Mongo.collection(KEY)

    recently_sent: list[tuple[datetime, str]] = []
    TTL_SENTD = timedelta(minutes=15)

    FIRST_TIME_SAMPLE_INTERVAL = timedelta(minutes=15)
    USED_SAMPLE_INTERVAL = timedelta(hours=4)

    @classmethod
    async def init(cls) -> None:
        await cls.corpus.collection.create_index({"keywords": 1})

    @classmethod
    def maintain(cls) -> None:
        """Remove outdated entries."""
        expire = datetime.now() - cls.TTL_SENTD
        cls.recently_sent = [(time, text) for time, text in cls.recently_sent
                             if time > expire]

    @classmethod
    async def add(cls, entry: Entry) -> None:
        """Add a message to the corpus.

        1. Do not add duplicated messages.
        2. Do not add recently sent messages.
        """
        cls.maintain()
        if entry.text in [text for _, text in cls.recently_sent]:
            return
        if await cls.corpus.find_one({"text": entry.text}) is not None:
            await cls.corpus.update_one(
                filter={"text": entry.text},
                update={"$set": {
                    "created": entry.created
                }})
        else:
            await cls.corpus.insert_one(entry)

    @classmethod
    async def use(cls, entry: Entry) -> None:
        """Mark a message as used."""
        await cls.corpus.update_one(
            filter={
                "text": entry.text,
                "group_id": entry.group_id
            },
            update={"$set": {
                "used": datetime.now()
            }},
        )

    @classmethod
    def find(
        cls,
        group_id: int | list[int],
        length: int | tuple[int, int] | None = None,
        keywords: list[str] | None = None,
        filter: dict[str, Any] | None = None,
        sample: int | None = None,
        *,
        no_shared: bool = False,
    ):
        cls.maintain()
        now = datetime.now()
        filter = filter or {}
        recent_text = set(text for _, text in cls.recently_sent)
        not_recent_sent = {"text": {"$nin": list(recent_text)}}
        not_recent_added = {
            # case 1: not used, and created > FIRST_TIME_SAMPLE_INTERVAL
            # case 2: used, and used > USED_SAMPLE_INTERVAL
            "$or": [{
                "$and": [{
                    "created": {
                        "$eq": "used"
                    }
                }, {
                    "used": {
                        "$lt": now - cls.FIRST_TIME_SAMPLE_INTERVAL
                    }
                }]
            }, {
                "used": {
                    "$lt": now - cls.USED_SAMPLE_INTERVAL
                }
            }]
        }
        if no_shared:
            group_id = [group_id] if isinstance(group_id, int) else group_id
        else:
            group_id = [group_id, cls.SHARED_GROUP_ID] if isinstance(
                group_id, int) else group_id + [cls.SHARED_GROUP_ID]
        match_group_id = {"group_id": {"$in": group_id}}
        pipeline: list[dict[str, Any]] = [{
            "$match": m
        } for m in (match_group_id, not_recent_sent, not_recent_added)]
        if length is not None:
            match_length = {
                "length": length
            } if isinstance(length, int) else {
                "length": {
                    "$gte": length[0],
                    "$lte": length[1]
                }
            }
            pipeline.insert(0, {"$match": match_length})
        if keywords is not None:
            pipeline.append({"$match": {"keywords": {"$in": keywords}}})
        if filter:
            pipeline.append({"$match": filter})
        if sample is not None:
            pipeline.append({"$sample": {"size": sample}})
        return cls.corpus.aggregate(pipeline)

    @classmethod
    async def find_after(
        cls,
        group_id: int,
        keywords: list[str],
        after: timedelta,
        sample: int,
    ):
        """Find corpus entry after a given message."""
        matched = await cls.find(group_id,
                                 keywords=keywords,
                                 sample=sample,
                                 no_shared=True).to_list(length=sample)
        if not matched:
            return None
        periods = [(entry["created"], entry["created"] + after)
                   for entry in matched]
        return cls.find(
            group_id,
            filter={
                "$or": [{
                    "created": {
                        "$gte": start,
                        "$lt": end
                    }
                } for start, end in periods]
            },
        )


@Corpus.corpus.serialize()
def _(entry: Entry) -> dict:
    return {
        "group_id": entry.group_id,
        "created": entry.created,
        "used": entry.used,
        "text": entry.text,
        "length": entry.length,
        "keywords": list(entry.keywords),
    }


@Corpus.corpus.deserialize()
def deserialize(data: dict) -> Entry:
    return Entry(
        group_id=data["group_id"],
        created=data["created"],
        used=data["used"],
        text=data["text"],
        length=data["length"],
        keywords=set(data["keywords"]),
    )


@Corpus.corpus.filter()
def _(entry: Entry) -> dict:
    return {
        "text": entry.text,
        "group_id": entry.group_id,
    }


@RMT.on_receive
async def add_to_corpus(_, data: RMD) -> None:
    """Add received messages to the corpus.

    1. Non-command (i.e. handled=False)
    2. Plain text
    """
    if data.handled:
        return
    allow_type = ("at", "face", "reply", "text")
    if any(seg.type not in allow_type for seg in data.content):
        return
    text = data.content.extract_plain_text().strip()
    if text and len(text) <= Corpus.MAX_CORPUS_TEXT_LENGTH:
        keywords = Keyword.extract(text)
        await Corpus.add(
            Entry(
                group_id=data.group_id,
                created=data.time,
                used=data.time,
                text=text,
                length=len(text),
                keywords=set(keywords),
            ))


@SMT.on_send
async def mark_as_sent(_, data: SMD) -> None:
    """Mark sent messages as recently sent."""
    text = data.content.extract_plain_text()
    if text:
        Corpus.recently_sent.append(
            (data.time, data.content.extract_plain_text()))


driver = get_driver()


@driver.on_startup
async def init_corpus() -> None:
    await Corpus.init()
