from mistletoe.span_token import SpanToken

from ._emoji import EMOJI_MULTI_REGEXP


class Emoji(SpanToken):

    pattern = EMOJI_MULTI_REGEXP
    parse_group = 1

    def __init__(self, match):
        self.math = match.group(1)
