from typing import ClassVar

from nonebot import get_driver

from src.ext.config import Config
from src.utils.log import logger_wrapper

logger = logger_wrapper(__name__)


class RandomResponseConfig(Config):
    user_friendly: ClassVar[str] = "随机回复"
    num_reqs_to_toggle: ClassVar[int] = 3

    # requests (user_ids) for toggling the whole group
    toggle_requests: list[int] = []


class RerankReplyConfig(Config):
    """rerank 智能回复：per-group 灰度开启 + 全局路由概率。"""

    user_friendly: ClassVar[str] = "智能回复"

    # 默认关闭，superadmin 用「智能回复 开」逐个开启
    enabled: bool = False

    # 全局路由概率（存于全局配置，命令「概率」修改）
    route_prob: float = 0.3

    @classmethod
    async def list_enabled(cls) -> list[tuple[int, bool]]:
        """返回所有已显式配置的群及其启用状态。"""
        from src.ext.config import ConfigManager

        result = []
        async for doc in ConfigManager.config.find_all(
            {"name": ConfigManager.config_name(cls)}
        ):
            if doc.group_id is not None:
                result.append((doc.group_id, doc.config.enabled))
        return sorted(result)


# 进程内缓存的路由概率，启动时从全局配置加载
_route_prob: float = 0.3


def get_route_prob() -> float:
    """读全局路由概率（缓存）。"""
    return _route_prob


async def set_route_prob(prob: float) -> None:
    """设全局路由概率：持久化并更新缓存。"""
    global _route_prob
    _route_prob = prob
    cfg = await RerankReplyConfig.get_global()
    cfg.route_prob = prob
    await RerankReplyConfig.set_global(cfg)


@get_driver().on_startup
async def _load_route_prob():
    global _route_prob
    cfg = await RerankReplyConfig.get_global()
    _route_prob = cfg.route_prob
    logger.info(f"Loaded rerank global route_prob={_route_prob}")


async def toggle_user_response(*, user_id: int, enabled: bool) -> bool:
    """Toggle user's random response."""
    user = await RandomResponseConfig.get(user_id=user_id)
    if user.enabled == enabled:
        return False
    user.enabled = enabled
    await RandomResponseConfig.set(user, user_id=user_id)
    return True


async def toggle_group_response_request(
    *,
    user_id: int,
    group_id: int,
    enabled: bool,
) -> int | bool:
    """Request to toggle group's random response.

    If there are enough users requesting to toggle the group, return True.
    Otherwise, return the current number of requests.
    """
    group = await RandomResponseConfig.get(group_id=group_id)
    if group.enabled == enabled:
        return False
    if user_id not in group.toggle_requests:
        group.toggle_requests.append(user_id)
    if len(group.toggle_requests) >= RandomResponseConfig.num_reqs_to_toggle:
        group.enabled = enabled
        group.toggle_requests.clear()
        await RandomResponseConfig.set(group, group_id=group_id)
        return True
    await RandomResponseConfig.set(group, group_id=group_id)
    return len(group.toggle_requests)
