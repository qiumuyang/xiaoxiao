from dataclasses import dataclass
from datetime import datetime

import pytest
from pydantic import BaseModel

from src.utils.persistence import Collection, Mongo
from src.utils.persistence.serialize import deserialize, serialize


@dataclass
class ObjectTest:

    @dataclass
    class Nested:
        arr: list[int] | None

    plain: int
    plain2: str
    plain3: float
    date: datetime

    container: list[int]
    container2: dict[str, float]

    optional: int | None
    nested: Nested
    multiple: list[Nested]
    multiple2: list[dict[str, Nested]]


def test_serialize_deserialize():
    obj = ObjectTest(plain=1,
                     plain2="2",
                     plain3=3.0,
                     date=datetime(2021, 1, 1),
                     container=[1, 2, 3],
                     container2={
                         "a": 1.0,
                         "b": 2.0
                     },
                     optional=None,
                     nested=ObjectTest.Nested(arr=[1, 2, 3]),
                     multiple=[
                         ObjectTest.Nested(arr=[1, 2, 3]),
                         ObjectTest.Nested(arr=[4, 5, 6])
                     ],
                     multiple2=[{
                         "a": ObjectTest.Nested(arr=[1, 2, 3])
                     }, {
                         "b": ObjectTest.Nested(arr=[4, 5, 6])
                     }])

    serialized = serialize(obj)
    deserialized = deserialize(serialized, ObjectTest)

    assert obj == deserialized


class ObjectTest2(BaseModel):
    uuid: str
    time: datetime
    nested: list[dict[str, int]]


@pytest.mark.asyncio
async def test_serialize_deserialize_pydantic():
    collection: Collection[dict, ObjectTest2] = Mongo.collection(
        name="test_serialize", db="test")
    collection.auto_serialize(ObjectTest2)
    from uuid import uuid4

    uuid = str(uuid4())
    obj = ObjectTest2(uuid=uuid,
                      time=datetime(2021, 1, 1),
                      nested=[{
                          "a": 1
                      }, {
                          "b": 2
                      }])
    await collection.insert_one(obj)
    result = await collection.find_one({"uuid": uuid})
    assert result is not None
    assert obj == result
