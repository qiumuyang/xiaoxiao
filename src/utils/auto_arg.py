import argparse
from typing import (Callable, Generic, Protocol, Type, TypeVar,
                    runtime_checkable)


@runtime_checkable
class SupportsComparison(Protocol):

    def __lt__(self, other: object) -> bool:
        ...

    def __gt__(self, other: object) -> bool:
        ...


T = TypeVar("T")


class Argument(Generic[T]):
    """A class to represent an argument that will be parsed from the command line.

    Args:
        default:
            The default value of the argument.
            Type will be inferred from it.
        range:
            A tuple of two values [min, max] that the argument must be in.
            If specified, the argument must support comparison operations.
        choices:
            A list of valid choices for the argument.
        validate:
            A custom validation function that checks if the argument is valid.
        positional:
            Whether the argument can be a positional argument.
            If True, the argument can be parsed both as a positional and an
            optional argument. If specified twice, the last value will be used.
            *Note that if the last value fails validation, the default value
            will be used even if the first appearance is valid.
    """

    def __init__(
        self,
        default: T,
        *,
        range: tuple[T | None, T | None] = (None, None),
        choices: list[T] | None = None,
        validate: Callable[[T], bool] | None = None,
        positional: bool = False,
        doc: str = "",
    ):
        self._default = default
        self._range = range
        self._choices = choices
        self._validate = validate
        self._positional = positional
        self._doc = doc

    @property
    def doc(self) -> str:
        return " || ".join([self._doc, self.requirements])

    @property
    def requirements(self) -> str:
        if self._range[0] is not None or self._range[1] is not None:
            if self._range[0] is not None and self._range[1] is not None:
                return f"[{self._range[0]}, {self._range[1]}]"
            if self._range[0] is not None:
                return f"[{self._range[0]}, ∞)"
            if self._range[1] is not None:
                return f"(-∞, {self._range[1]}]"
        if self._choices is not None:
            return f"{' | '.join(map(str, self._choices))}"
        return ""

    @property
    def default(self) -> T:
        return self._default

    @property
    def positional(self) -> bool:
        return self._positional

    def get_type(self):
        return type(self._default)

    def check(self, value: T) -> tuple[bool, T | None]:
        if (self._range[0] or self._range[1]) is not None:
            if not isinstance(value, SupportsComparison):
                raise ValueError(
                    f"Value must support comparison operations: {value}")
            if self._range[0] is not None and value < self._range[0]:
                return False, self._range[0]
            if self._range[1] is not None and value > self._range[1]:
                return False, self._range[1]
        if self._choices is not None and value not in self._choices:
            return False, None
        if self._validate is not None and not self._validate(value):
            return False, None
        return True, None

    def parser_type(self, value: str, raise_error: bool = False) -> T:
        type_ = self.get_type()
        value_ = type_(value)  # type: ignore
        valid, new_value = self.check(value_)
        if not valid:
            if raise_error:
                raise ValueError(f"Invalid value: {value}")
            return new_value if new_value is not None else self._default
        return value_


class AutoArgumentParserMixin:

    @classmethod
    def add_arguments(cls, parser: "AutoArgumentParser"):
        for var_name, var_value in cls.__dict__.items():
            if isinstance(var_value, Argument):
                arg_type = var_value.get_type()
                dash_name = var_name.replace("_", "-")
                arg = f"--{dash_name}"
                if arg_type == bool:
                    # bool cannot be positional
                    if var_value.positional:
                        raise ValueError(
                            f"Cannot have positional argument of type bool: "
                            f"{dash_name}")
                    if var_value.default:
                        arg = f"--no-{dash_name}"
                        parser.add_argument(f"--no-{dash_name}",
                                            action="store_false",
                                            dest=var_name,
                                            default=var_value.default)
                    else:
                        parser.add_argument(f"--{dash_name}",
                                            action="store_true",
                                            default=var_value.default)
                else:
                    action = parser.add_argument(f"--{dash_name}",
                                                 type=var_value.parser_type,
                                                 default=var_value.default)
                    if var_value.positional:
                        parser.add_argument(action.dest,
                                            type=var_value.parser_type,
                                            nargs="?",
                                            default=var_value.default)
                # store documentation
                if not hasattr(parser, "argument_document"):
                    parser.argument_document = {}
                parser.argument_document[arg] = var_value.doc


class AutoArgumentParser(argparse.ArgumentParser):

    argument_document: dict[str, str]

    @classmethod
    def from_class(cls, target_class: Type[AutoArgumentParserMixin]):
        parser = cls(exit_on_error=False, add_help=False)

        if not issubclass(target_class, AutoArgumentParserMixin):
            raise ValueError("Must be a subclass of AutoArgumentParserMixin")

        target_class.add_arguments(parser)
        return parser

    def parse_args(self, args=None, namespace=None):  # type: ignore
        try:
            args, _ = super().parse_known_args(args, namespace)
        except:
            args = argparse.Namespace(
                **{action.dest: action.default
                   for action in self._actions})
        # use default values for missing arguments
        for action in self._actions:
            if not hasattr(args, action.dest):
                setattr(args, action.dest, action.default)
        return args

    @property
    def dests(self) -> set[str]:
        return {action.dest for action in self._actions}

    def format_args(self) -> str:
        lines = []
        for arg, desc in getattr(self, "argument_document", {}).items():
            lines.append(f":param {arg}: {desc}")
        return "\n".join(lines)

    def format_example(self) -> str:
        parts = []
        for action in self._actions:
            if action.option_strings and action.default is not argparse.SUPPRESS:
                name = action.option_strings[0]
                default = action.default
                if isinstance(default, bool):
                    parts.append(f"[{name}]")
                else:
                    parts.append(f"{name}={default}")
        return " ".join(parts)
