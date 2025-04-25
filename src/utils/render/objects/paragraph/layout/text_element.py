import string
from bisect import bisect_right
from typing import ClassVar

import pyphen

from ....base import Hyphen, OverflowWrap, RenderText
from .element import Element, Split


def isalpha(char: str) -> bool:
    return char in string.ascii_letters


class TextElement(RenderText):
    # yapf: disable
    # English quotation marks `""` should be considered separately
    PUNCTUATION_KEEP_PREVIOUS = {".", "?", "!", ",", ";", ":", ")", "]", "}",
                                 "。", "？", "！", "，", "、", "；", "：", "）", "》",
                                 "】", "」", "”"}
    PUNCTUATION_KEEP_NEXT = {"(", "[", "{", "（", "《", "【", "「", "“"}
    PUNCTUATIONS = PUNCTUATION_KEEP_PREVIOUS | PUNCTUATION_KEEP_NEXT
    # yapf: enable

    hypenator: ClassVar = pyphen.Pyphen(lang="en_US")

    def _compute_overflow(self, text: str, width: int, *,
                          add_hyphen: bool) -> int:
        """Compute the maximum substring length that fits into width."""
        suffix = "-" if add_hyphen else ""
        index = bisect_right(
            range(len(text) + 1),
            width,
            key=lambda x: self.with_text(text[:x] + suffix).width,
        ) - 1
        return 0 if index <= 0 else index

    def split_at(self, width: int, next_width: int) -> Split:
        # check shortcut if multiline
        if self.multiline:
            cur, rem = self._do_multiline(width, next_width)
            cur = self.with_text(cur) if cur else None
            rem = self.with_text(rem) if rem else None
            if rem:
                rem.multiline = self.multiline  # pass multiline info
            if cur and not self.multiline:
                cur.line_continue = True
                if rem:
                    remain_width = width - cur.width
                    rem.lstrip_safe = remain_width < rem[0].width
            return Split(current=cur, remaining=rem)

        if self.lstrip_safe:
            self.text = self.text.lstrip(" ")  # remove leading space

        # self.text[:overflow] is the text that fits in max_width
        overflow = self._compute_overflow(self.text, width, add_hyphen=False)
        if overflow == len(self.text) and "\n" not in self.text:
            return Split(current=self, remaining=None)
        if overflow == 0:
            return Split(current=None, remaining=self)

        # case 1. split at newline
        fitting_text = self.text[:overflow]
        if "\n" in fitting_text:
            index = fitting_text.index("\n")
            cur, rem = self[:index], self[index + 1:]
            rem.lstrip_safe = False
            return Split(current=cur, remaining=rem)

        # case 2. split at English word boundary
        index = overflow
        prv, nxt = self.text[index - 1], self.text[index]
        if isalpha(prv) and isalpha(nxt):
            cur, rem = self._split_word(index, width, next_width)
            # allow RenderText("") to avoid max on empty sequence
            cur = self.with_text(cur) if cur else None
            rem = self.with_text(rem) if rem else None
            if rem:
                rem.multiline = self.multiline  # pass multiline info
            if cur and not self.multiline:
                cur.line_continue = True
                if rem:
                    rem.lstrip_safe = False
            return Split(current=cur, remaining=rem)

        if nxt == " ":
            return Split(current=self[:index], remaining=self[index + 1:])

        # eat one newline of remaining text if any
        if self.text[index] == "\n":
            current, remaining = self.text[:index], self.text[index + 1:]
            hard_break = True
        else:
            current, remaining = self.text[:index], self.text[index:]
            hard_break = False
        cur, rem = self.with_text(current), self.with_text(remaining)
        rem.lstrip_safe = not hard_break
        return Split(current=cur, remaining=rem)
        # return Split(current=self.with_text(current),
        #              remaining=self.with_text(remaining))
        # # case 3. split at punctuation
        # if nxt in self.PUNCTUATION_KEEP_PREVIOUS:
        #     index = self._split_punctuation_to_next(self.text, index)
        #     return Split(current=self[:index], remaining=self[index:])
        # if prv in self.PUNCTUATION_KEEP_NEXT:
        #     index = self._split_punctuation_to_previous(self.text, index)
        #     return Split(current=self[:index], remaining=self[index:])

        # # case 4. split at space
        # if nxt == " ":
        #     pass

    @property
    def line_continue(self) -> bool:
        return getattr(self, "_on_same_line", False)

    @line_continue.setter
    def line_continue(self, value: bool):
        setattr(self, "_on_same_line", value)

    @property
    def lstrip_safe(self) -> bool:
        return getattr(self, "_lstrip_safe", False)

    @lstrip_safe.setter
    def lstrip_safe(self, value: bool):
        setattr(self, "_lstrip_safe", value)

    @property
    def multiline(self) -> tuple[str, str] | None:
        """For break word across lines.

        Returns:
            tuple[str, str] | None:
                A tuple of the word split across lines.
                The first element is the part processed in previous lines.
                The second element is the part to be processed in current line.
                None if the word is not split.
        """
        return getattr(self, "_multiline", None)

    @multiline.setter
    def multiline(self, value: tuple[str, str] | None):
        setattr(self, "_multiline", value)

    def _do_multiline(self, width: int, next_width: int) -> tuple[str, str]:
        assert self.multiline is not None
        previous, processing = self.multiline

        # If the whole processing fits, clear multiline and return.
        if self.with_text(processing).width <= width:
            self.multiline = None
            return processing, self.text.removeprefix(processing)

        def update_multiline(fits: str,
                             rest: str,
                             *,
                             hyphenate: bool = False) -> tuple[str, str]:
            # Update the stored multiline state based on
            # whether we have remaining text.
            self.multiline = (previous + fits, rest) if rest else None
            return ((fits + "-") if hyphenate and fits and rest else
                    fits), self.text.removeprefix(fits)

        if self.wrap.hyphen == Hyphen.NONE:
            # simply find the overflow position
            overflow = self._compute_overflow(processing,
                                              width,
                                              add_hyphen=False)
            fits, rest = processing[:overflow], processing[overflow:]
            return update_multiline(fits, rest, hyphenate=False)

        if self.wrap.hyphen == Hyphen.ANYWHERE:
            # same as None, but add hyphen when calculating overflow
            overflow = self._compute_overflow(processing,
                                              width,
                                              add_hyphen=True)
            fits, rest = processing[:overflow], processing[overflow:]
            # Enforce minimum character counts
            # if the whole word fits on the next line.
            left_insufficient = len(fits) < self.hypenator.left
            right_insufficient = 0 < len(rest) < self.hypenator.right
            if left_insufficient or right_insufficient:
                if self.with_text(processing).width <= next_width:
                    # space on the next line is enough for the whole word
                    # refuse to break here
                    fits, rest = "", processing
            return update_multiline(fits, rest, hyphenate=True)

        if self.wrap.hyphen == Hyphen.RULE:
            # use hyphenator to find the hyphenation point
            full_word = previous + processing
            # Get hyphenation positions that lie in the 'processing' part.
            positions = [
                p - len(previous) for p in self.hypenator.positions(full_word)
                if p > len(previous)
            ]
            current_width = self.with_text(processing).width
            for pos in reversed(positions):
                current_width = self.with_text(processing[:pos] + "-").width
                if current_width <= width:
                    return update_multiline(processing[:pos],
                                            processing[pos:],
                                            hyphenate=True)
            # If no valid break was found,
            # and the first part would fit on the next line
            if current_width <= next_width:
                return "", self.text
            # Otherwise, fallback to ANYWHERE
            overflow = self._compute_overflow(processing,
                                              width,
                                              add_hyphen=True)
            fits, rest = processing[:overflow], processing[overflow:]
            return update_multiline(fits, rest, hyphenate=True)
        raise ValueError("Invalid hyphen setting")

    def _split_word(self, cursor: int, width: int,
                    next_width: int) -> tuple[str, str]:
        text = self.text
        left = right = cursor
        while left > 0 and isalpha(text[left - 1]):
            left -= 1
        while right < len(text) and isalpha(text[right]):
            right += 1
        word = text[left:right]
        match self.wrap.overflow:
            case OverflowWrap.FLEX:
                cur, rem = text[:left], text[left:]
                # the following 2 lines
                # to simulate multiline case for _do_multiline
                word_width = width - self.with_text(text[:left]).width
                rem_element = self.with_text(rem)
                rem_element.multiline = ("", word)
                # word break for this line
                head, tail = rem_element._do_multiline(word_width, next_width)
                self.multiline = rem_element.multiline
                return cur + head, tail
            case OverflowWrap.STRICT:  # the word will be put in the next line
                if self.with_text(word).width > next_width:
                    # word cannot fit in next line, requires word break
                    self.multiline = ("", word)
                # else: word fits in next line, do nothing extra
                return text[:left], text[left:]
            case _:
                raise ValueError("Invalid overflow wrap setting")

    def _split_punctuation_to_next(self, text: str, overflow: int) -> int:
        return overflow

    def _split_punctuation_to_previous(self, text: str, overflow: int) -> int:
        return overflow

    def merge(self, other: Element) -> "Element | None":
        if not isinstance(other, TextElement):
            return None
        if self.style != other.style:
            return None
        return self.with_text(self.text + other.text)

    @property
    def inline(self) -> bool:
        return True
