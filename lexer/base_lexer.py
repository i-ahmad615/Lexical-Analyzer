"""
BaseLexer – shared cursor / source-navigation helpers.
All language-specific lexers extend this class.
"""

from .tokens import make_token, make_error, ERROR


class BaseLexer:
    def __init__(self, source: str):
        self.source: str  = source
        self.pos: int     = 0          # current character index
        self.line: int    = 1
        self.col: int     = 1
        self.tokens: list = []
        self.errors: list = []

    # ── Navigation helpers ─────────────────────────────────────────────────
    def current(self) -> str:
        """Return char at current pos, or '' at EOF."""
        return self.source[self.pos] if self.pos < len(self.source) else ""

    def peek(self, offset: int = 1) -> str:
        """Return char at pos+offset without advancing."""
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else ""

    def advance(self) -> str:
        """Consume current char, update line/col tracking, return it."""
        ch = self.current()
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def match(self, expected: str) -> bool:
        """Consume next char only if it equals *expected*."""
        if self.current() == expected:
            self.advance()
            return True
        return False

    def skip_whitespace(self):
        """Skip spaces and tabs (not newlines – subclass decides)."""
        while self.current() in (" ", "\t", "\r"):
            self.advance()

    def skip_whitespace_and_newlines(self):
        while self.current() in (" ", "\t", "\r", "\n"):
            self.advance()

    def at_end(self) -> bool:
        return self.pos >= len(self.source)

    # ── Token / error helpers ──────────────────────────────────────────────
    def add_token(self, ttype: str, value: str, line: int, col: int):
        self.tokens.append(make_token(ttype, value, line, col))

    def add_error(self, message: str, value: str, line: int, col: int):
        err = make_error(message, value, line, col)
        self.errors.append(err)
        self.tokens.append(err)

    # ── Abstract entry-point ───────────────────────────────────────────────
    def tokenize(self) -> dict:
        """
        Must be overridden by subclasses.
        Returns {"tokens": [...], "errors": [...]}
        """
        raise NotImplementedError

    # ── Common string-escape reader ────────────────────────────────────────
    def _read_escape(self, start_line: int, start_col: int) -> str:
        """
        Called after the backslash has already been consumed.
        Returns the two-character escape sequence string (e.g. '\\n').
        Emits an error token for unrecognised escapes.
        """
        # Common valid escape sequences for C/C++/Python
        valid = set("nrtabfv0\\'\"?xuUN01234567")
        ch = self.current()
        if ch == "":
            self.add_error(
                "Illegal escape sequence – unterminated escape at end of file",
                "\\",
                start_line,
                start_col,
            )
            return "\\"
        if ch not in valid:
            esc = "\\" + ch
            self.add_error(
                f"Illegal escape sequence '\\{ch}' – unrecognized escape character",
                esc,
                start_line,
                start_col,
            )
            self.advance()
            return esc
        self.advance()
        return "\\" + ch
