from typing import Iterable

from .command import CommandCategory, CommandMeta, CommandOverview


class DocManager:
    """Manages the documentation for bot."""

    _commands: dict[str, CommandMeta] = {}
    _aliases: dict[str, str] = {}

    @classmethod
    def register(cls,
                 name: str,
                 category: CommandCategory,
                 aliases: Iterable[str] = (),
                 visible_in_overview: bool = True,
                 is_command_group: bool = False):

        def decorator(fn):
            meta = CommandMeta.parse(fn)
            meta.name = name
            meta.category = category
            meta.aliases = set(aliases)
            meta.visible_in_overview = visible_in_overview
            meta.is_command_group = is_command_group
            cls._commands[name] = meta
            for alias in aliases:
                cls._aliases[alias] = name
            return fn

        return decorator

    @classmethod
    def get(cls, name: str) -> CommandMeta | None:
        name = cls._aliases.get(name, name)
        return cls._commands.get(name)

    @classmethod
    def iter_doc(cls):
        for cmd in cls._commands.values():
            yield cmd

    @classmethod
    def export_overview(cls) -> str:
        return CommandOverview(cls._commands).export_markdown()


command_doc = DocManager.register
