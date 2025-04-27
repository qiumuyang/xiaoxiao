import asyncio
import math
from datetime import datetime
from typing import Any, Awaitable, ClassVar, Iterable, Literal, NamedTuple
from uuid import uuid4

from nonebot.adapters.onebot.v11 import Message
from pydantic import BaseModel, Field

from src.utils.persistence import Collection, Mongo, PydanticObjectId


class MessageItem(BaseModel):
    type: Literal["message"] = "message"
    content: Message
    creator_id: int
    uuid: str = Field(default_factory=lambda: str(uuid4()))

    def __str__(self):
        return str(self.content)


class ReferenceItem(BaseModel):
    type: Literal["reference"] = "reference"
    name: str
    creator_id: int
    uuid: str = Field(default_factory=lambda: str(uuid4()))

    def __str__(self) -> str:
        return f"[{self.name}]"


class Pagination(NamedTuple):
    page_id: int
    page_size: int
    num_pages: int
    items: list[MessageItem | ReferenceItem]

    def enumerate(self):
        return enumerate(self.items, start=self.page_id * self.page_size)


class UserList(BaseModel):
    id: PydanticObjectId | None = Field(alias="_id", default=None)
    name: str
    group_id: int
    creator_id: int
    created_at: datetime = Field(default_factory=datetime.now)
    items: list[MessageItem | ReferenceItem] = Field(default_factory=list)

    async def db_append(self, *items: MessageItem | ReferenceItem):
        result = await UserListCollection().append(self.group_id, self.name,
                                                   *items)
        if result.modified_count > 0:
            self.items.extend(items)
        return result

    async def db_pop(self, *uuids: str):
        result = await UserListCollection().pop(self.group_id, self.name,
                                                *uuids)
        if result.modified_count > 0:
            self.items = [i for i in self.items if i.uuid not in uuids]
        return result

    def paginate(self, page_id: int, page_size: int, strict: bool = False):
        if page_size <= 0:
            raise ValueError("page_size must be greater than 0")
        num_pages = max(math.ceil(len(self.items) / page_size), 1)
        if strict and not 0 <= page_id < num_pages:
            raise IndexError(f"{page_id} out of page range")
        page_id = max(0, min(page_id, num_pages - 1))
        return Pagination(
            page_id, page_size, num_pages,
            self.items[page_id * page_size:(page_id + 1) * page_size])

    @property
    def expanded_items(self) -> Awaitable[list[Message]]:
        collection = UserListCollection()
        raw = [i.content for i in self.items if isinstance(i, MessageItem)]
        ref = [
            i for i in self.items
            if isinstance(i, ReferenceItem) and i.name != self.name
        ]

        async def load_message(group_id: int, name: str):
            lst = await collection.find(group_id, name)
            return [
                i.content for i in lst.items if isinstance(i, MessageItem)
            ] if lst else []

        async def result():
            return sum(
                await asyncio.gather(
                    *[load_message(self.group_id, i.name) for i in ref]), raw)

        return result()

    @property
    def valid_references(self) -> Awaitable[list[str]]:

        async def result():
            exists = await asyncio.gather(*[
                UserListCollection().find(self.group_id, i.name)
                for i in self.items if isinstance(i, ReferenceItem)
            ])
            return [i.name for i in exists if i is not None]

        return result()

    def append(self, item: MessageItem | ReferenceItem):
        self.items.append(item)

    def extend(self, items: Iterable[MessageItem | ReferenceItem]):
        self.items.extend(items)

    def remove(self, item: MessageItem | ReferenceItem):
        self.items.remove(item)

    def clear(self):
        self.items.clear()

    def pop(self, index: int = -1):
        return self.items.pop(index)

    def __getitem__(self, index: int):
        return self.items[index]

    def __len__(self):
        return len(self.items)

    def __setitem__(self, index: int, item: MessageItem | ReferenceItem):
        self.items[index] = item

    def __str__(self):
        return str([str(i) for i in self.items])


class UserListCollection:

    _collection: ClassVar[Collection[dict[str, Any], UserList]]
    _collection = Mongo.collection("userlist")
    _collection.auto_serialize(UserList)

    def __getitem__(
        self,
        index: tuple[int, str],
    ) -> Awaitable[UserList | None]:
        return self.find(*index)

    async def create(self, group_id: int, creator_id: int, name: str):
        return await self._collection.insert_if_not_exists(
            UserList(name=name, group_id=group_id, creator_id=creator_id))

    async def find(self, group_id: int, name: str):
        return await self._collection.find_one(filter={
            "group_id": group_id,
            "name": name
        })

    def find_all(self, group_id: int):
        return self._collection.find_all({"group_id": group_id})

    async def delete(self, group_id: int, name: str):
        return await self._collection.delete_one(filter={
            "group_id": group_id,
            "name": name
        })

    async def append(
        self,
        group_id: int,
        name: str,
        *items: MessageItem | ReferenceItem,
    ):
        return await self._collection.update_one(
            filter={
                "group_id": group_id,
                "name": name
            },
            update={
                "$push": {
                    "items": {
                        "$each": [i.model_dump(mode="json") for i in items]
                    }
                }
            })

    async def pop(self, group_id: int, name: str, *uuid: str):
        return await self._collection.update_one(
            filter={
                "group_id": group_id,
                "name": name
            },
            update={"$pull": {
                "items": {
                    "uuid": {
                        "$in": list(uuid)
                    }
                }
            }})

    async def update(self, userlist: UserList):
        return await self._collection.update_one(
            userlist,
            {"$set": userlist.model_dump(mode="json", exclude={"id"})})

    async def count_lists(self, group_id: int):
        return await self._collection.count({"group_id": group_id})

    async def count_items(self, group_id: int, name: str):
        return await self._collection.count({
            "group_id": group_id,
            "name": name
        })


@UserListCollection._collection.filter()
def _(userlist: UserList):
    if userlist.id is None:
        return {"group_id": userlist.group_id, "name": userlist.name}
    return {"_id": userlist.id}
