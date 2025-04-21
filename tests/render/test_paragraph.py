from pathlib import Path

import pytest

from src.plugins.annual_report.render import AnnualReportRenderer
from src.plugins.annual_report.statistics import AnnualStatistics
from src.utils.render import Palette, Paragraph, RenderImage, TextStyle

out = Path("render-test/paragraph")
out.mkdir(parents=True, exist_ok=True)


@pytest.mark.asyncio
async def test_paragraph_in_annual_report():
    user = await AnnualStatistics.user(user_id=782719906, group_id=924824320)
    user.popular_sentence = ("Test Emoji 🤣👉🤡", 10)
    group = await AnnualStatistics.group(group_id=924824320)

    o1 = await AnnualReportRenderer.render_user(user, 782719906,
                                                "<inject>Name</inject>",
                                                924824320)
    o1.render().save(out / "test_paragraph_in_annual_report_user.png")

    o2 = await AnnualReportRenderer.render_group(group, 924824320, "test")
    o2.render().save(out / "test_paragraph_in_annual_report_group.png")


def test_paragraph_with_image():
    content = "蓝的盆<pen/>盆的<i>蓝</i>"
    for max_width in [100, 200, 400, None]:
        Paragraph.from_markup(
            content,
            max_width=max_width,
            default=TextStyle(font="/mnt/c/Windows/Fonts/simsun.ttc", size=24),
            styles=dict(i=TextStyle(italic=True)),
            images=dict(pen=RenderImage.from_file(
                "/home/qmy/XiaoBot/2.jpg").rescale(0.25)),
            line_spacing=6,
            background=Palette.GRAY,
        ).render().save(out / f"test_paragraph_with_image_{max_width}.png")
