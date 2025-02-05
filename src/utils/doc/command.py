import importlib
import inspect
import re
from enum import Enum


class CommandCategory(Enum):
    CHAT = "聊天互动"
    FUN = "娱乐玄学"
    IMAGE = "图片处理"
    STATISTICS = "统计排行"
    TEXT = "文本处理"
    UTILITY = "实用工具"
    UNKNOWN = "未分类"


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

    def __init__(self, **kwargs):
        self._meta = kwargs

    @classmethod
    def parse(cls, func):
        """Extracts structured information from a function's docstring."""
        doc = inspect.getdoc(func)
        if not doc:
            return cls()

        lines = doc.strip().split("\n")

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
                content = section_match.group(2).strip()
                if current_section != section_name:
                    current_section = section_name
                    sections.setdefault(current_section, [])
                if content:
                    sections[current_section].append(content)
                continue

            sections[current_section].append(line.strip())

        for k, v in sections.items():
            sections[k] = "\n".join(v)
        return cls(**sections, module=func.__module__)

    @property
    def description(self) -> str:
        return self.meta.get("description", "").strip()

    @property
    def examples(self) -> list[str]:
        if examples := self.meta.get("examples"):
            return [_ for ex in examples.split("\n\n") if (_ := ex.strip())]
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
            filter(lambda x: x.strip(),
                   self.meta.get("usage", "").splitlines()))

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
        inner = {"cmd": self._meta.get("name"), "cmdhelp": self.CMD_HELP}
        inner = dict(filter(lambda x: x[1], inner.items()))

        def sub(m):
            try:
                return str(eval(m.group(1), globals_ | inner))
            except Exception as e:
                return m.group(0)

        return {
            k: re.sub(r"\{(.+?)\}", sub, v)
            for k, v in self._meta.items() if isinstance(v, str)
        }

    def export_markdown(self) -> str:
        """Export the metadata to a markdown format."""
        parts = [
            f"## {self.name}",
            self.description,
        ]
        if (_ := self.special) and (sp := _.strip()):
            parts.append(f"> *{sp}*")
        if self.usage:
            tbl = [["输入", "描述"], ["---", "---"]]
            norm = []
            for line in self.usage:
                tokens = line.split(" - ", 1)
                if len(tokens) > 1:
                    tbl.append([_.strip() for _ in tokens])
                else:
                    norm.append(line.strip())
            parts.append("### 用法")
            if len(tbl) > 2:
                escape = lambda x: x.replace("|", "\\|")
                tbl_str = "\n".join(f"|{'|'.join(escape(_) for _ in row)}|"
                                    for row in tbl)
                parts.append(tbl_str)
            if norm:
                bullet = "\n".join(f"- {line}" for line in norm)
                parts.append(bullet)
        if self.examples:
            parts.append("### 示例")
            for example in self.examples:
                parts.append(f"```plaintext\n{example}\n```")
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
