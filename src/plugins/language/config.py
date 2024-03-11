from typing import ClassVar

from src.ext.config import Config, ConfigManager


class RandomResponseConfig(Config):

    user_friendly: ClassVar[str] = "随机回复"
    num_reqs_to_toggle: ClassVar[int] = 3

    # requests (user_ids) for toggling the whole group
    toggle_requests: list[int] = []


async def toggle_user_response(*, user_id: int, enabled: bool) -> bool:
    """Toggle user's random response."""
    user = await ConfigManager.get_user(user_id, RandomResponseConfig)
    if user.enabled == enabled:
        return False
    user.enabled = enabled
    await ConfigManager.set_user(user_id, user)
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
    group = await ConfigManager.get_group(group_id, RandomResponseConfig)
    if group.enabled == enabled:
        return False
    if user_id not in group.toggle_requests:
        group.toggle_requests.append(user_id)
    if len(group.toggle_requests) >= RandomResponseConfig.num_reqs_to_toggle:
        group.enabled = enabled
        group.toggle_requests.clear()
        await ConfigManager.set_group(group_id, group)
        return True
    await ConfigManager.set_group(group_id, group)
    return len(group.toggle_requests)
