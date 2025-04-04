from dataclasses import dataclass
from typing import NewType

from ...utils import Flex, PathLike


@dataclass(frozen=True)
class FontFamily:
    """Font family with regular, bold, italic, and bold italic fonts.

    Attributes:
        baseline_correction (int | bool):
            baseline calculated by ascender is not always correct.
            If True, use yMin in font metrics for baseline correction.
            If int, use the specified value for baseline correction.
        shear (float):
            Factor for simulating italic text.
        thickness (float):
            Factor multiplied with height for text decoration line thickness.
        fallbacks (list[FontFamily] | None):
            List of fallback fonts when a glyph is not supported.
        scale (float, only for fallback):
            The scale of the fallback font relative to the primary font.
    """
    regular: PathLike
    bold: PathLike
    italic: PathLike | None = None
    bold_italic: PathLike | None = None
    baseline_correction: int | bool = False
    embedded_color: bool = False
    shear: float = 0.2
    thickness: float = 0.08
    fallbacks: list["FontFamily"] | None = None
    scale: float = 1

    @classmethod
    def of(
        cls,
        *,
        regular: PathLike,
        bold: PathLike | None = None,
        italic: PathLike | None = None,
        bold_italic: PathLike | None = None,
        embedded_color: bool = False,
        baseline_correction: int | bool = False,
        shear: float = 0.2,
        thickness: float = 0.08,
        fallbacks: Flex["str | FontFamily"] | None = None,
        scale: float = 1,
    ) -> "FontFamily":
        """
        If bold not specified, use regular font as bold font.
        If italic not specified, text will be sheared to simulate italic.
        """
        fallbacks = fallbacks or []
        if not isinstance(fallbacks, list):
            fallbacks = [fallbacks]
        return cls(
            regular,
            bold or regular,
            italic,
            bold_italic,
            baseline_correction=baseline_correction,
            embedded_color=embedded_color,
            shear=shear,
            thickness=thickness,
            fallbacks=[
                f if isinstance(f, FontFamily) else FontFamily.of(regular=f)
                for f in fallbacks
            ],
            scale=scale)

    def resolve(self, bold: bool, italic: bool) -> tuple[str, bool]:
        """Retrieves the appropriate font variant based on bold and italic flags.

        Returns:
            (str, bool):
                The selected font and whether italic needs to be simulated.
        """
        if bold and italic:
            return str(self.bold_italic or self.bold), self.bold_italic is None
        if bold:
            return str(self.bold), False
        if italic:
            return str(self.italic or self.regular), self.italic is None
        return str(self.regular), False


RelativeSize = NewType("RelativeSize", float)
AbsoluteSize = NewType("AbsoluteSize", int)
