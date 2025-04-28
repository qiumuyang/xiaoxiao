import random

from nonebot.adapters.onebot.v11 import Message

from src.ext import MessageSegment

from ..log import logger_wrapper
from ..persistence import FileStorage
from .data import MessageItem, ReferenceItem, UserListCollection
from .exception import (ListPermissionError, TooManyItemsError,
                        TooManyListsError)

logger = logger_wrapper("userlist")


async def promote(*messages: Message):
    storage = await FileStorage.get_instance()
    exceptions = []
    for message in messages:
        for segment in message:
            segment = MessageSegment.from_onebot(segment)
            if segment.is_image() or segment.is_mface():
                try:
                    filename = segment.extract_filename()
                    url = segment.extract_url()
                    await storage.load(url, filename)
                    if not await storage.promote(filename):
                        await storage.increase_reference(filename)
                except Exception as e:
                    exceptions.append(e)
    if exceptions:
        logger.warning(f"Promote failed: {exceptions}")
    return messages


async def demote(*messages: Message):
    storage = await FileStorage.get_instance()
    exceptions = []
    for message in messages:
        for segment in message:
            segment = MessageSegment.from_onebot(segment)
            if segment.is_image() or segment.is_mface():
                try:
                    filename = segment.extract_filename()
                    await storage.decrease_reference(filename)
                except Exception as e:
                    exceptions.append(e)
    if exceptions:
        logger.warning(f"Demote failed: {exceptions}")
    return messages


class UserListService:

    MAX_ITEMS = 100
    MAX_LISTS = 100

    collection = UserListCollection()

    @classmethod
    async def find_list(cls, group_id: int, name: str):
        return await cls.collection.find(group_id, name)

    @classmethod
    async def find_all_list_meta(cls, group_id: int):
        return await cls.collection.find_all(group_id)

    @classmethod
    async def create_list(cls, group_id: int, name: str, creator_id: int):
        if await cls.collection.count_lists(group_id) >= cls.MAX_LISTS:
            raise TooManyListsError
        return await cls.collection.create(group_id, creator_id, name)

    @classmethod
    async def remove_list(cls,
                          group_id: int,
                          name: str,
                          operator_id: int,
                          sudo: bool = False):
        lst = await cls.collection.find(group_id, name)
        if lst is not None:
            if not sudo and lst.creator_id != operator_id:
                raise ListPermissionError
            res = await cls.collection.delete(group_id, name)
            if res.deleted_count == 1:
                # decrease image reference
                for item in lst.items:
                    if isinstance(item, MessageItem):
                        await demote(item.content)
        return lst

    @classmethod
    async def random_choice(cls, group_id: int, name: str):
        lst = await cls.collection.find(group_id, name)
        if lst is not None:
            items = await lst.expanded_items
            return random.choice(items) if items else None

    @classmethod
    async def append_message(cls, group_id: int, name: str, creator_id: int,
                             *message: Message):
        if await cls.collection.count_items(
                group_id, name) + len(message) >= cls.MAX_ITEMS:
            raise TooManyItemsError
        res = await cls.collection.append(
            group_id, name, *[
                MessageItem(content=msg, creator_id=creator_id)
                for msg in message
            ])
        if res.modified_count > 0:
            await promote(*message)
        return res

    @classmethod
    async def append_reference(cls, group_id: int, name: str, creator_id: int,
                               *reference: str):
        if await cls.collection.count_items(
                group_id, name) + len(reference) >= cls.MAX_ITEMS:
            raise TooManyItemsError
        return await cls.collection.append(
            group_id, name, *[
                ReferenceItem(name=ref, creator_id=creator_id)
                for ref in reference
            ])

    @classmethod
    async def remove_by_uuid(cls, group_id: int, name: str, *uuid: str):
        lst = await cls.collection.find(group_id, name)
        res = await cls.collection.pop(group_id, name, *uuid)
        if res.modified_count > 0 and lst is not None:
            items = [
                i for i in lst.items
                if i.uuid in uuid and isinstance(i, MessageItem)
            ]
            await demote(*[i.content for i in items])
        return res

    @classmethod
    async def remove_by_index(cls, group_id: int, name: str, *indices: int):
        lst = await cls.collection.find(group_id, name)
        if lst is not None:
            uuids = [lst.items[i].uuid for i in indices if 0 <= i < len(lst)]
        else:
            uuids = []
        return await cls.remove_by_uuid(group_id, name, *uuids)
