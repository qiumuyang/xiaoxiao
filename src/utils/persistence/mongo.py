from typing import Any, AsyncGenerator, Callable, Generic, Mapping, TypeVar

from motor.core import (AgnosticCollection, AgnosticCommandCursor,
                        AgnosticCursor)
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.results import (DeleteResult, InsertManyResult, InsertOneResult,
                             UpdateResult)

from src.ext import logger_wrapper

T = TypeVar("T")
D = TypeVar("D", bound=Mapping[str, Any])

logger = logger_wrapper(__name__)


class Collection(Generic[D, T]):

    def __init__(self, collection: AgnosticCollection) -> None:
        self.collection = collection
        self._to_mongo: Callable[[T], D] = lambda x: x  # type: ignore
        self._from_mongo: Callable[[D], T] = lambda x: x  # type: ignore
        self._to_filter: Callable[[T], D] = lambda x: x  # type: ignore

    def serialize(self):

        def decorator(fn: Callable[[T], D]) -> Callable[[T], D]:
            self._to_mongo = fn
            return fn

        return decorator

    def deserialize(self, drop_id: bool = False):

        def decorator(fn: Callable[[D], T]) -> Callable[[D], T]:

            def wrapper(doc: D) -> T:
                if drop_id:
                    doc.pop("_id", None)  # type: ignore
                return fn(doc)

            self._from_mongo = wrapper
            return fn

        return decorator

    def filter(self):

        def decorator(fn: Callable[[T], D]) -> Callable[[T], D]:
            self._to_filter = fn
            return fn

        return decorator

    async def insert_one(self, object: T, *args, **kwargs) -> InsertOneResult:
        return await self.collection.insert_one(self._to_mongo(object), *args,
                                                **kwargs)

    async def insert_many(
        self,
        objects: list[T],
        *args,
        **kwargs,
    ) -> InsertManyResult:
        return await self.collection.insert_many(
            [self._to_mongo(doc) for doc in objects],
            *args,
            **kwargs,
        )

    async def insert_if_not_exists(
        self,
        object: T,
    ) -> InsertOneResult | None:
        if await self.find_one(object):
            return None
        return await self.insert_one(object)

    async def get(self, id: str) -> T | None:
        return await self.find_one({"_id": id})

    async def find_one(
        self,
        filter: dict[str, Any] | T,
        *args,
        **kwargs,
    ) -> T | None:
        if not isinstance(filter, dict):
            filter = self._to_filter(filter)
        doc = await self.collection.find_one(filter, *args, **kwargs)
        return self._from_mongo(doc) if doc else None

    async def find_one_and_delete(
        self,
        filter: dict[str, Any] | T,
        *args,
        **kwargs,
    ) -> T | None:
        if not isinstance(filter, dict):
            filter = self._to_filter(filter)
        doc = await self.collection.find_one_and_delete(
            filter, *args, **kwargs)
        return self._from_mongo(doc) if doc else None

    async def find_one_and_update(
        self,
        filter: dict[str, Any] | T,
        update: dict[str, Any] | T,
        *args,
        **kwargs,
    ) -> T | None:
        if not isinstance(filter, dict):
            filter = self._to_filter(filter)
        if not isinstance(update, dict):
            update = {"$set": self._to_mongo(update)}
        doc = await self.collection.find_one_and_update(
            filter, update, *args, **kwargs)
        return self._from_mongo(doc) if doc else None

    def find(
        self,
        filter: dict[str, Any],
        *args,
        **kwargs,
    ) -> AgnosticCursor:
        return self.collection.find(filter, *args, **kwargs)

    def aggregate(
        self,
        pipeline: list[dict[str, Any]],
        *args,
        **kwargs,
    ) -> AgnosticCommandCursor:
        return self.collection.aggregate(pipeline, *args, **kwargs)

    async def find_all(
        self,
        filter: dict[str, Any],
        *args,
        **kwargs,
    ) -> AsyncGenerator[T, None]:
        async for doc in self.collection.find(filter, *args, **kwargs):
            yield self._from_mongo(doc)

    async def update_one(
        self,
        filter: dict[str, Any] | T,
        update: dict[str, Any] | T,
        *args,
        **kwargs,
    ) -> UpdateResult:
        if not isinstance(filter, dict):
            filter = self._to_filter(filter)
        if not isinstance(update, dict):
            update = {"$set": self._to_mongo(update)}
        return await self.collection.update_one(filter, update, *args,
                                                **kwargs)

    async def update_many(
        self,
        filter: dict[str, Any] | T,
        update: dict[str, Any] | T,
        *args,
        **kwargs,
    ) -> UpdateResult:
        if not isinstance(filter, dict):
            filter = self._to_filter(filter)
        if not isinstance(update, dict):
            update = {"$set": self._to_mongo(update)}
        return await self.collection.update_many(filter, update, *args,
                                                 **kwargs)

    async def delete_one(
        self,
        filter: dict[str, Any] | T,
        *args,
        **kwargs,
    ) -> DeleteResult:
        if not isinstance(filter, dict):
            filter = self._to_filter(filter)
        return await self.collection.delete_one(filter, *args, **kwargs)

    async def delete_many(
        self,
        filter: dict[str, Any] | T,
        *args,
        **kwargs,
    ) -> DeleteResult:
        if not isinstance(filter, dict):
            filter = self._to_filter(filter)
        return await self.collection.delete_many(filter, *args, **kwargs)

    async def drop(self) -> None:
        await self.collection.drop()


class Mongo:

    DB = "nonebot2"

    _client = AsyncIOMotorClient()

    collections: list[tuple[str, str]] = []

    @classmethod
    def collection(cls, name: str, db: str = "") -> Collection:
        db = db or cls.DB
        if (db, name) not in cls.collections:
            cls.collections.append((db, name))
        else:
            logger.warning(
                f"Collection {name} already exists in database {db}")
        return Collection(cls._client[db][name])

    @classmethod
    def close(cls) -> None:
        cls._client.close()

    @classmethod
    async def drop_collection(cls, name: str, db: str = "") -> None:
        db = db or cls.DB
        await cls._client[db][name].drop()

    @classmethod
    async def drop_database(cls, db: str) -> None:
        await cls._client.drop_database(db)