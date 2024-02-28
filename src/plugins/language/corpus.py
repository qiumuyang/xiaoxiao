from dataclasses import dataclass
from datetime import datetime, timedelta

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


@Corpus.corpus.serialize()
def _(entry: Entry) -> dict:
    return {
        "group_id": entry.group_id,
        "created": entry.created,
        "used": entry.used,
        "text": entry.text,
    }


@Corpus.corpus.deserialize()
def _(data: dict) -> Entry:
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
