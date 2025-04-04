import re
from string import Formatter
from typing import Any, Callable, Iterable

from typing_extensions import Self, Unpack, override

from ...base import (Alignment, BaseStyle, RenderImage, RenderObject,
                     TextStyle, cached, volatile)
from .layout import Element, LineBreaker, concat_elements_by_baseline
from .markup.generator import LayoutElementGenerator
from .markup.parser import MarkupParser


class CustomFormatter(Formatter):
    """Extended Formatter for

    - formatting lists of mappings (e.g., dictionaries)
    - escape formatted strings

    Format spec syntax:

        [separator]sub_format

        Use "\\]" to escape the closing square bracket.

    Example:

        formatter.format(
            "Users: {users:[, ]{{name}} ({{age}})",
            users=[
                {"name": "Alice", "age": 20},
                {"name": "Bob", "age": 25}
            ]
        )
    """

    _FORMAT_SPEC_REGEX = re.compile(r"^\[((?:[^\\\]]|\\.)*)\](.*)$", re.DOTALL)

    def __init__(self, escape: Callable[[str], str] = lambda x: x):
        Formatter.__init__(self)
        self.escape = escape

    def format_field(self, value: Any, format_spec: str) -> str:
        m = self._FORMAT_SPEC_REGEX.match(format_spec)
        if not m:
            # only escape when returning from parent
            default_result = Formatter.format_field(self, value, format_spec)
            return self.escape(default_result)

        separator_escaped, sub_format = m.groups()
        separator = separator_escaped.replace(r"\]", "]").replace(r"\\", "\\")

        # since self.format already escapes the raw values
        # we don't need to escape them here
        return separator.join(
            self.format(sub_format, **item) for item in value)


