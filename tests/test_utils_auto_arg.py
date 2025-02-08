from argparse import Namespace

import pytest

from src.utils.auto_arg import (Argument, AutoArgumentParser,
                                AutoArgumentParserMixin)


class TestClassValid(AutoArgumentParserMixin):
    """测试用合法类，包含各种类型的参数"""
    int_arg = Argument(42, range=(0, 100))
    str_arg = Argument("default", choices=["a", "b", "default"])
    bool_arg = Argument(False)
    pos_arg = Argument("positional", positional=True)
    validated_arg = Argument(10, validate=lambda x: x % 2 == 0)


class TestClassInvalid:
    """不继承Mixin的测试类，用于测试类继承检查"""
    dummy = Argument(1)


class TestClassMixture(AutoArgumentParserMixin):
    """混合位置参数和可选参数的测试类"""
    pos_arg = Argument("positional", positional=True)
    pos_arg2 = Argument(100, choices=[100, 150, 200], positional=True)
    opt_arg = Argument("optional_default")
    bool_arg = Argument(True)


@pytest.fixture
def valid_parser() -> AutoArgumentParser:
    return AutoArgumentParser.from_class(TestClassValid)


@pytest.fixture
def mixture_parser() -> AutoArgumentParser:
    return AutoArgumentParser.from_class(TestClassMixture)


@pytest.fixture
def sample_args() -> list[str]:
    return ["--int-arg=50", "--str-arg=a", "--bool-arg", "custom_pos"]


def test_parser_creation(valid_parser: AutoArgumentParser):
    """测试解析器能正确创建"""
    assert isinstance(valid_parser, AutoArgumentParser)
    assert len(valid_parser._actions) >= 4  # 至少4个参数


def test_invalid_class_creation():
    """测试非Mixin子类创建解析器抛出异常"""
    with pytest.raises(ValueError):
        AutoArgumentParser.from_class(TestClassInvalid)  # type: ignore


class TestArgumentParsing:
    """测试参数解析的核心功能"""

    def test_default_values(self, valid_parser: AutoArgumentParser):
        """测试默认值正确应用"""
        args = valid_parser.parse_args([])
        assert args.int_arg == 42
        assert args.str_arg == "default"
        assert args.bool_arg is False
        assert args.pos_arg == "positional"

    def test_positional_arg_override(self, valid_parser: AutoArgumentParser):
        """测试位置参数覆盖可选参数"""
        args = valid_parser.parse_args(
            ["--pos-arg=optional", "positional_val"])
        assert args.pos_arg == "positional_val"

    def test_bool_arg_parsing(self, valid_parser: AutoArgumentParser):
        """测试布尔参数正确解析"""
        args = valid_parser.parse_args(["--bool-arg"])
        assert args.bool_arg is True

    def test_type_conversion(self, valid_parser: AutoArgumentParser):
        """测试类型转换逻辑"""
        args = valid_parser.parse_args(["--int-arg=23"])
        assert isinstance(args.int_arg, int)
        assert args.int_arg == 23


class TestValidationLogic:
    """测试参数验证逻辑"""

    def test_range_validation(self, valid_parser: AutoArgumentParser):
        """测试范围约束"""
        # 低于最小值
        args = valid_parser.parse_args(["--int-arg=-10"])
        assert args.int_arg == 0  # use lower bound
        # 在范围内
        args = valid_parser.parse_args(["--int-arg=50"])
        assert args.int_arg == 50
        # 超过最大值
        args = valid_parser.parse_args(["--int-arg=150"])
        assert args.int_arg == 100  # use upper bound

    def test_choices_validation(self, valid_parser: AutoArgumentParser):
        """测试选项约束"""
        # 有效选项
        args = valid_parser.parse_args(["--str-arg=a"])
        assert args.str_arg == "a"
        # 无效选项
        args = valid_parser.parse_args(["--str-arg=invalid"])
        assert args.str_arg == "default"

    def test_custom_validation(self, valid_parser: AutoArgumentParser):
        """测试自定义验证函数"""
        # 有效值
        args = valid_parser.parse_args(["--validated-arg=20"])
        assert args.validated_arg == 20
        # 无效值
        args = valid_parser.parse_args(["--validated-arg=15"])
        assert args.validated_arg == 10  # 返回默认值


def test_mixed_arguments(valid_parser: AutoArgumentParser,
                         sample_args: list[str]):
    """测试混合参数解析"""
    args = valid_parser.parse_args(sample_args)
    assert args == Namespace(
        int_arg=50,
        str_arg="a",
        bool_arg=True,
        pos_arg="custom_pos",
        validated_arg=10  # 未指定时使用默认值
    )


def test_argument_dest_names(valid_parser: AutoArgumentParser):
    """测试参数dest名称正确生成"""
    dests = valid_parser.dests
    assert dests == {
        "int_arg",
        "str_arg",
        "bool_arg",
        "pos_arg",
        "validated_arg",
    }


class TestPositionalWithOptional:
    """新增的测试类，完全独立于原有测试"""

    def test_multiple_positional_with_optional(
            self, mixture_parser: AutoArgumentParser):
        args = mixture_parser.parse_args(
            ["--pos-arg2=999", "pos1_value", "200"])
        # 验证扩展类的新参数
        assert args.pos_arg == "pos1_value"
        assert args.pos_arg2 == 200
        assert args.opt_arg == "optional_default"
        args = mixture_parser.parse_args(
            ["--pos-arg2=200", "pos1_value", "999"])
        assert args.pos_arg == "pos1_value"
        # Be careful with this: fallback to default value
        #                       even if the first appearance is valid
        assert args.pos_arg2 == 100
        assert args.opt_arg == "optional_default"

    def test_argument_order_priority(self, mixture_parser: AutoArgumentParser):
        # 测试覆盖顺序 (后定义的参数覆盖先定义的参数)
        args1 = mixture_parser.parse_args(["--pos-arg=opt_val", "pos_val"])
        assert args1.pos_arg == "pos_val"
        args2 = mixture_parser.parse_args(
            ["pos_val_first", "--pos-arg=opt_val"])
        assert args2.pos_arg == "opt_val"

    def test_insufficient_positional_args(self,
                                          mixture_parser: AutoArgumentParser):
        args = mixture_parser.parse_args(["only_pos1"])
        # 验证原有参数和新参数
        assert args.pos_arg == "only_pos1"  # 来自原有类
        assert args.pos_arg2 == 100  # 新参数默认值

    def test_default_true_bool(self, mixture_parser: AutoArgumentParser):
        args = mixture_parser.parse_args(["--no-bool-arg"])
        assert args.bool_arg is False
