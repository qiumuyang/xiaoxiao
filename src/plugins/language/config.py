from typing import ClassVar

from src.ext.config import Config


class RandomResponseConfig(Config):

    user_friendly: ClassVar[str] = "随机回复"
    num_reqs_to_toggle: ClassVar[int] = 3

    # requests (user_ids) for toggling the whole group
    toggle_requests: list[int] = []


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
