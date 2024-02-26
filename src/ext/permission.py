from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.permission import SUPERUSER, Permission


async def owner(event: GroupMessageEvent):
    return event.sender.role == "owner"


async def admin(event: GroupMessageEvent):
    return event.sender.role in ("admin", "owner")


OWNER = Permission(owner)
ADMIN = Permission(admin)

__all__ = [
    "ADMIN",
    "OWNER",
    "SUPERUSER",
]
