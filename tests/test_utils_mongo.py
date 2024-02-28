from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import pytest
from bson.errors import InvalidDocument
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from src.ext.message import MessageSegment as ExtMessageSegment
from src.utils.persistence import Collection, Mongo


@dataclass
class MessageData:
    time: datetime
    content: Message
    handled: bool


@pytest.mark.asyncio
async def test_mongo():
    rand_name = uuid4().hex
    db = uuid4().hex

    collection: Collection[dict, MessageData] = Mongo.collection(rand_name, db)

    @collection.serialize()
    def serialize(data: MessageData):
        content = [{
            "type": segment.type,
            "data": segment.data
        } for segment in data.content]
        return {"time": data.time, "content": content, "handled": data.handled}

    @collection.deserialize(drop_id=True)
    def _(data: dict):
        content = [
            MessageSegment(type=segment["type"], data=segment["data"])
            for segment in data["content"]
        ]
        return MessageData(
            time=data["time"],
            content=Message(content),
            handled=data["handled"],
        )

    rand_name2 = uuid4().hex
    collection2 = Mongo.collection(rand_name2, db)

    @collection2.serialize()
    def fixed_serialize(data: MessageData):
        content = ExtMessageSegment.serialize(data.content)
        return {"time": data.time, "content": content, "handled": data.handled}

    @collection2.deserialize(drop_id=True)
    def fixed_deserialize(data: dict):
        content = ExtMessageSegment.deserialize(data["content"])
        return MessageData(
            time=data["time"],
            content=content,
            handled=data["handled"],
        )

    messages = [
        MessageSegment.anonymous(),
        MessageSegment.at(123456),
        MessageSegment.contact_group(654321),
        MessageSegment.dice(),
        MessageSegment.face(123),
        MessageSegment.forward("id"),
        MessageSegment.image(uuid4().bytes, cache=True, timeout=2),
        MessageSegment.json("{\"data\": 1}"),
        MessageSegment.location(123.456, 654.321, "address"),
        MessageSegment.music("music", 999),
        MessageSegment.node_custom(1234567, "passed", "plain_text"),
        MessageSegment.poke("type", "id"),
        MessageSegment.record("file"),
        MessageSegment.text("text"),
        MessageSegment.xml("<xml></xml>"),
    ]
    try:
        for i, msg in enumerate(messages):
            message = Message(messages[:i + 1])
            data = MessageData(time=datetime.now(),
                               content=message,
                               handled=int("0x" + uuid4().hex[0], 16) % 2 == 0)
            result = await collection.insert_one(data)
            assert result.inserted_id
            data_out = await collection.get(result.inserted_id)
            assert data_out
            assert data_out.content == data.content
            assert data_out.handled == data.handled
            # mongo uses milliseconds
            assert data.time.replace(microsecond=data.time.microsecond //
                                     1000 * 1000) == data_out.time

        failure = Message([
            MessageSegment.node_custom(1234567, "nested",
                                       Message(MessageSegment.text("text")))
        ])
        with pytest.raises(InvalidDocument):
            await collection.insert_one(
                MessageData(
                    time=datetime.now(),
                    content=failure,
                    handled=False,
                ))

        result = await collection2.insert_one(
            MessageData(
                time=datetime.now(),
                content=failure,
                handled=False,
            ))
        assert result.inserted_id
        data_out = await collection2.get(result.inserted_id)
        assert data_out and data_out.content == failure

    finally:
        await collection.drop()
        await Mongo.drop_database(db)
