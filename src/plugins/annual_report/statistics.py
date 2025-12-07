from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from src.utils.env import inject_env
from src.utils.message.receive import ReceivedMessageTracker as RMT

from .data import GroupStatistics, UserStatistics, collect_statistics


@inject_env()
class AnnualStatistics:

    GROUP_LOCAL = "data/dynamic/annual_report/{year}/{group_id}/group.json"
    USER_LOCAL = "data/dynamic/annual_report/{year}/{group_id}/{user_id}.json"

    ANNUAL_STATISTICS_END: str
    GROUP_INHERIT: dict[int, int]  # {new_group_id: old_group_id}

    @classmethod
    def _load(cls, path: Path, model):
        if path.exists():
            return model.model_validate_json(path.read_bytes())

    @classmethod
    def _dump(cls, path: Path, data: BaseModel):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data.model_dump_json())

    @classmethod
    def _load_group(
        cls,
        year: int,
        group_id: int,
    ) -> GroupStatistics | None:
        path = Path(cls.GROUP_LOCAL.format(group_id=group_id, year=year))
        return cls._load(path, GroupStatistics)

    @classmethod
    def _load_user(
        cls,
        year: int,
        user_id: int,
        group_id: int,
    ) -> UserStatistics | None:
        path = Path(
            cls.USER_LOCAL.format(group_id=group_id,
                                  user_id=user_id,
                                  year=year))
        return cls._load(path, UserStatistics)

    @classmethod
    async def _get_statistics(cls, load_func, *args):
        if (stat := load_func(*args)) is not None:
            return stat
        await cls.process_group(args[-1])
        stat = load_func(*args)
        # assert stat is not None
        return stat

    @classmethod
    def _default_year_by_end(cls):
        ends = datetime.strptime(cls.ANNUAL_STATISTICS_END, "%Y-%m-%d")
        # before Dec, use last year
        if ends.month < 12:
            return ends.year - 1
        return ends.year

    @classmethod
    async def group(
        cls,
        *,
        year: int | None = None,
        group_id: int,
    ) -> GroupStatistics:
        year = year or cls._default_year_by_end()
        return await cls._get_statistics(cls._load_group, year, group_id)

    @classmethod
    async def user(
        cls,
        *,
        year: int | None = None,
        user_id: int,
        group_id: int,
    ) -> UserStatistics:
        year = year or cls._default_year_by_end()
        return await cls._get_statistics(cls._load_user, year, user_id,
                                         group_id)

    @classmethod
    async def process_group(cls, group_id: int):
        ends = datetime.strptime(cls.ANNUAL_STATISTICS_END, "%Y-%m-%d")
        year = cls._default_year_by_end()
        messages = await RMT.find(group_id,
                                  since=datetime(year, 1, 1),
                                  until=ends)
        if group_id in cls.GROUP_INHERIT:
            # fetch old group messages and merge
            old_group_id = cls.GROUP_INHERIT[group_id]
            old_messages = await RMT.find(old_group_id,
                                          since=datetime(year, 1, 1),
                                          until=ends)
            messages.extend(old_messages)
        group, users = collect_statistics(messages, year)
        # dump
        cls._dump(Path(cls.GROUP_LOCAL.format(group_id=group_id, year=year)),
                  group)
        for user_id, user in users.items():
            cls._dump(
                Path(
                    cls.USER_LOCAL.format(group_id=group_id,
                                          user_id=user_id,
                                          year=year)), user)
