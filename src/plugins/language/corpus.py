from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property
from typing import Any, Iterable

import jieba.posseg as pseg

from src.utils.message.receive import MessageData as RMD
from src.utils.message.receive import ReceivedMessageTracker as RMT
from src.utils.message.send import MessageData as SMD
from src.utils.message.send import SentMessageTracker as SMT
from src.utils.persistence import Collection, Mongo


@dataclass
class Entry:
    group_id: int
    created: datetime
    used: datetime
    text: str

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


class Corpus:

    KEY = "corpus"
    corpus: Collection[dict, Entry] = Mongo.collection(KEY)

    recently_sent: list[tuple[datetime, str]] = []
    TTL_SENTD = timedelta(minutes=15)

    FIRST_TIME_SAMPLE_INTERVAL = timedelta(minutes=15)
    USED_SAMPLE_INTERVAL = timedelta(hours=4)

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
        filter: dict[str, Any] | None = None,
        sample: int | None = None,
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
        from_group = {
            "group_id": {
                "$in": group_id
            }
        } if isinstance(group_id, list) else {
            "group_id": group_id
        }
        if length is not None:
            text_length = {
                "$expr": {
                    "and": [{
                        "$gte": [{
                            "$strLenCP": "$text"
                        }, length[0]]
                    }, {
                        "$lte": [{
                            "$strLenCP": "$text"
                        }, length[1]]
                    }]
                } if isinstance(length, tuple) else {
                    "$eq": [{
                        "$strLenCP": "$text"
                    }, length]
                }
            }
            filter.update(text_length)

        match_filter: dict[str, Any] = {
            "$match": {
                "$and":
                [filter, not_recent_sent, not_recent_added, from_group]
            }
        }
        pipeline = [match_filter]
        if sample is not None:
            pipeline.append({"$sample": {"size": sample}})
        return cls.corpus.aggregate(pipeline)


@Corpus.corpus.serialize()
def _(entry: Entry) -> dict:
    return {
        "group_id": entry.group_id,
        "created": entry.created,
        "used": entry.used,
        "text": entry.text,
    }


@Corpus.corpus.deserialize()
def deserialize(data: dict) -> Entry:
    return Entry(
        group_id=data["group_id"],
        created=data["created"],
        used=data["used"],
        text=data["text"],
    )


@Corpus.corpus.filter()
def _(entry: Entry) -> dict:
    return {
        "text": entry.text,
        "group_id": entry.group_id,
    }


@RMT.on_receive
async def add_to_corpus(object_id: str | None, data: RMD) -> None:
    """Add received messages to the corpus.

    1. Non-command (i.e. handled=False)
    2. Plain text
    """
    if data.handled or any(seg.type != "text" for seg in data.content):
        return
    text = data.content.extract_plain_text()
    if text.strip():
        await Corpus.add(
            Entry(
                group_id=data.group_id,
                created=data.time,
                used=data.time,
                text=text,
            ))


@SMT.on_send
async def mark_as_sent(object_id: str, data: SMD) -> None:
    """Mark sent messages as recently sent."""
    text = data.content.extract_plain_text()
    if text:
        Corpus.recently_sent.append(
            (data.time, data.content.extract_plain_text()))
