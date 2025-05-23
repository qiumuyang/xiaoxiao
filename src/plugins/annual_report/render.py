import asyncio
import math
import random
from datetime import datetime
from functools import lru_cache

from PIL import Image as PILImage

from src.utils.env import inject_env
from src.utils.image.avatar import Avatar
from src.utils.render import *
from src.utils.render_ext.data_graph import BarChart

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
    AVATAR_BORDER = Border.of(1, Color.of(240, 240, 240, 128))
    TREND_BORDER = Border.of(3, Palette.WHITE.with_alpha(0.4))
    GLOBAL_MARGIN = Space.of_side(horizontal=30, vertical=15)

    EMPH_COLOR = Color.of(80, 80, 80)
    NORMAL_COLOR = EMPH_COLOR.with_alpha(0.75)

    EMOJI_FONT = FontFamily.of(regular=SegUIEmoji,
                               embedded_color=True,
                               scale=0.85,
                               baseline_correction=True)
    MAIN_FONT = FontFamily.of(regular=NotoSansHansRegular,
                              bold=NotoSansHansBold,
                              fallbacks=EMOJI_FONT)
    MAIN_STYLE = TextStyle(font=MAIN_FONT, size=18, color=NORMAL_COLOR)
    STYLES = {
        "s": TextStyle(size=0.75),
        "b": TextStyle(size=1.6, bold=True),
        "b2": TextStyle(size=1.2, bold=True),
    }

    CAPTION_STYLE = TextStyle(font=NotoSansHansLight,
                              size=14,
                              color=Palette.GRAY)

    TITLE_TEMPLATE = "{name} · {year}群聊年度报告"
    ACTIVE_DAYS_TEMPLATE = "今年，你在群内活跃了 <b>{active_days}</b> 天"
    MESSAGE_COUNT_TEMPLATE = ("在这些日子里，你一共发送了 <b>{num_messages}</b> 条消息，"
                              "排名第 <b>{message_rank}</b>")
    MOST_MESSAGE_TEMPLATE = ("你在 <b>{month}月{day}日</b> 发了<b>{most_message}</b>"
                             "条消息\n{most_message_comment}")
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
    POPULAR_SENTENCE_TEMPLATE = ("你最喜欢说的一句话是“<b>{sentence}</b>”\n"
                                 "过去的一年里足足说了 <b>{times}</b> 次")
    NO_MESSAGE_FALLBACK = "这一年还没有发送过消息\n未语亦有痕，或待璀璨时"

    GROUP_ACTIVE_DAYS_TEMPLATE = "今年，群内活跃了 <b>{active_days}</b> 天"
    GROUP_MESSAGE_COUNT_TEMPLATE = ("在这些日子里，<b>{active_users}</b> "
                                    "位群友一共发送了 <b>{num_messages}</b> 条消息")
    GROUP_MOST_USER_TEMPLATE = ("<b>{month}月{day}日</b>，"
                                "群内共有 <b>{most_user}</b> 人发言")
    GROUP_MOST_MESSAGE_TEMPLATE = ("<b>{month}月{day}日</b>共发送 "
                                   "<b>{most_message}</b> 条消息")
    GROUP_COMMENTS = ["历历瞬间 令人难忘", "真是温暖的大家庭", "和你们聊天，不怕冷场"]
    GROUP_POPULAR_SENTENCE_TEMPLATE = ("过去的一年里，<b>{users}</b> 位群友说了"
                                       "<b>{times}</b>次“<b>{sentence}</b>”")
    GROUP_POPULAR_SENTENCE_EXTRA = ("此外，群友们还经常说：\n"
                                    "{items:[\n]“<b2>{{sentence}}</b2>” "
                                    "（{{users}} <s>人</s>{{times}} <s>次</s>）}")
    GROUP_TOP_USER_MESSAGE_TEMPLATE = "发言TOP3占比 <b>{top3_ratio:.1%}</b>"
    GROUP_TOP_USER_MESSAGE_COMMENT_THRESH = 0.5
    GROUP_TOP_USER_MESSAGE_COMMENTS = [
        "不愧是你群的灵魂人物",
        "占据了群里的半壁江山",
        "无疑是群中砥柱",
    ]
    GROUP_TOP_USER_TALKATIVE_TEMPLATE = "龙王天数TOP3占比 <b>{top3_ratio:.1%}</b>"
    GROUP_TOP_USER_TALKATIVE_COMMENT_THRESH = 0.6
    GROUP_TOP_USER_TALKATIVE_COMMENTS = [
        "开群看到的不是ta就是ta",
        "有他们在，别想抢到龙王",
    ]

    TITLE_COLOR = Color.of(40, 40, 40)
    MONTH_COLOR1 = Color.from_hex("#c2e9fb")
    MONTH_COLOR2 = Color.from_hex("#a1c4fd")
    DAY_COLOR1 = Color.from_hex("#f6d365")
    DAY_COLOR2 = Color.from_hex("#fda085")
    BG_COLOR1 = Color.from_hex("#a8edea")
    BG_COLOR2 = Color.from_hex("#fed6e3")
    HOR_LINE_COLOR = NORMAL_COLOR.with_alpha(0.25)

    TREND_CAPTION_TEXT = Paragraph.of("活跃度趋势", style=CAPTION_STYLE)
    TALKATIVE_DAYS_FALLBACK_TEXT = Paragraph.of(TALKATIVE_DAYS_FALLBACK,
                                                style=MAIN_STYLE)
    NO_MESSAGE_FALLBACK_TEXT = Paragraph.of(NO_MESSAGE_FALLBACK,
                                            style=MAIN_STYLE,
                                            margin=Space.of_side(0, 40))

    @classmethod
    async def render_group(cls, group: GroupStatistics, group_id: int,
                           group_name: str):
        comp_width_reserve = Spacer.of(width=cls.MAX_WIDTH)
        comp_footer = cls._render_footer()
        year = datetime.strptime(cls.ANNUAL_STATISTICS_END, "%Y-%m-%d").year
        comp_title = cls._render_title(group_name, year)
        comp_avatar = await cls._render_avatar(group_id=group_id)

        if not group or group.num_messages == 0:
            return Container.from_children(
                (comp_width_reserve, comp_title, comp_avatar,
                 cls.NO_MESSAGE_FALLBACK_TEXT, comp_footer),
                alignment=Alignment.CENTER,
                direction=Direction.VERTICAL,
                spacing=30,
            )

        comp_basic_info1 = Paragraph.from_template(
            cls.GROUP_ACTIVE_DAYS_TEMPLATE,
            values=dict(active_days=group.active_days),
            default=cls.MAIN_STYLE,
            styles=cls.STYLES,
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
        )
        comp_basic_info2 = Paragraph.from_template(
            cls.GROUP_MESSAGE_COUNT_TEMPLATE,
            values=dict(active_users=group.active_users,
                        num_messages=group.num_messages),
            default=cls.MAIN_STYLE,
            styles=cls.STYLES,
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
        )
        comp_trend = cls._render_message_trend(group.message_each_month,
                                               group.message_each_day)
        assert group.most_user is not None
        assert group.most_message is not None
        most_user_date, most_user = group.most_user
        most_message_date, most_message = group.most_message
        comp_most_user = Paragraph.from_template(
            cls.GROUP_MOST_USER_TEMPLATE,
            values=dict(month=most_user_date.month,
                        day=most_user_date.day,
                        most_user=most_user),
            default=cls.MAIN_STYLE,
            styles=cls.STYLES,
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
        )
        comp_most_message = Paragraph.from_template(
            cls.GROUP_MOST_MESSAGE_TEMPLATE,
            values=dict(month=most_message_date.month,
                        day=most_message_date.day,
                        most_message=most_message),
            default=cls.MAIN_STYLE,
            styles=cls.STYLES,
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
        )
        comp_comment = Paragraph.of(text=random.choice(cls.GROUP_COMMENTS),
                                    style=cls.MAIN_STYLE,
                                    alignment=Alignment.CENTER,
                                    max_width=cls.MAX_WIDTH)
        components = [
            comp_width_reserve,
            comp_title,
            comp_avatar,
            comp_basic_info1,
            comp_basic_info2,
            comp_trend,
            comp_most_user,
            comp_most_message,
            comp_comment,
        ]
        if group.popular_sentences:
            pop = group.popular_sentences
            top_sentence, top_times, top_users = pop[0]
            comp_popular_sentence = Paragraph.from_template(
                cls.GROUP_POPULAR_SENTENCE_TEMPLATE,
                values=dict(users=top_users,
                            times=top_times,
                            sentence=top_sentence),
                default=cls.MAIN_STYLE,
                styles=cls.STYLES,
                alignment=Alignment.CENTER,
                max_width=cls.MAX_WIDTH,
            )
            components.append(cls._render_horizontal_line(cls.MAX_WIDTH))
            components.append(comp_popular_sentence)
            if len(pop) > 1:
                sampled = random.sample(pop[1:], min(3, len(pop) - 1))
                sampled = sorted(sampled, key=lambda x: -x[1])
                comp_popular_sentence_extra = Paragraph.from_template(
                    cls.GROUP_POPULAR_SENTENCE_EXTRA,
                    values=dict(items=[{
                        "sentence": sentence,
                        "users": users,
                        "times": times
                    } for sentence, times, users in sampled]),
                    default=cls.MAIN_STYLE,
                    styles=cls.STYLES,
                    alignment=Alignment.CENTER,
                    max_width=cls.MAX_WIDTH,
                    line_spacing=15,
                )
                components.append(comp_popular_sentence_extra)
        if len(group.user_messages) > 5:
            comp_top_message_user = await cls._render_top_users(
                group.user_messages)
            ratio = sum(v for _, v in sorted(group.user_messages.items(),
                                             key=lambda x: -x[1])
                        [:3]) / group.num_messages
            comp_top_message_text = Paragraph.from_template(
                cls.GROUP_TOP_USER_MESSAGE_TEMPLATE,
                values=dict(top3_ratio=ratio),
                default=cls.MAIN_STYLE,
                styles=cls.STYLES,
                alignment=Alignment.CENTER,
                max_width=cls.MAX_WIDTH,
            )
            components.append(cls._render_horizontal_line(cls.MAX_WIDTH))
            components.append(comp_top_message_user)
            components.append(comp_top_message_text)
            if ratio > cls.GROUP_TOP_USER_MESSAGE_COMMENT_THRESH:
                comp_top_message_comment = Paragraph.of(
                    text=random.choice(cls.GROUP_TOP_USER_MESSAGE_COMMENTS),
                    style=cls.MAIN_STYLE,
                    alignment=Alignment.CENTER,
                    max_width=cls.MAX_WIDTH,
                )
                components.append(comp_top_message_comment)
        if len(group.user_talkative_days) > 5:
            comp_top_talkative_user = await cls._render_top_users(
                group.user_talkative_days)
            ratio = sum(v for _, v in sorted(group.user_talkative_days.items(),
                                             key=lambda x: -x[1])
                        [:3]) / group.active_days
            comp_top_talkative_text = Paragraph.from_template(
                cls.GROUP_TOP_USER_TALKATIVE_TEMPLATE,
                values=dict(top3_ratio=ratio),
                default=cls.MAIN_STYLE,
                styles=cls.STYLES,
                alignment=Alignment.CENTER,
                max_width=cls.MAX_WIDTH,
            )
            components.append(cls._render_horizontal_line(cls.MAX_WIDTH))
            components.append(comp_top_talkative_user)
            components.append(comp_top_talkative_text)
            if ratio > cls.GROUP_TOP_USER_TALKATIVE_COMMENT_THRESH:
                comp_top_talkative_comment = Paragraph.of(
                    text=random.choice(cls.GROUP_TOP_USER_TALKATIVE_COMMENTS),
                    style=cls.MAIN_STYLE,
                    alignment=Alignment.CENTER,
                    max_width=cls.MAX_WIDTH,
                )
                components.append(comp_top_talkative_comment)
        return cls._fill_bg(
            Container.from_children(
                (*components, comp_footer),
                alignment=Alignment.CENTER,
                direction=Direction.VERTICAL,
                spacing=30,
                margin=cls.GLOBAL_MARGIN,
            ))

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
        if not user or user.num_messages == 0:
            return Container.from_children(
                (comp_width_reserve, comp_title, comp_avatar,
                 cls.NO_MESSAGE_FALLBACK_TEXT, comp_footer),
                alignment=Alignment.CENTER,
                direction=Direction.VERTICAL,
                spacing=30,
            )
        comp_basic_info1 = Paragraph.from_template(
            cls.ACTIVE_DAYS_TEMPLATE,
            values=dict(active_days=user.active_days),
            default=cls.MAIN_STYLE,
            styles=cls.STYLES,
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
        )
        comp_basic_info2 = Paragraph.from_template(
            cls.MESSAGE_COUNT_TEMPLATE,
            values=dict(num_messages=user.num_messages,
                        message_rank=user.message_rank),
            default=cls.MAIN_STYLE,
            styles=cls.STYLES,
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
        comp_most_message = Paragraph.from_template(
            cls.MOST_MESSAGE_TEMPLATE,
            values=dict(month=most_message_date.month,
                        day=most_message_date.day,
                        most_message=most_message,
                        most_message_comment=random.choice(comments)),
            default=cls.MAIN_STYLE,
            styles=cls.STYLES,
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
            line_spacing=20,
        )
        if user.talkative_days:
            comp_talkative_days = Paragraph.from_template(
                cls.TALKATIVE_DAYS_TEMPLATE,
                values=dict(talkative_days=user.talkative_days,
                            talkative_rank=user.talkative_rank),
                default=cls.MAIN_STYLE,
                styles=cls.STYLES,
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
            comp_popular_sentence = Paragraph.from_template(
                cls.POPULAR_SENTENCE_TEMPLATE,
                values=dict(sentence=sentence, times=times),
                default=cls.MAIN_STYLE,
                styles=cls.STYLES,
                alignment=Alignment.CENTER,
                max_width=cls.MAX_WIDTH,
            )
            components.append(comp_popular_sentence)

        return cls._fill_bg(
            Container.from_children(
                (*components, comp_talkative_days, comp_footer),
                alignment=Alignment.CENTER,
                direction=Direction.VERTICAL,
                spacing=30,
                margin=cls.GLOBAL_MARGIN,
            ))

    @classmethod
    def _render_title(cls, name: str, year: int):
        return Paragraph.from_template(
            cls.TITLE_TEMPLATE,
            values=dict(name=name, year=year),
            default=TextStyle(font=cls.TITLE_FONT,
                              size=cls.TITLE_FONT_SIZE,
                              color=cls.TITLE_COLOR),
            alignment=Alignment.CENTER,
            max_width=cls.MAX_WIDTH,
            margin=Space(10, 10, 20, 10),
        )

    @classmethod
    async def _render_avatar(cls,
                             *,
                             user_id: int = -1,
                             group_id: int = -1,
                             size: int = -1):
        if user_id != -1:
            avatar = await Avatar.user(user_id)
        elif group_id != -1:
            avatar = await Avatar.group(group_id)
        else:
            raise ValueError
        if size == -1:
            size = cls.AVATAR_SIZE
        return Image.from_image(
            avatar.resize((size, size)),
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
    async def _render_top_users(cls, users: dict[int, int]):
        # users: user_id -> num
        sorted_users = sorted(users.items(), key=lambda x: -x[1])
        top = []
        for i, (user_id, num) in enumerate(sorted_users[:3]):
            space = Spacer.of(height=cls.AVATAR_SIZE // 4)
            avatar = await cls._render_avatar(user_id=user_id)
            caption = Paragraph.of(f"{num}", style=cls.CAPTION_STYLE)
            if i == 0:
                # top1 is higher than others
                order = [avatar, space, caption]
            else:
                order = [space, avatar, caption]
            top.append(
                Container.from_children(order,
                                        alignment=Alignment.CENTER,
                                        direction=Direction.VERTICAL,
                                        spacing=10))
        comp_top = Container.from_children([top[1], top[0], top[2]],
                                           alignment=Alignment.START,
                                           direction=Direction.HORIZONTAL,
                                           spacing=cls.AVATAR_SIZE // 2)
        if len(users) > 8:
            avatars = await asyncio.gather(*(
                cls._render_avatar(user_id=user_id, size=cls.AVATAR_SIZE // 2)
                for user_id, _ in sorted_users[3:10]))
            comp_smaller = Container.from_children(
                children=avatars,
                direction=Direction.HORIZONTAL,
                spacing=15,
            )
            return Container.from_children([comp_top, comp_smaller],
                                           alignment=Alignment.CENTER,
                                           direction=Direction.VERTICAL,
                                           spacing=25)
        return comp_top

    @classmethod
    @lru_cache
    def _render_footer(cls):
        return Paragraph.of(
            f"* 数据起止：{cls.ANNUAL_STATISTICS_BEGIN} ~"
            f"{cls.ANNUAL_STATISTICS_END}",
            style=cls.CAPTION_STYLE,
            margin=Space.of_side(0, 20))

    @classmethod
    def _fill_bg(cls, obj: RenderObject):
        import numpy as np
        w, h = obj.width, obj.height
        bg = np.linspace(cls.BG_COLOR1.to_rgb(), cls.BG_COLOR2.to_rgb(), w)
        bg = np.repeat(bg[np.newaxis, :], h, axis=0)
        bg = RenderImage.from_pil(PILImage.fromarray(bg.astype(np.uint8)))
        return Stack.from_children((Image.from_image(bg), obj))

    @classmethod
    def _render_horizontal_line(cls, width: int):
        return Image.from_image(
            RenderImage.from_pil(
                PILImage.new("RGBA", (width, 1), cls.HOR_LINE_COLOR)))