class Paragraph(RenderObject):

    formatter = CustomFormatter(MarkupParser.escape)

    @classmethod
    def escape(cls, text: str) -> str:
        """Expose the escape method of the MarkupParser class."""
        return MarkupParser.escape(text)

    def __init__(
        self,
        elements: Iterable[Element],
        max_width: int | None,
        alignment: Alignment,
        line_spacing: int | float,
        **kwargs: Unpack[BaseStyle],
    ):
        super().__init__(**kwargs)
        with volatile(self) as vlt:
            self.elements = vlt.list(elements)
            self.alignment = alignment
            self.line_spacing = line_spacing
            self.max_width = max_width

    @property
    @cached
    @override
    def content_width(self) -> int:
        return self.render_content().width

    @property
    @cached
    @override
    def content_height(self) -> int:
        return self.render_content().height

    @cached
    @override
    def render_content(self) -> RenderImage:
        line_breaker = LineBreaker(self.elements)
        rendered_lines: list[RenderImage] = []
        for line in line_breaker.break_lines(self.max_width):
            if not line:
                continue
            line_im = concat_elements_by_baseline(line)
            rendered_lines.append(line_im)
            if isinstance(self.line_spacing, int):
                rendered_lines.append(RenderImage.empty(0, self.line_spacing))
            else:
                line_spacing = round(line_im.height * self.line_spacing)
                rendered_lines.append(RenderImage.empty(0, line_spacing))
        if rendered_lines:
            rendered_lines.pop()  # remove last line spacing
        if not rendered_lines:
            return RenderImage.empty(0, 0)
        return RenderImage.concat_vertical(rendered_lines,
                                           alignment=self.alignment)

    @classmethod
    def of(cls,
           text: str,
           style: TextStyle,
           *,
           max_width: int | None = None,
           alignment: Alignment = Alignment.START,
           line_spacing: int | float = 0.25,
           **kwargs: Unpack[BaseStyle]) -> Self:
        return cls.from_template(MarkupParser.escape(text), {},
                                 max_width=max_width,
                                 alignment=alignment,
                                 line_spacing=line_spacing,
                                 default=style,
                                 **kwargs)

    @classmethod
    def from_markup(
        cls,
        markup: str,
        *,
        max_width: int | None = None,
        alignment: Alignment = Alignment.START,
        line_spacing: int | float = 0.25,
        default: TextStyle | None = None,
        styles: dict[str, TextStyle] | None = None,
        images: dict[str, RenderObject | RenderImage] | None = None,
        **kwargs: Unpack[BaseStyle],
    ) -> Self:
        """Create a Paragraph from a markup string with styles and images.

        Args:
            markup: Markup string (plain-text with HTML-like tags).
                Syntax:
                1. To apply text styles, use the format <tag-name>text</tag-name>.
                    Styles can be nested, with inner tags overriding outer ones.
                    If a required attribute is missing in an inner tag, the attribute
                    from the outer tag will be used, defaulting to the base style if needed.
                2. To insert inline images, use the self-closing tag format <image-name/>.
            default: Default / fallback text style.
            styles: Mapping of style names to text styles.
            images: Mapping of image names to images.
        """
        styles = styles or {}
        images = images or {}
        default = default or {}
        parser = MarkupParser(markup)
        generator = LayoutElementGenerator(parser.parse(),
                                           default=default,
                                           styles=styles,
                                           images=images,
                                           unescape=MarkupParser.unescape)
        return cls(generator.layout(), max_width, alignment, line_spacing,
                   **kwargs)

    @classmethod
    def from_template(
        cls,
        template: str,
        values: dict[str, Any],
        *,
        max_width: int | None = None,
        alignment: Alignment = Alignment.START,
        line_spacing: int | float = 0.25,
        default: TextStyle | None = None,
        styles: dict[str, TextStyle] | None = None,
        images: dict[str, RenderObject | RenderImage] | None = None,
        **kwargs: Unpack[BaseStyle],
    ) -> Self:
        """Create a Paragraph from a template string with placeholders.

        Note:
            This method is safer than `from_markup` since it automatically
            escapes the strings filled in the template.
        """
        return cls.from_markup(cls.formatter.format(template, **values),
                               max_width=max_width,
                               alignment=alignment,
                               line_spacing=line_spacing,
                               default=default,
                               styles=styles,
                               images=images,
                               **kwargs)

    @staticmethod
    def find_max_font(
        text: str,
        style: TextStyle,
        *,
        font_size: tuple[int, int],
        max_size: tuple[int, int],
        alignment: Alignment = Alignment.START,
        line_spacing: int | float = 0.25,
        **kwargs: Unpack[BaseStyle],
    ) -> int:
        return Paragraph.find_template_max_font(MarkupParser.escape(text), {},
                                                font_size=font_size,
                                                max_size=max_size,
                                                alignment=alignment,
                                                line_spacing=line_spacing,
                                                default=style,
                                                **kwargs)

    @staticmethod
    def _adjust_absolute_size(
        *styles: TextStyle,
        target_size: int,
    ) -> tuple[TextStyle, ...]:
        """Adjust font sizes in text styles in place.

        The method iterates through the styles and finds the first absolute font
        size. This size is used as the reference for subsequent font sizes.

        Args:
            *styles: The list of TextStyle objects to be processed.
            target_size: The target size to be used for absolute font sizes.

        Returns:
            The list of TextStyle objects with adjusted font sizes.
        """
        absolute = None
        for style in styles:
            if "size" not in style or isinstance(style["size"], float):
                continue
            if absolute is None:
                absolute = style["size"]
                style["size"] = target_size
            else:
                style["size"] = round(style["size"] / absolute * target_size)
        return styles

    @staticmethod
    def find_template_max_font(
        template: str,
        values: dict[str, Any],
        *,
        font_size: tuple[int, int],
        max_size: tuple[int, int],
        alignment: Alignment = Alignment.START,
        line_spacing: int | float = 0.25,
        default: TextStyle | None = None,
        styles: dict[str, TextStyle] | None = None,
        images: dict[str, RenderObject | RenderImage] | None = None,
        **kwargs: Unpack[BaseStyle],
    ) -> int:
        min, current_size = font_size
        max_width, max_height = max_size
        while current_size >= min:
            attempt_default = (default or {}).copy()
            attempt_styles = {k: v.copy() for k, v in (styles or {}).items()}
            Paragraph._adjust_absolute_size(attempt_default,
                                            *attempt_styles.values(),
                                            target_size=current_size)
            para = Paragraph.from_template(template,
                                           values,
                                           max_width=max_width,
                                           alignment=alignment,
                                           line_spacing=line_spacing,
                                           default=attempt_default,
                                           styles=attempt_styles,
                                           images=images,
                                           **kwargs)
            if para.height <= max_height:
                return current_size
            current_size -= 1
        raise ValueError(f"Cannot find fitting font size: "
                         f"min_font_size={min}")

    @classmethod
    def from_template_with_font_range(
        cls,
        template: str,
        values: dict[str, Any],
        max_size: tuple[int, int],
        font_size: tuple[int, int],
        *,
        alignment: Alignment = Alignment.START,
        line_spacing: int | float = 0.25,
        default: TextStyle | None = None,
        styles: dict[str, TextStyle] | None = None,
        images: dict[str, RenderObject | RenderImage] | None = None,
        **kwargs: Unpack[BaseStyle],
    ) -> Self:
        max_font_size = cls.find_template_max_font(template,
                                                   values,
                                                   font_size=font_size,
                                                   max_size=max_size,
                                                   alignment=alignment,
                                                   line_spacing=line_spacing,
                                                   default=default,
                                                   styles=styles,
                                                   images=images,
                                                   **kwargs)
        overwrite_default = (default or {}).copy()
        overwrite_styles = {k: v.copy() for k, v in (styles or {}).items()}
        Paragraph._adjust_absolute_size(overwrite_default,
                                        *overwrite_styles.values(),
                                        target_size=max_font_size)
        return cls.from_template(template,
                                 values,
                                 max_width=max_size[0],
                                 alignment=alignment,
                                 line_spacing=line_spacing,
                                 default=overwrite_default,
                                 styles=overwrite_styles,
                                 images=images,
                                 **kwargs)
