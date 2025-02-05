from typing import Iterable

from .command import CommandCategory, CommandMeta


class DocManager:
    """Manages the documentation for bot."""

    _commands: dict[str, CommandMeta] = {}

    @classmethod
    def register(cls,
                 name: str,
                 category: CommandCategory,
                 aliases: Iterable[str] = (),
                 visible_in_overview: bool = True):

        def decorator(fn):
            meta = CommandMeta.parse(fn)
            meta.name = name
            meta.category = category
            meta.aliases = set(aliases)
            meta.visible_in_overview = visible_in_overview
            cls._commands[name] = meta
            for alias in aliases:
                cls._commands[alias] = meta
            return fn

        return decorator

    @classmethod
    def get(cls, name: str) -> CommandMeta | None:
        return cls._commands.get(name)

    @classmethod
    def iter_doc(cls):
        for cmd in cls._commands.values():
            yield cmd


command_doc = DocManager.register
