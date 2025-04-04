from pathlib import Path

from src.utils.render import (Alignment, Border, Container, Direction,
                              FontFamily, Palette, Paragraph, RenderText,
                              Space, TextStyle)

out = Path("render-test/render")
out.mkdir(parents=True, exist_ok=True)


def test_render_simulate_italic():
    RenderText.of(
        text="潮水冲淡了他们留在沙滩上的脚印",
        font="data/static/fonts/MSYAHEI.ttc",
        size=20,
        shading=Palette.LIGHT_YELLOW,
        italic=True).render().save("render-test/render/pseudo_italic.png")


def test_render_text_italic_bold():
    ff = FontFamily(regular="data/static/fonts/arial.ttf",
                    bold="data/static/fonts/arialbd.ttf",
                    italic="data/static/fonts/ariali.ttf",
                    bold_italic="data/static/fonts/arialbi.ttf")
    ff_cn = FontFamily(regular="data/static/fonts/MSYAHEI.ttc",
                       bold="data/static/fonts/MSYAHEIbd.ttc")
    default = TextStyle(font=ff, size=24, color=Palette.BLACK)
    text = Paragraph.from_markup(
        "The quick\n"
        "<b>brown fox \n"
        "<i>jumps over</i></b>\n"
        "the <i>lazy dog</i>.\n\n"
        "<cn>潮水<b>冲淡了\n"
        "<i>他们</i>留</b>在\n"
        "沙滩上的<i>脚印</i></cn>",
        default=default,
        styles=dict(i=TextStyle(italic=True),
                    b=TextStyle(bold=True),
                    cn=TextStyle(font=ff_cn)),
        background=Palette.WHITE,
        line_spacing=10,
    )

    text.render().save(out / "text_italic_bold.png")


def test_render_compare_sim_real_italic():
    cmp = []
    for size in [8, 16, 32, 64, 96]:
        sim = Paragraph.of("The quick brown fox jumps over the lazy dog.",
                           TextStyle(font="data/static/fonts/arial.ttf",
                                     size=size,
                                     color=Palette.BLACK,
                                     shading=Palette.WHITE,
                                     italic=True),
                           border=Border.of(1, Palette.LIGHT_PINK))
        real = Paragraph.of("The quick brown fox jumps over the lazy dog.",
                            TextStyle(font="data/static/fonts/ariali.ttf",
                                      size=size,
                                      color=Palette.BLACK,
                                      shading=Palette.WHITE),
                            border=Border.of(1, Palette.LIGHT_GREEN))
        cmp.extend([sim, real])
    Container.from_children(cmp,
                            alignment=Alignment.START,
                            direction=Direction.VERTICAL,
                            spacing=10,
                            padding=Space.all(20),
                            background=Palette.WHEAT).render().save(
                                out / "sim_vs_real.png")
