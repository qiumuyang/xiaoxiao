from typing import Iterable

from .element import Element


class LineBreaker:
    """
    A class to handle breaking a sequence of elements into lines based on a maximum width.

    Attributes:
        elements (Iterable[Element]):
            The elements to be processed and broken into lines.
        line_buffer (list[Element]):
            A buffer to hold elements for the current line being processed.

    Methods:
        current_width() -> int:
            Calculates the current width of the elements in the line buffer.

        break_lines(max_width: int | None) -> Iterable[list[Element]]:
            Breaks the elements into lines based on the specified maximum width.
            If max_width is None, yields all elements as a single line.
    """

    def __init__(self, elements: Iterable[Element], patience: int = 3):
        self.elements = elements
        self.line_buffer: list[Element] = []
        self.patience = patience

    @property
    def current_width(self) -> int:
        return sum(x.width for x in self.line_buffer)

    def break_lines(
        self,
        max_width: int | None,
        *,
        disable_block: bool = False,
    ) -> Iterable[list[Element]]:
        """
        Breaks the elements into lines based on the specified maximum width.

        Args:
            max_width (int | None):
                The maximum width for each line.
                If None, no restriction is applied. But it is still possible
                to break the elements into multiple lines ("\\n" in text).

        Yields:
            list[Element]: Elements that fit within maximum width.
        """

        self.line_buffer.clear()  # in case of reuse
        remain: Element | None = None
        it = iter(self.elements)

        patience = self.patience
        last_width = float("inf")
        while True:
            current = remain or next(it, None)
            if current is None:
                break  # no more elements

            if not disable_block and not current.inline:
                # block element (force line break before and after)
                if self.line_buffer:
                    yield self.flush()
                # treat it as a single element
                yield from LineBreaker([current], patience).break_lines(
                    max_width, disable_block=True)
                continue

            if current is not remain:
                # reset patience if we're on a new element
                patience = self.patience
                last_width = float("inf")
            if max_width is None:
                this_width = current.width
                next_width = this_width
            else:
                this_width = max_width - self.current_width
                next_width = max_width
            split = current.split_at(this_width, next_width)
            if split.current is not None:
                self.line_buffer.append(split.current)

            if split.remaining is not None:
                if not split.current or not split.current.line_continue:
                    merged = self.flush()
                    if merged:
                        yield merged
                remain = split.remaining
                # Element implementation should guarantee that
                # width of remaining is always reduced
                if remain.width >= last_width:
                    patience -= 1
                    if patience == 0:
                        raise ValueError(f"Element too wide to fit in line: "
                                         f"{remain.width} >= {last_width}, "
                                         f"element={remain}")
                else:
                    last_width = remain.width
                    patience = self.patience
            else:
                remain = None
        if self.line_buffer:
            yield self.flush()

    def flush(self) -> list[Element]:
        """
        Flushes the remaining elements in the line buffer.

        Returns:
            list[Element]: The remaining elements in the line buffer.
        """
        if self.line_buffer:
            buffer = []
            current = self.line_buffer[0]
            for item in self.line_buffer[1:]:
                merged = current.merge(item)
                if merged is None:
                    buffer.append(current)
                    current = item
                else:
                    current = merged
            buffer.append(current)
            self.line_buffer.clear()
            return buffer
        return []
