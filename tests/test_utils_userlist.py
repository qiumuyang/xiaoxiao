from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from nonebot.adapters.onebot.v11 import Message
from pymongo import MongoClient

from src.utils.persistence import Mongo
from src.utils.userlist.data import (
    MessageItem,
    UserList,
    UserListCollection,
)
from src.utils.userlist.service import UserListService


def _mongo_available():
    try:
        MongoClient(serverSelectionTimeoutMS=1000).server_info()
        return True
    except Exception:
        return False


@pytest.fixture
def check_mongo():
    if not _mongo_available():
        pytest.skip("MongoDB not available")


@pytest.fixture
def test_collection(check_mongo):
    from pymongo import AsyncMongoClient

    Mongo._client = AsyncMongoClient()
    key = uuid4().hex
    db = uuid4().hex
    UserListCollection._collection = Mongo.collection(key, db)
    UserListCollection._collection.auto_serialize(UserList)

    @UserListCollection._collection.filter()
    def _(userlist: UserList):
        if userlist.id is None:
            return {"group_id": userlist.group_id, "name": userlist.name}
        return {"_id": userlist.id}

    return db


@pytest.fixture
def test_group_id():
    return 999


@pytest.fixture
def test_list(test_group_id):
    return UserList(
        name="testlist",
        group_id=test_group_id,
        creator_id=111,
        items=[
            MessageItem(content=Message("饺子"), creator_id=111),
            MessageItem(content=Message("米饭"), creator_id=111),
        ],
    )


class TestSoftDeleteDataLayer:
    @pytest.mark.asyncio
    async def test_soft_delete_sets_deleted_at(
        self, test_collection, test_group_id, test_list
    ):
        col = UserListCollection()
        await col.create(test_group_id, 111, test_list.name)
        for item in test_list.items:
            await col.append(test_group_id, test_list.name, item)

        result = await col.delete(test_group_id, test_list.name)
        assert result.modified_count == 1

        doc = await col.find(test_group_id, test_list.name)
        assert doc is None

        raw = await UserListCollection._collection.collection.find_one(
            {"group_id": test_group_id, "name": test_list.name}
        )
        assert raw is not None
        assert raw["deleted_at"] is not None

    @pytest.mark.asyncio
    async def test_find_skips_soft_deleted(
        self, test_collection, test_group_id, test_list
    ):
        col = UserListCollection()
        await col.create(test_group_id, 111, test_list.name)
        await col.delete(test_group_id, test_list.name)

        doc = await col.find(test_group_id, test_list.name)
        assert doc is None

    @pytest.mark.asyncio
    async def test_find_all_skips_soft_deleted(
        self, test_collection, test_group_id, test_list
    ):
        col = UserListCollection()
        await col.create(test_group_id, 111, "list1")
        await col.create(test_group_id, 111, "list2")
        await col.delete(test_group_id, "list2")

        metas = await col.find_all(test_group_id)
        names = [m.name for m in metas]
        assert "list1" in names
        assert "list2" not in names

    @pytest.mark.asyncio
    async def test_count_lists_excludes_deleted(
        self, test_collection, test_group_id, test_list
    ):
        col = UserListCollection()
        await col.create(test_group_id, 111, "list1")
        await col.create(test_group_id, 111, "list2")
        await col.delete(test_group_id, "list2")

        count = await col.count_lists(test_group_id)
        assert count == 1

    @pytest.mark.asyncio
    async def test_count_items_excludes_deleted(
        self, test_collection, test_group_id, test_list
    ):
        col = UserListCollection()
        await col.create(test_group_id, 111, test_list.name)
        for item in test_list.items:
            await col.append(test_group_id, test_list.name, item)

        assert await col.count_items(test_group_id, test_list.name) == 2

        await col.delete(test_group_id, test_list.name)
        assert await col.count_items(test_group_id, test_list.name) == 0

    @pytest.mark.asyncio
    async def test_append_rejects_soft_deleted(
        self, test_collection, test_group_id, test_list
    ):
        col = UserListCollection()
        await col.create(test_group_id, 111, test_list.name)
        await col.delete(test_group_id, test_list.name)

        new_item = MessageItem(content=Message("面条"), creator_id=111)
        result = await col.append(test_group_id, test_list.name, new_item)
        assert result.modified_count == 0

    @pytest.mark.asyncio
    async def test_pop_rejects_soft_deleted(
        self, test_collection, test_group_id, test_list
    ):
        col = UserListCollection()
        await col.create(test_group_id, 111, test_list.name)
        item = MessageItem(content=Message("饺子"), creator_id=111)
        await col.append(test_group_id, test_list.name, item)
        lst = await col.find(test_group_id, test_list.name)
        await col.delete(test_group_id, test_list.name)

        result = await col.pop(test_group_id, test_list.name, lst.items[0].uuid)
        assert result.modified_count == 0

    @pytest.mark.asyncio
    async def test_create_beside_soft_deleted(
        self, test_collection, test_group_id, test_list
    ):
        col = UserListCollection()
        await col.create(test_group_id, 111, test_list.name)
        await col.delete(test_group_id, test_list.name)

        result = await col.create(test_group_id, 222, test_list.name)
        assert result is not None
        assert result.inserted_id is not None

        metas = await col.find_all(test_group_id)
        assert len(metas) == 1
        assert metas[0].name == test_list.name

    @pytest.mark.asyncio
    async def test_create_blocked_by_active(
        self, test_collection, test_group_id, test_list
    ):
        col = UserListCollection()
        await col.create(test_group_id, 111, test_list.name)

        result = await col.create(test_group_id, 222, test_list.name)
        assert result is None

    @pytest.mark.asyncio
    async def test_find_expired(self, test_collection, test_group_id, test_list):
        col = UserListCollection()
        await col.create(test_group_id, 111, "list1")
        await col.create(test_group_id, 111, "list2")
        await col.create(test_group_id, 111, "list3")
        await col.delete(test_group_id, "list1")
        await col.delete(test_group_id, "list2")

        expired = await col.find_expired(datetime.now() + timedelta(hours=1))
        names = [lst.name for lst in expired]
        assert "list1" in names
        assert "list2" in names
        assert "list3" not in names

        expired_old = await col.find_expired(datetime.now() - timedelta(days=365))
        assert len(expired_old) == 0

    @pytest.mark.asyncio
    async def test_hard_delete_removes(self, test_collection, test_group_id, test_list):
        col = UserListCollection()
        await col.create(test_group_id, 111, test_list.name)
        await col.delete(test_group_id, test_list.name)

        await col.hard_delete(test_group_id, test_list.name)
        raw = await UserListCollection._collection.collection.find_one(
            {"group_id": test_group_id, "name": test_list.name}
        )
        assert raw is None

    @pytest.mark.asyncio
    async def test_insert_if_not_exists_filters_deleted(
        self, test_collection, test_group_id, test_list
    ):
        col = UserListCollection()
        await col.create(test_group_id, 111, test_list.name)
        await col.delete(test_group_id, test_list.name)

        result = await col.create(test_group_id, 222, test_list.name)
        assert result is not None
        assert result.inserted_id is not None

        count = await col.count_lists(test_group_id)
        assert count == 1


