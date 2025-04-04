import io
import re
import xml.sax
from pathlib import Path
from typing import Literal
from xml.sax.handler import feature_namespaces

from py_mini_racer import MiniRacer

from .svgmath import MathHandler, XMLGenerator


class KaTeX:
    """Wrapper around KaTeX to render TeX equations to SVG.

    https://github.com/KaTeX/KaTeX
    """

    _ctx: MiniRacer
    _katex_js = Path(__file__).parent / "katex.js"

    def __init__(self):
        if not hasattr(KaTeX, "_ctx"):
            ctx = MiniRacer()
            ctx.eval(self._katex_js.read_text(encoding="utf-8"))
            KaTeX._ctx = ctx
        self.ctx = KaTeX._ctx

    def render_to_string(self,
                         tex: str,
                         format: Literal["html", "mathml",
                                         "htmlAndMathml"] = "htmlAndMathml",
                         inline: bool = False) -> str:
        return self.ctx.call("katex.renderToString", tex, {
            "output": format,
            "displayMode": not inline
        })

    def render_pure_mathml(self, tex: str, inline: bool = False) -> str:
        katex_mathml = self.render_to_string(tex,
                                             format="mathml",
                                             inline=inline)
        return self.clean_mathml(katex_mathml)

    def render_to_svg(self, tex: str, inline: bool = False) -> str:
        """
        Render a TeX equation to SVG.

        Raises:
            py_mini_racer.JSEvalException:
                If the rendering fails, most likely due to invalid TeX.
            xml.sax.SAXException:
                If svgmath fails to parse mathml.
        """
        mathml = self.render_pure_mathml(tex, inline=inline)

        in_buffer = io.BytesIO(mathml.encode("utf-8"))
        out_buffer = io.BytesIO()
        text_out = io.TextIOWrapper(out_buffer, encoding="utf-8")

        saxoutput = XMLGenerator(text_out, "utf-8")
        handler = MathHandler(saxoutput)
        parser = xml.sax.make_parser()
        parser.setFeature(feature_namespaces, 1)
        parser.setContentHandler(handler)
        parser.parse(in_buffer)

        text_out.flush()
        return out_buffer.getvalue().decode("utf-8")

    @staticmethod
    def clean_mathml(katex_mathml: str) -> str:
        # remove outer span katex
        # <span class="katex"> </span>
        katex_mathml = katex_mathml.replace("<span class=\"katex\">",
                                            "").replace("</span>", "")
        # remove <semantics> and </semantics> tags
        katex_mathml = katex_mathml.replace("<semantics>",
                                            "").replace("</semantics>", "")
        # remove <annotation xxx> and </annotation> tags
        katex_mathml = re.sub(r"<annotation[^>]*>.*?</annotation>",
                              "",
                              katex_mathml,
                              flags=re.DOTALL)
        return katex_mathml


if __name__ == "__main__":
    eq = r"""
    \begin{bmatrix}
    a & b \\
    c & d
    \end{bmatrix}
    \begin{bmatrix}
    x \\
    y
    \end{bmatrix}
    =
    \begin{bmatrix}
    ax + by \\
    cx + dy
    \end{bmatrix}
    """

    eq = r"""\sum_{i=1}^{n} i = \frac{n(n+1)}{2}"""

    katex = KaTeX()

    svg = katex.render_to_svg(eq, inline=True)
    print(svg)
