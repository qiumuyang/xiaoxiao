import math
import random
from datetime import datetime
from functools import lru_cache

from PIL import Image as PILImage

from src.utils.env import inject_env
from src.utils.image.avatar import Avatar
from src.utils.render import *

from .statistics import GroupStatistics, UserStatistics


@inject_env()
class AnnualReportRenderer:

    ANNUAL_STATISTICS_BEGIN: str
    ANNUAL_STATISTICS_END: str

    NotoSansHansLight = "data/static/fonts/NotoSansHans-Light.otf"
    NotoSansHansRegular = "data/static/fonts/NotoSansHans-Regular.ttf"
    NotoSansHansBold = "data/static/fonts/NotoSansHans-Bold.otf"
    SegUIEmoji = "data/static/fonts/seguiemj.ttf"

    MAX_WIDTH = 500
    TITLE_FONT = NotoSansHansBold
    TITLE_FONT_SIZE = 40
    AVATAR_SIZE = 80
    AVATAR_DEFAULT = PILImage.new("RGB", (AVATAR_SIZE, AVATAR_SIZE),
                                  Palette.WHITE)
    AVATAR_BORDER = Border.of(1, Color.of(240, 240, 240, 128))
    TREND_BORDER = Border.of(3, Palette.WHITE.of_alpha(0.4))

    EMPH_TEXT_COLOR = Color.of(80, 80, 80)
    NORMAL_TEXT_COLOR = EMPH_TEXT_COLOR.of_alpha(0.75)
    NORMAL_TEXT_STYLE = TextStyle.of(
        font=NotoSansHansRegular,
        size=18,
        color=NORMAL_TEXT_COLOR,
    )
    EMPH_TEXT_STYLE = TextStyle.of(
        font=NotoSansHansBold,
        size=1.6,  # relative to normal
        color=EMPH_TEXT_COLOR,
    )
    EMOJI_TEXT_STYLE = TextStyle.of(font=SegUIEmoji,
                                    size=0.85,
                                    stroke_width=0,
                                    embedded_color=True,
                                    ymin_correction=True)

    ACTIVE_DAYS_TEMPLATE = "今年，你在群内活跃了 <b>{active_days}</b> 天"
    MESSAGE_COUNT_TEMPLATE = ("在这些日子里，你一共发送了 <b>{num_messages}</b> 条消息，"
                              "排名第 <b>{message_rank}</b>")
    MOST_MESSAGE_TEMPLATE = ("你在 <b>{month}月{day}日</b> 发了<b>{most_message}</b>"
                             "条消息\n\n{most_message_comment}")
    MOST_MESSAGE_COMMENTS = [
        "或许发生了什么有趣的事",
        "还记得当时聊了些什么吗",
        "真是妙语连珠，舌灿莲花",
    ]
    MOST_MESSAGE_COMMENT_CONDITION = {
        (int.__le__, 20): ["一切点滴都值得分享", "生活故事多，群中多唠嗑", "多来群里聊天吧"],
        (int.__ge__, 80): ["你的能量，超乎你想象", "话语如泉涌，灵感永不穷"],
    }
    TALKATIVE_DAYS_TEMPLATE = ("获得了 <b>{talkative_days}</b> 次群龙王，"
                               "排名第 <b>{talkative_rank}</b>")
    TALKATIVE_DAYS_FALLBACK = "你还没有获得过群龙王"
    POPULAR_SENTENCE_TEMPLATE = ("你最喜欢说的一句话是“<b>{popular}</b>”\n"
                                 "过去的一年里足足说了 <b>{times}</b> 次")
    NO_MESSAGE_FALLBACK = "你今年还没有发送过消息\n未语亦有痕，或待璀璨时"

    TITLE_COLOR = Color.of(40, 40, 40)
    MONTH_COLOR1 = Color.of_hex("#c2e9fb")
    MONTH_COLOR2 = Color.of_hex("#a1c4fd")
    DAY_COLOR1 = Color.of_hex("#f6d365")
    DAY_COLOR2 = Color.of_hex("#fda085")
    BG_COLOR1 = Color.of_hex("#a8edea")
    BG_COLOR2 = Color.of_hex("#fed6e3")

    TREND_CAPTION_TEXT = Text.of("活跃度趋势",
                                 font=NotoSansHansLight,
                                 size=14,
                                 color=Palette.GRAY)
    TALKATIVE_DAYS_FALLBACK_TEXT = Text.from_style(TALKATIVE_DAYS_FALLBACK,
                                                   style=NORMAL_TEXT_STYLE)
    NO_MESSAGE_FALLBACK_TEXT = Text.from_style(NO_MESSAGE_FALLBACK,
                                               style=NORMAL_TEXT_STYLE,
                                               margin=Space.of_side(0, 40))

    @classmethod
    async def render_group(cls, group: GroupStatistics, group_id: int,
                           group_name: str):
        pass

    @classmethod
    async def render_user(cls, user: UserStatistics, user_id: int,
                          user_name: str, group_id: int) -> RenderObject:
        comp_width_reserve = Spacer.of(width=cls.MAX_WIDTH)
        comp_footer = cls._render_footer()
        year = datetime.strptime(cls.ANNUAL_STATISTICS_END, "%Y-%m-%d").year
        comp_title = cls._render_title(user_name, year)
        comp_avatar = Container.from_children(
            [
                await cls._render_avatar(user_id=user_id),
                await cls._render_avatar(group_id=group_id),
            ],
            spacing=cls.AVATAR_SIZE // 2,
            direction=Direction.HORIZONTAL,
        )
        if user.num_messages == 0:
            return Container.from_children(
                (comp_width_reserve, comp_title, comp_avatar,
                 cls.NO_MESSAGE_FALLBACK_TEXT, comp_footer),
                alignment=Alignment.CENTER,
                direction=Direction.VERTICAL,
                spacing=30,
            )
        comp_basic_info1 = StyledText.of(
            text=cls.ACTIVE_DAYS_TEMPLATE.format(active_days=user.active_days),
            default=cls.NORMAL_TEXT_STYLE,
            styles={"b": cls.EMPH_TEXT_STYLE},
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
        )
        comp_basic_info2 = StyledText.of(
            text=cls.MESSAGE_COUNT_TEMPLATE.format(
                num_messages=user.num_messages,
                message_rank=user.message_rank),
            default=cls.NORMAL_TEXT_STYLE,
            styles={"b": cls.EMPH_TEXT_STYLE},
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
        )
        comp_trend = cls._render_message_trend(user.message_each_month,
                                               user.message_each_day)
        assert user.most_message is not None
        most_message_date, most_message = user.most_message
        comments = cls.MOST_MESSAGE_COMMENTS.copy()
        for (op, thresh), extra in cls.MOST_MESSAGE_COMMENT_CONDITION.items():
            if op(most_message, thresh):
                comments.extend(extra)
        comp_most_message = StyledText.of(
            text=cls.MOST_MESSAGE_TEMPLATE.format(
                month=most_message_date.month,
                day=most_message_date.day,
                most_message=most_message,
                most_message_comment=random.choice(comments)),
            default=cls.NORMAL_TEXT_STYLE,
            styles={"b": cls.EMPH_TEXT_STYLE},
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
            line_spacing=20,
        )
        if user.talkative_days:
            comp_talkative_days = StyledText.of(
                text=cls.TALKATIVE_DAYS_TEMPLATE.format(
                    talkative_days=user.talkative_days,
                    talkative_rank=user.talkative_rank),
                default=cls.NORMAL_TEXT_STYLE,
                styles={"b": cls.EMPH_TEXT_STYLE},
                alignment=Alignment.CENTER,
                max_width=cls.MAX_WIDTH,
            )
        else:
            comp_talkative_days = cls.TALKATIVE_DAYS_FALLBACK_TEXT
        components = [
            comp_width_reserve,
            comp_title,
            comp_avatar,
            comp_basic_info1,
            comp_basic_info2,
            comp_trend,
            comp_most_message,
        ]
        if user.popular_sentence:
            sentence, times = user.popular_sentence
            filled = cls.POPULAR_SENTENCE_TEMPLATE.format(popular=sentence,
                                                          times=times)
            styled_parts = []
            for text, support in Text.split_font_unsupported(
                    cls.NotoSansHansRegular, filled):
                styled_parts.append(
                    text if support else f"<emoji>{text}</emoji>")
            comp_popular_sentence = StyledText.of(
                text="".join(styled_parts),
                default=cls.NORMAL_TEXT_STYLE,
                styles={
                    "b": cls.EMPH_TEXT_STYLE,
                    "emoji": cls.EMOJI_TEXT_STYLE
                },
                alignment=Alignment.CENTER,
                max_width=cls.MAX_WIDTH,
            )
            components.append(comp_popular_sentence)

        return cls._wrap(
            Container.from_children(
                (*components, comp_talkative_days, comp_footer),
                alignment=Alignment.CENTER,
                direction=Direction.VERTICAL,
                spacing=30,
            ))

    @classmethod
    def _render_title(cls, name: str, year: int):
        styled_parts = []
        for text, support in Text.split_font_unsupported(cls.TITLE_FONT, name):
            styled_parts.append(text if support else f"<emoji>{text}</emoji>")
        return StyledText.of(
            text="{name} · {year}群聊年度报告".format(
                name="".join(styled_parts),
                year=year,
            ),
            styles={"emoji": cls.EMOJI_TEXT_STYLE},
            default=TextStyle.of(font=cls.TITLE_FONT,
                                 size=cls.TITLE_FONT_SIZE,
                                 color=cls.TITLE_COLOR),
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
            margin=Space(10, 10, 20, 10),
        )

    @classmethod
    async def _render_avatar(cls, *, user_id: int = -1, group_id: int = -1):
        avatar = None
        if user_id != -1:
            avatar = await Avatar.user(user_id)
        elif group_id != -1:
            avatar = await Avatar.group(group_id)
        avatar = avatar or cls.AVATAR_DEFAULT
        return Image.from_image(
            avatar.resize((cls.AVATAR_SIZE, cls.AVATAR_SIZE)),
            border=cls.AVATAR_BORDER,
        )

    @classmethod
    def _colorize_month_trend(cls, v: float, min: float, max: float):
        return Palette.natural_blend(cls.MONTH_COLOR1, cls.MONTH_COLOR2,
                                     v / max)

    @classmethod
    def _colorize_day_trend(cls, v: float, min: float, max: float):
        return Palette.natural_blend(cls.DAY_COLOR1, cls.DAY_COLOR2, v / max)

    @classmethod
    def _render_message_trend(cls, month: list[int], day: list[int]):
        chart_month = BarChart(month,
                               bar_width=math.ceil(len(day) / len(month)),
                               bar_spacing=0,
                               bar_length=len(day),
                               layout=Direction.HORIZONTAL,
                               color=cls._colorize_month_trend)
        chart_day = BarChart(day,
                             bar_width=1,
                             bar_spacing=0,
                             bar_length=len(day),
                             layout=Direction.HORIZONTAL,
                             color=cls._colorize_day_trend)
        chart_combine = Stack.from_children((chart_month, chart_day),
                                            border=cls.TREND_BORDER)
        chart_combine_resize = Image.from_image(chart_combine.render().resize(
            cls.MAX_WIDTH * 2 // 3, cls.MAX_WIDTH * 2 // 3))
        return Container.from_children(
            (chart_combine_resize, cls.TREND_CAPTION_TEXT),
            alignment=Alignment.CENTER,
            direction=Direction.VERTICAL,
            spacing=10)

    @classmethod
    @lru_cache
    def _render_footer(cls):
        color = cls.NORMAL_TEXT_COLOR.of_alpha(0.6)
        return Text.of(
            f"* 数据起止：{cls.ANNUAL_STATISTICS_BEGIN} ~"
            f"{cls.ANNUAL_STATISTICS_END}",
            font=cls.NotoSansHansLight,
            size=14,
            color=color,
            margin=Space.of_side(0, 20))

    @classmethod
    def _wrap(cls, obj: RenderObject):
        import numpy as np
        w, h = obj.width, obj.height
        bg = np.linspace(cls.BG_COLOR1.to_rgb(), cls.BG_COLOR2.to_rgb(), w)
        bg = np.repeat(bg[np.newaxis, :], h, axis=0)
        bg = RenderImage.from_pil(PILImage.fromarray(bg.astype(np.uint8)))
        return Stack.from_children((Image.from_image(bg), obj))
