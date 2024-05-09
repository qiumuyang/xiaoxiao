from dataclasses import dataclass, field

# yapf: disable
KEYWORDS = [
    "风", "雨", "雪", "夜", "时",
    "日", "月", "星", "云", "天", "地",
    "花", "草", "山", "水", "江", "河", "海",
    "东", "南", "西", "北", "春", "秋",
    "人", "家", "国", "情", "心", "愁",
    "书", "酒",
]
# yapf: enable


@dataclass
class GroupData:
    group_id: int
    keywords: list[str] = field(default_factory=list)
    score: dict[int, int] = field(default_factory=dict)
    history: list[tuple[int, str]] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)

    @property
    def in_progress(self) -> bool:
        return bool(self.keywords)

    @property
    def display_keywords(self) -> str:
        return " / ".join(self.keywords)

    def stop(self):
        self.keywords.clear()
        self.topic = ""
        self.score.clear()
        self.history.clear()
        self.parts.clear()
        return self


class FeiHuaData:
    """Manage FeiHuaLing data for each group."""

    # TODO: use mongodb for persistence
    data: dict[int, GroupData] = {}

    @classmethod
    async def get(cls, group_id: int) -> GroupData:
        return cls.data.get(group_id, GroupData(group_id=group_id))

    @classmethod
    async def set(cls, group_id: int, data: GroupData):
        cls.data[group_id] = data
        return data
