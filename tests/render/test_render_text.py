from pathlib import Path

from src.utils.render import FontFamily, Palette, RenderText

out = Path("render-test/text-new")
out.mkdir(parents=True, exist_ok=True)


def test_render_text():
    text = "Hello, World! 你好, 世界!"
    RenderText.of(text,
                  "/mnt/c/Windows/Fonts/times.ttf",
                  24,
                  shading=Palette.WHITE).render().save(
                      out / "test_new_render_text.png")

    font_with_fallback = FontFamily.of(
        regular="/mnt/c/Windows/Fonts/times.ttf",
        fallbacks="/mnt/c/Windows/Fonts/simsun.ttc",
    )

    RenderText.of(text, font_with_fallback, 24,
                  shading=Palette.WHITE).render().save(
                      out / "test_new_render_text_with_fallback.png")
