import importlib
import inspect
import re
from enum import Enum
from textwrap import dedent

from src.ext import logger_wrapper

from ..env import inject_env
from .table import Table

logger = logger_wrapper("Documentation")


class CommandCategory(Enum):
    FUN = "娱乐玄学"
    CHAT = "聊天互动"
    IMAGE = "图片处理"
    STATISTICS = "统计排行"
    UTILITY = "实用工具"
    UNKNOWN = "未分类"


@inject_env()
class EnvRecv:
    BOT_NAME: str


class CommandMeta:
    """Represents metadata extracted from a bot command docstring."""

    SECTION_ALIAS = {
        "example": "examples",
        "note": "notes",
    }
    CMD_HELP = "帮助"

    name: str
    category: CommandCategory
    aliases: set[str]
    module: str
    visible_in_overview: bool
    is_placeholder: bool

    def __init__(self, **kwargs):
        self._meta = kwargs

    @classmethod
    def parse(cls, func):
        """Extracts structured information from a function's docstring."""
        doc = inspect.getdoc(func)
        if not doc:
            return cls()

        lines = dedent(doc.rstrip()).split("\n")

        sections: dict = {
            "description": [],
            "usage": [],
            "examples": [],
            "notes": [],
        }
        current_section = "description"

        section_pattern = re.compile(r"^(\w+):\s*(.*)", re.IGNORECASE)

        for line in lines:
            section_match = section_pattern.match(line)
            if section_match:
                section_name = section_match.group(1).lower()
                section_name = cls.SECTION_ALIAS.get(section_name,
                                                     section_name)
                content = section_match.group(2).rstrip()
                if current_section != section_name:
                    current_section = section_name
                    sections.setdefault(current_section, [])
                if content:
                    sections[current_section].append(content)
                continue

            sections[current_section].append(line.rstrip())

        for k, v in sections.items():
            sections[k] = "\n".join(v)
        return cls(**sections, module=func.__module__)

    @property
    def description(self) -> str:
        return self.meta.get("description", "").strip()

    @property
    def examples(self) -> list[str]:
        if examples := dedent(self.meta.get("examples", "")):
            return [_ for ex in examples.split("\n\n") if (_ := ex.rstrip())]
        return []

    @property
    def notes(self) -> list[str]:
        if notes := self.meta.get("notes"):
            lstrip_notes = "\n".join([_.lstrip() for _ in notes.splitlines()])
            return self.parse_markdown_list(lstrip_notes)
        return []

    @property
    def usage(self) -> list[str]:
        return list(
            filter(lambda x: x.rstrip(),
                   dedent(self.meta.get("usage", "")).splitlines()))

    @property
    def extra(self) -> dict[str, str]:
        return {
            k: v
            for k, v in self.meta.items()
            if k not in ["description", "usage", "examples", "notes"]
        }

    def __getattr__(self, name):
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        str_keys = {
            key
            for key, value in self._meta.items() if isinstance(value, str)
        }
        if name not in str_keys:
            return self._meta.get(name)
        return self.meta.get(name)

    def __setattr__(self, name, value):
        if name == "_meta":
            object.__setattr__(self, name, value)
        else:
            self._meta[name] = value

    @property
    def meta(self):
        """Fill in the template."""

        mod = importlib.import_module(self._meta["module"])
        globals_ = mod.__dict__
        inner = {
            "cmd": self._meta.get("name"),
            "cmdhelp": self.CMD_HELP,
            "bot": EnvRecv.BOT_NAME
        }
        inner = dict(filter(lambda x: x[1], inner.items()))

        def sub(m):
            try:
                evaluated = str(eval(m.group(1), globals_ | inner))
                # this 2-step replacement is to allow simple nested templates
                return evaluated.replace("{cmd}", self._meta["name"])
            except Exception as e:
                return m.group(0)

        return {
            k: re.sub(r"\{(.+?)\}", sub, v, flags=re.DOTALL)
            for k, v in self._meta.items() if isinstance(v, str)
        }

    def export_markdown(self) -> str:
        """Export the metadata to a markdown format."""
        if self.aliases:
            alias = "，".join(self.aliases)
            alias = f"`{alias}`"
        else:
            alias = ""
        parts = [
            f"## {self.name} {alias}",
            self.description,
        ]
        if (_ := self.special) and (sp := dedent(_)):
            lines = []
            for line in sp.splitlines():
                if not line.strip():
                    lines.append("> ")
                else:
                    lines.append(f"> *{line}*")
            parts.append("\n".join(lines))
            if not sp.strip().endswith(("。", "？", "！", "…", "”", "）")):
                logger.warning(
                    f"⚠️  [{self.name}] special no ending punctuation")
        else:
            logger.warning(f"❓ [{self.name}] no special")
        if self.usage:
            tbl_input = Table(["输入", "描述"])
            tbl_param = Table(["参数", "描述", "范围"], ["`{}`", "{}", "`{}`"])
            tbl_syntax = Table(["语法", "描述"], ["`{}`", "{}"])
            plain_text = []
            for line in self.usage:
                # :param <name>: <description> || <range>
                # :syntax <name>: <description>
                if m := re.search(r":param\s+([^:]+?):\s*(.+)$", line):
                    name, desc_range = m.groups()
                    if " || " in desc_range:
                        desc, range_ = desc_range.rsplit(" || ", 1)
                    else:
                        desc, range_ = desc_range, ""
                    tbl_param.append([name, desc, range_])
                elif m := re.search(r":syntax\s+([^:]+?):\s*(.+)$", line):
                    name, desc = m.groups()
                    tbl_syntax.append([name, desc])
                elif " - " in line:
                    input_, desc = line.rsplit(" - ", 1)
                    tbl_input.append([input_, desc])
                elif text := line.rstrip():
                    plain_text.append(text)
            parts.append("### 用法")
            if tbl_input:
                parts.append(tbl_input.render())
            if tbl_param:
                parts.append(tbl_param.render())
            if tbl_syntax:
                parts.append(tbl_syntax.render())
            if plain_text:
                parts.append("\n".join(plain_text))
        if self.examples:
            parts.append("### 示例")
            for example in self.examples:
                parts.append(f"```text\n{example}\n```")
        if self.notes:
            parts.append("### 说明")
            parts.append("\n".join(f"- {note}" for note in self.notes))
        return "\n\n".join(parts)

    @staticmethod
    def parse_markdown_list(markdown: str):
        lines = markdown.split("\n")
        stack = []  # Stack to maintain nesting levels
        root = []  # Root list to return

        def add_item(item, level):
            """Helper function to add an item to the correct level."""
            while len(stack) > level:
                stack.pop()

            if not stack:
                root.append(item)
                stack.append(root)
            else:
                parent = stack[-1][-1]
                if not isinstance(parent, list):
                    parent = stack[-1][-1] = [parent, []]
                parent[1].append(item)
                stack.append(parent[1])

        current_item = None
        current_indent = None

        for line in lines:
            match = re.match(r"^(\s*)([-*+]\s+)(.*)", line)
            if match:
                if current_item is not None:
                    add_item(current_item, current_indent)

                indent, _, content = match.groups()
                current_indent = len(
                    indent) // 2  # Assume 2 spaces per indent level
                current_item = content
            elif current_item is not None and line.strip():
                # current_item += " " + line.strip()
                if current_item.endswith("\\"):
                    current_item = current_item[:-1] + "\n" + line.strip()
                else:
                    current_item += " " + line.strip()

        if current_item is not None:
            add_item(current_item, current_indent)

        return root


