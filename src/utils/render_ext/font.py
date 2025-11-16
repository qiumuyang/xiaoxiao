from src.utils.render import FontFamily


class FontUtils:

    FALLBACK: list[FontFamily | str] = [
        FontFamily.of(regular="data/static/fonts/seguiemj.ttf",
                      embedded_color=True,
                      scale=0.85,
                      baseline_correction=True),
        "data/static/fonts/MiSansThai.ttf",
        "data/static/fonts/MiSansLao.ttf",
        "data/static/fonts/MiSans L3.ttf",
        "data/static/fonts/NotoSansJP-Regular.ttf",
        "data/static/fonts/NotoSansLisu-Regular.ttf",
        "data/static/fonts/MiSansArabic-Regular.ttf",
        "data/static/fonts/MiSansTibetan-Regular.ttf",
        "data/static/fonts/MiSansLatin-Regular.ttf",
        "data/static/fonts/MiSansTC-Regular.ttf",
        "data/static/fonts/arial.ttf",
    ]
