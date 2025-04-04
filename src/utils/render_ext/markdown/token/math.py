import re

from mistletoe.span_token import SpanToken


class Math(SpanToken):

    pattern = re.compile(r"(\${1,2})([^$]+?)\1")
    parse_group = 0

    def __init__(self, match):
        self.math = match.group(2)
        self.inline = match.group(1) == "$"
