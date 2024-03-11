from enum import IntEnum
from typing import Any


class ButtonStyle(IntEnum):
    GRAY_LINE = 0
    BLUE_LINE = 1


class ButtonAction(IntEnum):
    JUMP = 0
    CALLBACK = 1
    TEXT_INPUT = 2


class ButtonPermission(IntEnum):
    # SPECIFY_USER = 0
    # ADMIN = 1
    EVERYONE = 2


class Button:

    def __init__(
        self,
        text: str,
        data: str,
        enter: bool = False,
        visited_text: str = "",
        unsupport_tips: str = "暂不支持此功能",
        style: ButtonStyle = ButtonStyle.BLUE_LINE,
        action: ButtonAction = ButtonAction.TEXT_INPUT,
        permission: ButtonPermission = ButtonPermission.EVERYONE,
    ):
        self.text = text
        self.visited_text = visited_text or text
        self.style = style
        self.action = action
        self.permission = permission
        self.data = data
        self.enter = enter
        self.unsupport_tips = unsupport_tips

    def __or__(self, other: "Button") -> "ButtonGroup":
        return ButtonGroup() | self | other

    def __add__(self, other: "Button | ButtonGroup") -> "ButtonGroup":
        return (ButtonGroup() | self) + other

    def dict(self, id: str) -> dict[str, Any]:
        return {
            "id": id,
            "render_data": {
                "label": self.text,
                "visited_label": self.visited_text,
                "style": self.style.value,
            },
            "action": {
                "type": self.action.value,
                "permission": {
                    "type": self.permission.value,
                },
                "data": self.data,
                "enter": self.enter,
                "unsupport_tips": self.unsupport_tips,
                "at_bot_show_channel_list": True,
            }
        }


class ButtonGroup:

    MAX_ROW = 5
    MAX_COL = 5

    def __init__(self):
        self.rows: list[list[Button]] = []

    def __or__(self, other: Button) -> "ButtonGroup":
        if not isinstance(other, Button):
            raise TypeError("Expected Button")
        if isinstance(other, Button):
            if not self.rows:
                self.rows.append([])
            self.rows[-1].append(other)
            if len(self.rows[-1]) > self.MAX_COL:
                raise ValueError("Too many buttons in a row")
        return self

    def __add__(self, other: "Button | ButtonGroup") -> "ButtonGroup":
        if not isinstance(other, (Button, ButtonGroup)):
            raise TypeError("Expected Button or ButtonGroup")
        if isinstance(other, Button):
            self.rows.append([other])
        elif isinstance(other, ButtonGroup):
            self.rows.extend(other.rows)
        if len(self.rows) > self.MAX_ROW:
            raise ValueError("Too many rows of buttons")
        return self

    def dict(self) -> dict[str, Any]:
        return {
            "rows": [{
                "buttons": [
                    button.dict(f"{i * self.MAX_COL + j}")
                    for j, button in enumerate(row)
                ]
            } for i, row in enumerate(self.rows)]
        }
