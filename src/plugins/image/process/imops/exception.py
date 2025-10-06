class DSLParseError(Exception):

    def __init__(self,
                 message,
                 line=None,
                 column=None,
                 text=None,
                 span: int = 40):
        super().__init__(message)
        self.line = line
        self.column = column
        self.text = text
        self.span = span

    def __str__(self):
        if self.text and self.column:
            pointer = " " * (self.column - 1) + "^"
            if self.span and self.span > 1:
                p = max(self.column - self.span, 0)
            else:
                p = 0
            return f"Syntax error: {self.args[0]}\n{self.text[p:]}\n{pointer[p:]}"
        return f"Syntax error: {self.args[0]}"
