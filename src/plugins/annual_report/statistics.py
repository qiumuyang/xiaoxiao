from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from src.utils.env import inject_env
from src.utils.message.receive import ReceivedMessageTracker as RMT

from .data import GroupStatistics, UserStatistics, collect_statistics


@inject_env()
class AnnualStatistics:

    GROUP_LOCAL = "data/dynamic/annual_report/{group_id}/group.json"
    USER_LOCAL = "data/dynamic/annual_report/{group_id}/{user_id}.json"

    ANNUAL_STATISTICS_END: str

    @classmethod
    def _load(cls, path: Path, model):
        if path.exists():
            return model.model_validate_json(path.read_bytes())

    @classmethod
    def _dump(cls, path: Path, data: BaseModel):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data.model_dump_json())

    @classmethod
    def _load_group(cls, group_id: int) -> GroupStatistics | None:
        path = Path(cls.GROUP_LOCAL.format(group_id=group_id))
        return cls._load(path, GroupStatistics)

    @classmethod
    def _load_user(cls, user_id: int, group_id: int) -> UserStatistics | None:
        path = Path(cls.USER_LOCAL.format(group_id=group_id, user_id=user_id))
        return cls._load(path, UserStatistics)

    @classmethod
    async def _get_statistics(cls, load_func, *args):
        if (stat := load_func(*args)) is not None:
            return stat
        await cls.process_group(args[-1])
        stat = load_func(*args)
        assert stat is not None
        return stat

    @classmethod
    async def group(cls, group_id: int) -> GroupStatistics:
        return await cls._get_statistics(cls._load_group, group_id)

    @classmethod
    async def user(cls, user_id: int, group_id: int) -> UserStatistics:
        return await cls._get_statistics(cls._load_user, user_id, group_id)

    @classmethod
    async def process_group(cls, group_id: int):
        date = datetime.strptime(cls.ANNUAL_STATISTICS_END, "%Y-%m-%d")
        # before Dec, use last year
        if date.month < 12:
            year = date.year - 1
        else:
            year = date.year
        messages = await RMT.find(group_id,
                                  since=datetime(year, 1, 1),
                                  until=datetime(year, 12, 31))
        group, users = collect_statistics(messages, year)
        # dump
        cls._dump(Path(cls.GROUP_LOCAL.format(group_id=group_id)), group)
        for user_id, user in users.items():
            cls._dump(
                Path(cls.USER_LOCAL.format(group_id=group_id,
                                           user_id=user_id)), user)
