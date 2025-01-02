import string
from enum import Enum
from functools import lru_cache
from typing import TypedDict

from src.utils.image.avatar import Avatar
from src.utils.render import *

from ..data import Diff, IdiomItem
from .data import MAX_GUESS


class RenderAttemptData(TypedDict):
    user_id: int
    syllables: list[str]
    diffs: list[Diff]


class Status(Enum):
    MISS = 0
    EXACT = 1
    EXIST = 2
    TODO = -1

    @classmethod
    def from_diff(cls, diff: Diff) -> "Status":
        if diff == Diff.MISS:
            return cls.MISS
        if diff == Diff.EXACT:
            return cls.EXACT
        if diff == Diff.EXIST:
            return cls.EXIST


class Alphabet:

    MS_YAHEI = "data/static/fonts/MSYAHEI.ttc"

    THEME = {
        Status.EXACT: {
            "background": Color.of(56, 161, 105),
            "foreground": Palette.WHITE.with_alpha(200),
        },
        Status.MISS: {
            "background": Color.of(113, 128, 150),
            "foreground": Palette.WHITE.with_alpha(200),
        },
        Status.EXIST: {
            "background": Color.of(214, 158, 46),
            "foreground": Palette.WHITE.with_alpha(200),
        },
        Status.TODO: {
            "background": Color.of(237, 242, 247),
            "foreground": Palette.BLACK.with_alpha(200),
        },
    }

    @classmethod
    @lru_cache()
    def render(
        cls,
        character: str,
        *,
        font_size: int,
        fixed_size: tuple[int, int],
        background: Color,
        foreground: Color,
        rounded_border: bool = False,
    ) -> RenderObject:
        if not character.strip():
            inner_object = Spacer.of()
        else:
            inner_object = Text.of(text=character.upper(),
                                   font=cls.MS_YAHEI,
                                   size=font_size,
                                   color=foreground)
        decorations = tuple()
        style = {}
        if rounded_border:
            decorations = Decorations.of().after_padding(
                RectCrop.of(border_radius=fixed_size[0] // 8))
        return FixedContainer.from_children(
            width=fixed_size[0],
            height=fixed_size[1],
            children=[inner_object],
            justify_content=JustifyContent.CENTER,
            alignment=Alignment.CENTER,
            background=background,
            decorations=decorations,
            **style,
        )


class Keyboard:

    KEYS = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]

    FIXED_SIZE = (36, 50)
    FONT_SIZE = 20

    HSPACE = 11
    VSPACE = 4

    @classmethod
    def init(cls):
        """Cache all renderable objects."""
        for status in Status:
            for character in string.ascii_uppercase:
                Alphabet.render(
                    character,
                    font_size=cls.FONT_SIZE,
                    fixed_size=cls.FIXED_SIZE,
                    background=Alphabet.THEME[status]["background"],
                    foreground=Alphabet.THEME[status]["foreground"],
                    rounded_border=True,
                )

    @classmethod
    def render(cls, key_state: dict[str, Status]) -> RenderObject:
        rows = []
        for row in cls.KEYS:
            row_objects = []
            for character in row:
                status = key_state.get(character.lower(), Status.TODO)
                row_objects.append(
                    Alphabet.render(
                        character,
                        font_size=cls.FONT_SIZE,
                        fixed_size=cls.FIXED_SIZE,
                        background=Alphabet.THEME[status]["background"],
                        foreground=Alphabet.THEME[status]["foreground"],
                        rounded_border=True,
                    ))
            rows.append(
                Container.from_children(
                    children=row_objects,
                    alignment=Alignment.CENTER,
                    direction=Direction.HORIZONTAL,
                    spacing=cls.HSPACE,
                ))
        return Container.from_children(
            children=rows,
            alignment=Alignment.CENTER,
            direction=Direction.VERTICAL,
            spacing=cls.VSPACE,
        )


class GuessAttempt:

    FIXED_SIZE = (40, 60)
    FONT_SIZE = 36
    AVATAR_SIZE = (20, 20)

    HSPACE = 2
    VSPACE = 10
    SYLLABLE_SPACE = 20

    @classmethod
    def init(cls):
        """Cache all renderable objects."""
        for status in Status:
            for character in string.ascii_uppercase + " ":
                Alphabet.render(
                    character,
                    font_size=cls.FONT_SIZE,
                    fixed_size=cls.FIXED_SIZE,
                    background=Alphabet.THEME[status]["background"],
                    foreground=Alphabet.THEME[status]["foreground"],
                    rounded_border=False,
                )

    @classmethod
    async def render_attempt(cls, user_id: int, syllables: list[str],
                             diff: list[Diff]) -> RenderObject:
        avatar = await Avatar.user(user_id)
        objects: list[RenderObject] = [
            Image.from_image(avatar.resize(cls.AVATAR_SIZE))
        ]
        s = 0
        for syllable in syllables:
            for character in syllable:
                status = Status.from_diff(diff[s])
                s += 1
                char = Alphabet.render(
                    character,
                    font_size=cls.FONT_SIZE,
                    fixed_size=cls.FIXED_SIZE,
                    background=Alphabet.THEME[status]["background"],
                    foreground=Alphabet.THEME[status]["foreground"],
                    rounded_border=False,
                )
                objects.append(char)
            objects.append(Spacer.of(width=cls.SYLLABLE_SPACE -
                                     2 * cls.HSPACE))
        if objects:
            objects.pop()  # remove the last spacer
        return Container.from_children(
            children=objects,
            alignment=Alignment.CENTER,
            direction=Direction.HORIZONTAL,
            spacing=cls.HSPACE,
        )

    @classmethod
    async def render_placeholder(cls, syllables: list[int]) -> RenderObject:
        objects: list[RenderObject] = [Spacer.of(width=cls.AVATAR_SIZE[0])]
        for syllable in syllables:
            for _ in range(syllable):
                char = Alphabet.render(
                    "",
                    font_size=cls.FONT_SIZE,
                    fixed_size=cls.FIXED_SIZE,
                    background=Alphabet.THEME[Status.TODO]["background"],
                    foreground=Alphabet.THEME[Status.TODO]["foreground"],
                    rounded_border=False,
                )
                objects.append(char)
            objects.append(Spacer.of(width=cls.SYLLABLE_SPACE -
                                     2 * cls.HSPACE))
        if objects:
            objects.pop()
        return Container.from_children(
            children=objects,
            alignment=Alignment.CENTER,
            direction=Direction.HORIZONTAL,
            spacing=cls.HSPACE,
        )

    @classmethod
    async def render(
        cls,
        attempts: list[RenderAttemptData],
        syllables: list[int],
    ) -> RenderObject:
        objects = []
        for attempt in attempts:
            objects.append(await cls.render_attempt(attempt["user_id"],
                                                    attempt["syllables"],
                                                    attempt["diffs"]))
        for _ in range(MAX_GUESS - len(attempts)):
            objects.append(await cls.render_placeholder(syllables))
        return Container.from_children(
            children=objects,
            alignment=Alignment.CENTER,
            direction=Direction.VERTICAL,
            spacing=cls.VSPACE,
        )


class IdiomRender:

    STLITI = "data/static/fonts/STLITI.TTF"
    STKAITI = "data/static/fonts/STKAITI.TTF"
    MS_YAHEI = "data/static/fonts/MSYAHEI.ttc"

    WORD = TextStyle.of(font=STLITI, size=40)
    PINYIN = TextStyle.of(font=MS_YAHEI,
                          size=24,
                          decoration=TextDecoration.UNDERLINE)
    DETAIL = TextStyle.of(font=STKAITI, size=24)
    DEFAULT = TextStyle.of(font=MS_YAHEI, size=24, color=Palette.BLACK)

    TEXT_STYLE = {
        "w": WORD,
        "p": PINYIN,
        "d": DETAIL,
        "default": DEFAULT,
    }
    TEMPLATE_CENTER = ("<w>{word}</w>\n"
                       "<p>{pinyin}</p>\n")
    TEMPLATE_LEFT = ("<d>{explanation}</d>\n"
                     "<d>{derivation}</d>\n")

    @classmethod
    def render(cls, idiom: IdiomItem, max_width: int | None) -> RenderObject:
        pinyin = " ".join(idiom["pinyin_tone"])
        explanation = idiom["explanation"].strip()
        derivation = idiom["derivation"].strip()
        if explanation:
            explanation = "释义：" + explanation
        if derivation:
            derivation = "出处：" + derivation
        text_c = cls.TEMPLATE_CENTER.format(word=idiom["word"], pinyin=pinyin)
        text_l = cls.TEMPLATE_LEFT.format(explanation=explanation,
                                          derivation=derivation).replace(
                                              "<d></d>", "")
        sc = StyledText.of(text=text_c,
                           styles=cls.TEXT_STYLE,
                           max_width=max_width,
                           alignment=Alignment.CENTER)
        sl = StyledText.of(text=text_l,
                           styles=cls.TEXT_STYLE,
                           max_width=max_width,
                           alignment=Alignment.START)
        return Container.from_children(
            children=[sc, sl],
            alignment=Alignment.CENTER,
            direction=Direction.VERTICAL,
        )


class GuessRender:

    KEYBOARD_SPACE = 20
    ANSWER_SPACE = 20
    MARGIN = 15
    BACKGROUND = Palette.WHITE

    @classmethod
    async def render(
        cls,
        attempts: list[RenderAttemptData],
        syllables: list[int],
        key_state: dict[str, Status] | None = None,
        answer: IdiomItem | None = None,
    ) -> RenderObject:
        attempt = await GuessAttempt.render(attempts, syllables)
        objects = [attempt]
        if key_state is not None:
            keyboard = Keyboard.render(key_state)
            objects.extend([Spacer.of(height=cls.KEYBOARD_SPACE), keyboard])
        if answer is not None:
            detail = IdiomRender.render(answer, max_width=attempt.width)
            objects.extend([Spacer.of(height=cls.ANSWER_SPACE), detail])
        return Container.from_children(
            children=objects,
            alignment=Alignment.CENTER,
            direction=Direction.VERTICAL,
            padding=Space.all(cls.MARGIN),
            background=cls.BACKGROUND,
        )


GuessAttempt.init()
Keyboard.init()

__all__ = [
    "GuessAttempt",
    "GuessRender",
    "Keyboard",
    "RenderAttemptData",
]
