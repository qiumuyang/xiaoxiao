import textwrap

from PIL import Image as PILImage

from src.utils.image.avatar import Avatar
from src.utils.render import *

from .config import RenderBackground
from .fortune import Fortune


class FortuneRender:

    GOOD_EVENT_COLOR = (255, 219, 66)
    BAD_EVENT_COLOR = (90, 138, 189)
    GOOD_FORTUNE_COLOR = (204, 0, 0)
    BAD_FORTUNE_COLOR = (52, 88, 129)

    BG_COLOR_MAPPING = {
        RenderBackground.WHITE: Palette.WHITE,
        RenderBackground.BLACK: Palette.BLACK,
        RenderBackground.TRANSPARENT: Palette.TRANSPARENT,
    }

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
    VSPACE = 8

    NotoSansHansBold = "data/static/fonts/NotoSansHans-Bold.otf"
    NotoSansHansMedium = "data/static/fonts/NotoSansHans-Medium.otf"
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
    async def render(
        cls,
        fortune: Fortune,
        background: RenderBackground = RenderBackground.WHITE,
    ) -> PILImage.Image:
        raw_avatar = await Avatar.user(fortune["user_id"])
        avatar_sz = round(cls.SZ * cls.AVATAR_RATIO)
        if raw_avatar is None:
            # failed to get avatar
            raw_avatar = PILImage.new("RGB", (avatar_sz, avatar_sz),
                                      Palette.WHITE.to_rgb())
        else:
            raw_avatar = raw_avatar.resize((avatar_sz, avatar_sz))

        theme = Palette.dominant(raw_avatar)
        theme_light = Palette.blend(theme, Palette.WHITE, 0.3)
        theme_dark = Palette.blend(theme, Palette.BLACK, 0.2)

        # upper part: avatar, name, date, lucky color
        border = avatar_sz // cls.AVATAR_BORDER_D
        radius = avatar_sz // cls.AVATAR_RADIUS_D
        radius_outer = radius + border

        avatar_im = Image.from_image(
            raw_avatar, decorations=[RectCrop.of_square(border_radius=radius)])
        avatar_bg = Image.from_color(
            width=avatar_sz + 2 * border,
            height=avatar_sz + 2 * border,
            color=theme_dark,
            decorations=Decorations.of(
                RectCrop.of_square(border_radius=radius_outer)),
        )
        avatar = Stack.from_children([avatar_bg, avatar_im],
                                     alignment=Alignment.CENTER)

        max_name_width = cls.SZ * 2
        max_name_height = cls.SZ // 2
        max_name_size = (max_name_width, max_name_height)
        lucky_color = Color.of(*fortune["lucky_color"])
        # FIXME: incorrect text render start-position
        name_text = FontSizeAdaptableText.of(text=fortune["user_name"],
                                             font=cls.NotoSansHansBold,
                                             font_range=(cls.FONT_LARGE // 4,
                                                         cls.FONT_LARGE),
                                             max_size=max_name_size,
                                             color=theme_light,
                                             stroke_color=theme_dark,
                                             stroke_width=1)
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
        event_good = cls.render_event_row(
            event_width,
            True,
            fortune["event_good"],
            is_dark=background == RenderBackground.BLACK)
        event_bad = cls.render_event_row(
            event_width,
            False,
            fortune["event_bad"],
            is_dark=background == RenderBackground.BLACK)

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
            background=cls.BG_COLOR_MAPPING[background],
            direction=Direction.VERTICAL,
        ).render().to_pil()
