import textwrap
from datetime import datetime

from PIL import Image as PILImage

from src.utils.image.avatar import Avatar
from src.utils.render import *

from .config import RenderBackground
from .fortune import Fortune, get_sunrise_sunset


class FortuneRender:

    LOC = {"latitude": 32, "longitude": 118}
    _cache_date = datetime.now()

    GOOD_EVENT_COLOR = (255, 219, 66)
    BAD_EVENT_COLOR = (90, 138, 189)
    GOOD_FORTUNE_COLOR = (204, 0, 0)
    BAD_FORTUNE_COLOR = (52, 88, 129)

    SZ = 120
    AVATAR_RATIO = 0.9
    AVATAR_RADIUS_D = 8
    AVATAR_BORDER_D = 40
    AVATAR_SPACE_D = 8
    FORTUNE_RATIO = 0.75
    FORTUNE_ASPECT = 0.45
    FORTUNE_RADIUS_D = 16
    FORTUNE_SPACE_D = 8
    EVENT_EXPAND = 1.5
    EVENT_RADIUS_D = 32
    EVENT_ASPECT = 4 / EVENT_EXPAND
    FONT_SMALL = 18
    FONT_MEDIUM = 28
    FONT_EVENT = 22
    FONT_LARGE = 40
    EMOJI_CORRECTION = 0.85
    VSPACE = 8

    NotoSansHansBold = "data/static/fonts/NotoSansHans-Bold.otf"
    NotoSansHansMedium = "data/static/fonts/NotoSansHans-Medium.otf"
    SegUIEmoji = "data/static/fonts/seguiemj.ttf"
    STLiti = "data/static/fonts/STLITI.TTF"

    text_template = textwrap.dedent("""
        <date>■  {date}</date>
        <luck>■  今天的幸运色是 {lucky_color}</luck>
        """).strip()

    @classmethod
    def text_style(
        cls,
        theme_dark: Color,
        theme_light: Color,
        lucky_color: Color,
    ) -> dict[str, TextStyle]:
        return {
            "luck":
            TextStyle.of(font=cls.NotoSansHansMedium,
                         size=cls.FONT_SMALL,
                         color=lucky_color),
            "date":
            TextStyle.of(font=cls.NotoSansHansMedium,
                         size=cls.FONT_SMALL,
                         color=theme_light),
        }

    @classmethod
    def render_event_row(
        cls,
        width: int,
        is_good: bool,
        events: list[str],
        is_dark: bool = False,
    ) -> RenderObject:
        """Use a darker color for the event if the background is dark."""
        color = cls.GOOD_EVENT_COLOR if is_good else cls.BAD_EVENT_COLOR
        if is_dark:
            color = Palette.blend(Color.of(*color), Palette.BLACK, 0.2)
        else:
            color = Color.of(*color)
        head = Text.of(text="宜" if is_good else "忌",
                       font=cls.NotoSansHansMedium,
                       size=cls.FONT_EVENT,
                       color=Palette.WHITE)
        event_height = round(cls.FONT_EVENT * cls.EVENT_EXPAND)
        head = FixedContainer.from_children(
            children=[head],
            width=event_height,
            height=event_height,
            justify_content=JustifyContent.CENTER,
            alignment=Alignment.CENTER,
            background=color,
            decorations=Decorations.of().final(
                RectCrop.of(border_radius=cls.SZ // cls.EVENT_RADIUS_D)))
        event_width = round(event_height * cls.EVENT_ASPECT)
        event_objects = [
            FixedContainer.from_children(
                children=[
                    Text.of(text=event,
                            font=cls.NotoSansHansMedium,
                            size=cls.FONT_EVENT,
                            color=Palette.WHITE)
                ],
                width=event_width,
                height=event_height,
                justify_content=JustifyContent.CENTER,
                alignment=Alignment.CENTER,
                background=color,
                decorations=Decorations.of().final(
                    RectCrop.of(border_radius=cls.SZ // cls.EVENT_RADIUS_D)))
            for event in events
        ]
        children = [head] + event_objects
        space = (width - sum([c.width
                              for c in children])) // (len(children) - 1)
        return Image.from_image(
            RenderImage.concat_horizontal([c.render() for c in children],
                                          alignment=Alignment.CENTER,
                                          spacing=space))

    @classmethod
    def render_username(
        cls,
        username: str,
        max_name_width: int,
        max_name_height: int,
        theme_light: Color,
        theme_dark: Color,
    ) -> RenderObject:
        styled_parts = []
        for text, support in Text.split_font_unsupported(
                cls.NotoSansHansBold, username):
            # let's assume unsupported characters are all emojis
            styled_parts.append(text if support else f"<emoji>{text}</emoji>")
        max_name_size = (max_name_width, max_name_height)
        shared_kw = dict(
            text="".join(styled_parts),
            styles={
                "emoji":
                TextStyle.of(font=cls.SegUIEmoji,
                             size=cls.EMOJI_CORRECTION,
                             stroke_width=0,
                             embedded_color=True,
                             ymin_correction=True),
            },
            default=TextStyle.of(
                font=cls.NotoSansHansBold,
                size=0,
                color=theme_light,
                stroke_color=theme_dark,
                stroke_width=1,
            ),
        )
        font_size = StyledText.get_max_fitting_font_size(
            font_size_range=(cls.FONT_LARGE // 4, cls.FONT_LARGE),
            max_size=max_name_size,
            **shared_kw)  # type: ignore
        shared_kw["default"].size = font_size  # type: ignore
        return StyledText.of(max_width=max_name_width,
                             **shared_kw)  # type: ignore

    @classmethod
    def is_dark_by_sunrise_sunset(cls) -> bool:
        now = datetime.now()
        if now.day != cls._cache_date.day:
            cls._cache_date = now
            get_sunrise_sunset.cache_clear()
        sunrise, sunset = get_sunrise_sunset(**cls.LOC)
        return not sunrise < now < sunset

    @classmethod
    async def render(
        cls,
        fortune: Fortune,
        background: RenderBackground = RenderBackground.WHITE,
    ) -> PILImage.Image:
        raw_avatar = await Avatar.user(fortune["user_id"])
        avatar_sz = round(cls.SZ * cls.AVATAR_RATIO)

        match background:
            case RenderBackground.AUTO:
                is_dark = cls.is_dark_by_sunrise_sunset()
                bg_color = Palette.BLACK if is_dark else Palette.WHITE
            case RenderBackground.WHITE:
                is_dark = False
                bg_color = Palette.WHITE
            case RenderBackground.BLACK:
                is_dark = True
                bg_color = Palette.BLACK
            case RenderBackground.TRANSPARENT:
                is_dark = False
                bg_color = Palette.TRANSPARENT

        theme = Palette.dominant(raw_avatar)
        theme_light = Palette.blend(theme, Palette.WHITE, 0.3)
        theme_dark = Palette.blend(theme, Palette.BLACK, 0.2)

        # upper part: avatar, name, date, lucky color
        border = avatar_sz // cls.AVATAR_BORDER_D
        radius = avatar_sz // cls.AVATAR_RADIUS_D
        radius_outer = radius + border

        avatar_im = Image.from_image(
            raw_avatar.resize((avatar_sz, avatar_sz)),
            decorations=[RectCrop.of_square(border_radius=radius)],
        )
        avatar_bg = Image.from_color(
            width=avatar_sz + 2 * border,
            height=avatar_sz + 2 * border,
            color=theme_dark,
            decorations=Decorations.of(
                RectCrop.of_square(border_radius=radius_outer)),
        )
        avatar = Stack.from_children([avatar_bg, avatar_im],
                                     alignment=Alignment.CENTER)

        lucky_color = Color.of(*fortune["lucky_color"])
        max_name_width = cls.SZ * 2
        max_name_height = cls.SZ // 2
        name_text = cls.render_username(fortune["user_name"], max_name_width,
                                        max_name_height, theme_light,
                                        theme_dark)
        if name_text.width < max_name_width:
            # pad at right
            name_text = Image.from_image(
                name_text.render(),
                margin=Space.of(0, max_name_width - name_text.width, 0, 0))
        desc_text = StyledText.of(
            text=cls.text_template.format(lucky_color=lucky_color.as_hex(),
                                          date=fortune["date"]),
            styles=cls.text_style(theme_dark, theme_light, lucky_color),
            default=TextStyle.of(),  # default style not used
            max_width=max_name_width,
            line_spacing=cls.FONT_MEDIUM // 4)

        avatar_space_r = cls.SZ // cls.AVATAR_SPACE_D
        avatar_offset = (avatar_space_r, 0)
        upper_container = RelativeContainer(padding=Space.vertical(cls.VSPACE))
        upper_container.add_child(avatar,
                                  align_top=upper_container,
                                  align_left=upper_container)
        upper_container.add_child(name_text,
                                  align_top=avatar,
                                  right=avatar,
                                  offset=avatar_offset)
        upper_container.add_child(desc_text,
                                  align_bottom=avatar,
                                  right=avatar,
                                  offset=avatar_offset)

        # lower part: fortune text & events texts
        is_good_fortune = "吉" in fortune["fortune"]
        fortune_color = cls.GOOD_FORTUNE_COLOR if is_good_fortune else cls.BAD_FORTUNE_COLOR
        fortune_text = Text.of(
            text=fortune["fortune"],
            font=cls.STLiti,
            size=cls.FONT_MEDIUM,
            color=Palette.WHITE,
            max_width=cls.FONT_MEDIUM,
            line_spacing=6,
        )
        fortune_text = FixedContainer.from_children(
            height=round(cls.SZ * cls.FORTUNE_RATIO),
            width=round(cls.SZ * cls.FORTUNE_ASPECT * cls.FORTUNE_RATIO),
            children=[fortune_text],
            justify_content=JustifyContent.CENTER,
            alignment=Alignment.CENTER,
            background=Color.of(*fortune_color),
            decorations=Decorations.of().final(
                RectCrop.of(border_radius=cls.SZ // cls.FORTUNE_RADIUS_D)))

        fortune_space = cls.SZ // cls.FORTUNE_SPACE_D
        event_offset = (fortune_space, 0)
        event_width = upper_container.width - fortune_text.width - fortune_space
        event_good = cls.render_event_row(event_width,
                                          True,
                                          fortune["event_good"],
                                          is_dark=is_dark)
        event_bad = cls.render_event_row(event_width,
                                         False,
                                         fortune["event_bad"],
                                         is_dark=is_dark)

        lower_container = RelativeContainer(padding=Space.vertical(cls.VSPACE))
        lower_container.add_child(fortune_text,
                                  align_top=lower_container,
                                  align_left=lower_container)
        lower_container.add_child(event_good,
                                  align_top=fortune_text,
                                  right=fortune_text,
                                  offset=event_offset)
        lower_container.add_child(event_bad,
                                  align_bottom=fortune_text,
                                  right=fortune_text,
                                  offset=event_offset)

        return Container.from_children(
            children=[
                upper_container,
                lower_container,
            ],
            padding=Space.of_side(15, 5),
            background=bg_color,
            direction=Direction.VERTICAL,
        ).render().to_pil()