class TestSoftDeleteServiceLayer:
    @pytest.fixture
    def mock_storage(self):
        with (
            patch(
                "src.utils.userlist.service.FileStorage.get_instance",
                new_callable=AsyncMock,
            ),
            patch(
                "src.utils.userlist.service.demote",
                new_callable=AsyncMock,
            ) as mock_demote,
        ):
            yield mock_demote

    @pytest.mark.asyncio
    async def test_remove_list_no_demote(
        self, test_collection, test_group_id, test_list, mock_storage
    ):
        mock_demote = mock_storage
        col = UserListCollection()
        svc = UserListService()
        svc.collection = col

        await col.create(test_group_id, 111, test_list.name)
        for item in test_list.items:
            await col.append(test_group_id, test_list.name, item)

        await svc.remove_list(test_group_id, test_list.name, 111, sudo=True)
        mock_demote.assert_not_called()

        doc = await col.find(test_group_id, test_list.name)
        assert doc is None

    @pytest.mark.asyncio
    async def test_purge_expired_demotes_and_deletes(
        self, test_collection, test_group_id, test_list, mock_storage
    ):
        mock_demote = mock_storage
        col = UserListCollection()
        svc = UserListService()
        svc.collection = col

        await col.create(test_group_id, 111, test_list.name)
        for item in test_list.items:
            await col.append(test_group_id, test_list.name, item)
        await col.delete(test_group_id, test_list.name)

        raw = await UserListCollection._collection.collection.find_one(
            {"group_id": test_group_id, "name": test_list.name}
        )
        raw["deleted_at"] = datetime.now() - timedelta(hours=48)
        await UserListCollection._collection.collection.update_one(
            {"_id": raw["_id"]},
            {"$set": {"deleted_at": raw["deleted_at"]}},
        )

        await svc.purge_expired()

        mock_demote.assert_called()
        raw_after = await UserListCollection._collection.collection.find_one(
            {"group_id": test_group_id, "name": test_list.name}
        )
        assert raw_after is None