class CommandOverview:

    def __init__(self, commands: dict[str, CommandMeta]):
        self.commands = commands

    def export_markdown(self) -> str:
        # group commands by category
        categories: dict[CommandCategory, list[CommandMeta]] = {}
        for cmd in self.commands.values():
            if not cmd.visible_in_overview:
                continue
            categories.setdefault(cmd.category, []).append(cmd)

        def export_category(category: CommandCategory):
            commands = categories.get(category)
            if not commands:
                return ""
            parts = [f"### {category.value}"]
            tbl = Table(["指令", "别名", "描述"])
            for cmd in commands:
                asterisk = "\\*" if cmd.is_placeholder else ""
                tbl.append([
                    cmd.name + asterisk,
                    ", ".join(cmd.aliases) if cmd.aliases else "-",
                    cmd.description
                ])
            parts.append(tbl.render())
            return "\n\n".join(parts)

        intro = [
            "## 指令概览",
            f"- 使用`{CommandMeta.CMD_HELP} <指令>`查看详细信息",
            ("- 注意： 带\\*为*功能名称*，*非实际指令*，"
             "无法通过`<指令> [参数]...`方式触发"),
        ]
        acknowledgement = [
            "## 致谢",
            "本项目基于以下项目开发",
            "- [Lagrange.Core](https://github.com/LagrangeDev/Lagrange.Core)",
            "- [NoneBot2](https://nonebot.dev)",
        ]
        parts = [
            "\n".join(intro),
            *[export_category(cat) for cat in CommandCategory],
            "\n".join(acknowledgement),
        ]
        return "\n\n".join(parts)


if __name__ == "__main__":

    template_value = "Since eval is used,"

    class Complex:
        value = "expression can also be used"

    def fn():
        """Here is the description.

        Still the description.

        Template test: {template_value} {Complex.value}

        Usage:
            This is the usage.
            Each new line is a new item.
            /cmd          - blah blah
            /cmd <arg>    - blah blah

        Examples:
            >>> user input
            bot output

            >>> use double newlines to separate examples
            >>> multiple user inputs
            bot output

        Notes:
            - This is a note.
            - This is another note.
              - No nesting support yet.
            - Multiline notes are supported.\\
              Like this.

        Test:
            Test extra section.

        Warning:
            Another extra section.
        """

    meta = CommandMeta.parse(fn)
    print(f"{meta.description=}")
    print(f"{meta.usage=}")
    print(f"{meta.examples=}")
    print(f"{meta.notes=}")
    print(f"{meta.extra=}")
    with open("test.md", "w") as f:
        f.write(meta.export_markdown())
