import pytest

from src.utils.render.objects.paragraph.markup.parser import (
    MarkupElement, MarkupImage, MarkupParser, MarkupSyntaxError, MarkupText)


def test_markup_good():
    testcases = [
        ("<br/>", [MarkupImage("br")]),
        ("<br></br>", [MarkupElement("br", [])]),
        ("<div><span>hello</span></div>", [
            MarkupElement("div",
                          [MarkupElement("span", [MarkupText("hello")])])
        ]),
        ("<div><span>hello</span><span>world</span></div>", [
            MarkupElement("div", [
                MarkupElement("span", [MarkupText("hello")]),
                MarkupElement("span", [MarkupText("world")])
            ])
        ]),
        ("Pure text", [MarkupText("Pure text")]),
        ("<p><br/></p>", [MarkupElement("p", [MarkupImage("br")])]),
        ("<invalid!>", [MarkupText("<invalid!>")]),
    ]
    for text, expected in testcases:
        parser = MarkupParser(text)
        got = parser.parse()
        assert got == expected


def test_markup_bad():
    testcases = [
        "<div></span>",
        "<div>",
        "</div>",
        "<div/></div>",
        "</img/>",
    ]
    for text in testcases:
        parser = MarkupParser(text)
        with pytest.raises(MarkupSyntaxError):
            parser.parse()
