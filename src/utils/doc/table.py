class Table:

    def __init__(self,
                 header: list[str],
                 formats: list[str] | None = None) -> None:
        self.header = header
        self.rows = []
        self.formats = formats or ["{}"] * len(header)
        if len(self.formats) != len(header):
            raise ValueError("Length of formats does not match header")

    def append(self, row: list[str]) -> None:
        if len(row) > len(self.header):
            raise ValueError("Row length exceeds header length")
        escaped_row = [cell.replace("|", "\\|").strip() for cell in row]
        self.rows.append(escaped_row)

    def __bool__(self) -> bool:
        return bool(self.rows)

    def render(self) -> str:
        rendered = [
            "|" + "|".join(self.header) + "|",
            "|" + "|".join("-" * len(cell) for cell in self.header) + "|",
        ]

        for row in self.rows:
            inner = "|".join(
                f.format(cell) for f, cell in zip(self.formats, row))
            rendered.append(f"|{inner}|")
        return "\n".join(rendered)
