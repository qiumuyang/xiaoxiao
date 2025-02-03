import argparse
from typing import (Callable, Generic, Protocol, Type, TypeVar,
                    runtime_checkable)


@runtime_checkable
class SupportsComparison(Protocol):

    def __lt__(self, other: object) -> bool:
        ...

    def __ge__(self, other: object) -> bool:
        ...


T = TypeVar("T")


class Argument(Generic[T]):
    """A class to represent an argument that will be parsed from the command line.

    Args:
        default:
            The default value of the argument.
            Type will be inferred from it.
        range:
            A tuple of two values [min, max) that the argument must be in.
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
    ):
        self._default = default
        self._range = range
        self._choices = choices
        self._validate = validate
        self._positional = positional

    @property
    def default(self) -> T:
        return self._default

    @property
    def positional(self) -> bool:
        return self._positional

    def get_type(self):
        return type(self._default)

    def check(self, value: T) -> bool:
        if (self._range[0] or self._range[1]) is not None:
            if not isinstance(value, SupportsComparison):
                raise ValueError(
                    f"Value must support comparison operations: {value}")
            if self._range[0] is not None and value < self._range[0]:
                return False
            if self._range[1] is not None and value >= self._range[1]:
                return False
        if self._choices is not None and value not in self._choices:
            return False
        if self._validate is not None and not self._validate(value):
            return False
        return True

    def parser_type(self, value: str, raise_error: bool = False) -> T:
        type_ = self.get_type()
        value_ = type_(value)  # type: ignore
        if not self.check(value_):
            if raise_error:
                raise ValueError(f"Invalid value: {value}")
            return self.default
        return value_


class AutoArgumentParserMixin:

    @classmethod
    def add_arguments(cls, parser: "AutoArgumentParser"):
        for var_name, var_value in cls.__dict__.items():
            if isinstance(var_value, Argument):
                arg_type = var_value.get_type()
                var_name = var_name.replace("_", "-")
                if arg_type == bool:
                    # bool cannot be positional
                    parser.add_argument(f"--{var_name}",
                                        action="store_true",
                                        default=var_value.default)
                else:
                    action = parser.add_argument(f"--{var_name}",
                                                 type=var_value.parser_type,
                                                 default=var_value.default)
                    if var_value.positional:
                        parser.add_argument(action.dest,
                                            type=var_value.parser_type,
                                            nargs="?",
                                            default=var_value.default)


class AutoArgumentParser(argparse.ArgumentParser):

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
