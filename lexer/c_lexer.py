"""
C Lexer  –  fully handles:
  • Preprocessor directives  (#include, #define, #ifdef …)
  • Single-line comments      (//)
  • Multi-line comments       (/* … */)
  • String literals           ("…") with escape checking
  • Character literals        ('…') with escape checking
  • Integer literals          (decimal, hex 0x…, octal 0…, binary-C23 0b…)
  • Float / double literals   (with optional suffix f/F/l/L)
  • All C operators and compound assignments
  • All C delimiters
  • All C89 / C99 / C11 keywords
  • Error messages specific to C
"""

from .base_lexer import BaseLexer
from .tokens import (
    KEYWORD, IDENTIFIER, INTEGER, FLOAT, STRING, CHAR,
    OPERATOR, DELIMITER, PREPROCESSOR, ERROR
)

C_KEYWORDS = frozenset({
    "auto", "break", "case", "char", "const", "continue", "default",
    "do", "double", "else", "enum", "extern", "float", "for", "goto",
    "if", "inline", "int", "long", "register", "restrict", "return",
    "short", "signed", "sizeof", "static", "struct", "switch", "typedef",
    "union", "unsigned", "void", "volatile", "while",
    # C99/C11 additions
    "_Alignas", "_Alignof", "_Atomic", "_Bool", "_Complex",
    "_Generic", "_Imaginary", "_Noreturn", "_Static_assert",
    "_Thread_local",
})

# C operators sorted longest-first so the scanner always matches
# the longest possible token.
C_OPERATORS = [
    "<<=", ">>=",                                          # 3-char
    "->", "++", "--", "<<", ">>", "<=", ">=", "==", "!=", # 2-char
    "&&", "||", "+=", "-=", "*=", "/=", "%=",
    "&=", "|=", "^=",
    "+", "-", "*", "/", "%", "=", "<", ">",               # 1-char
    "&", "|", "^", "~", "!", ".",
]

C_DELIMITERS = set("(){};,[]:#")

VALID_STRING_SUFFIXES = {"", "L", "u", "U", "u8"}


class CLexer(BaseLexer):
    """Lexer for the C programming language."""

    def tokenize(self) -> dict:
        while not self.at_end():
            self._scan_token()
        return {
            "tokens": [t for t in self.tokens if t["type"] != "COMMENT"],
            "errors": self.errors,
        }

    # ── Main dispatcher ────────────────────────────────────────────────────
    def _scan_token(self):
        # Skip whitespace / newlines (C is free-form)
        if self.current() in (" ", "\t", "\r", "\n"):
            self.advance()
            return

        line, col = self.line, self.col
        ch = self.current()

        # ── preprocessor ──────────────────────────────────────────────────
        if ch == "#":
            self._read_preprocessor(line, col)
            return

        # ── line comment ──────────────────────────────────────────────────
        if ch == "/" and self.peek() == "/":
            self._read_line_comment()
            return

        # ── block comment ─────────────────────────────────────────────────
        if ch == "/" and self.peek() == "*":
            self._read_block_comment(line, col)
            return

        # ── string literal ────────────────────────────────────────────────
        if ch == '"':
            self._read_string(line, col)
            return

        # ── wide / UTF prefixed string  L"…"  u"…"  U"…"  u8"…" ─────────
        if ch in ("L", "u", "U") and self.peek() == '"':
            prefix = ch
            self.advance()
            self._read_string(line, col, prefix=prefix)
            return
        if ch == "u" and self.peek() == "8" and self.peek(2) == '"':
            self.advance(); self.advance()
            self._read_string(line, col, prefix="u8")
            return

        # ── wide char  L'…' ───────────────────────────────────────────────
        if ch in ("L", "u", "U") and self.peek() == "'":
            self.advance()
            self._read_char(line, col)
            return

        # ── char literal ──────────────────────────────────────────────────
        if ch == "'":
            self._read_char(line, col)
            return

        # ── numbers ───────────────────────────────────────────────────────
        if ch.isdigit() or (ch == "." and self.peek().isdigit()):
            self._read_number(line, col)
            return

        # ── identifiers / keywords ────────────────────────────────────────
        if ch.isalpha() or ch == "_":
            self._read_identifier(line, col)
            return

        # ── operators ─────────────────────────────────────────────────────
        for op in C_OPERATORS:
            if self.source[self.pos: self.pos + len(op)] == op:
                for _ in op:
                    self.advance()
                self.add_token(OPERATOR, op, line, col)
                return

        # ── delimiters ────────────────────────────────────────────────────
        if ch in C_DELIMITERS:
            self.advance()
            self.add_token(DELIMITER, ch, line, col)
            return

        # ── unknown character ─────────────────────────────────────────────
        self.advance()
        self.add_error(
            f"[C Error] Unknown character '{ch}' (ASCII {ord(ch)})",
            ch, line, col,
        )

    # ── Preprocessor ──────────────────────────────────────────────────────
    def _read_preprocessor(self, line: int, col: int):
        text = ""
        while not self.at_end() and self.current() != "\n":
            # Support line-continuation
            if self.current() == "\\" and self.peek() == "\n":
                self.advance(); self.advance()
                continue
            text += self.advance()
        self.add_token(PREPROCESSOR, text.strip(), line, col)

    # ── Comments ──────────────────────────────────────────────────────────
    def _read_line_comment(self):
        while not self.at_end() and self.current() != "\n":
            self.advance()

    def _read_block_comment(self, line: int, col: int):
        self.advance(); self.advance()          # consume /*
        while not self.at_end():
            if self.current() == "*" and self.peek() == "/":
                self.advance(); self.advance()  # consume */
                return
            self.advance()
        self.add_error(
            "[C Error] Unterminated block comment – missing closing '*/'",
            "/*", line, col,
        )

    # ── String literal ────────────────────────────────────────────────────
    def _read_string(self, line: int, col: int, prefix: str = ""):
        self.advance()                          # consume opening "
        value = prefix + '"'
        while not self.at_end():
            ch = self.current()
            if ch == "\n":
                self.add_error(
                    "[C Error] Unterminated string literal – newline inside string",
                    value, line, col,
                )
                return
            if ch == "\\":
                self.advance()
                value += self._read_escape(self.line, self.col)
                continue
            if ch == '"':
                value += self.advance()
                # optional suffix  e.g. nothing in standard C for strings
                self.add_token(STRING, value, line, col)
                return
            value += self.advance()
        self.add_error(
            "[C Error] Unterminated string literal – reached end of file",
            value, line, col,
        )

    # ── Char literal ──────────────────────────────────────────────────────
    def _read_char(self, line: int, col: int):
        self.advance()                          # consume opening '
        value = "'"
        char_count = 0
        while not self.at_end():
            ch = self.current()
            if ch == "\n":
                self.add_error(
                    "[C Error] Unterminated character literal – newline inside char",
                    value, line, col,
                )
                return
            if ch == "\\":
                self.advance()
                value += self._read_escape(self.line, self.col)
                char_count += 1
                continue
            if ch == "'":
                value += self.advance()
                if char_count == 0:
                    self.add_error(
                        "[C Error] Empty character literal ''",
                        value, line, col,
                    )
                elif char_count > 1:
                    self.add_error(
                        f"[C Error] Multi-character character literal '{value}' "
                        "(implementation-defined behavior)",
                        value, line, col,
                    )
                else:
                    self.add_token(CHAR, value, line, col)
                return
            value += self.advance()
            char_count += 1
        self.add_error(
            "[C Error] Unterminated character literal – reached end of file",
            value, line, col,
        )

    # ── Number ────────────────────────────────────────────────────────────
    def _read_number(self, line: int, col: int):
        value = ""
        is_float = False
        decimal_count = 0

        # Hexadecimal
        if self.current() == "0" and self.peek() in ("x", "X"):
            value += self.advance() + self.advance()
            if not (self.current() in "0123456789abcdefABCDEF"):
                self.add_error(
                    "[C Error] Invalid hex literal – no digits after '0x'",
                    value, line, col,
                )
                return
            while self.current() in "0123456789abcdefABCDEF_":
                value += self.advance()
            # hex float (C99)
            if self.current() == ".":
                is_float = True
                decimal_count += 1
                value += self.advance()
                # Check for multiple decimal points
                if self.current() == ".":
                    self.add_error(
                        "[C Error] Malformed numeric literal – multiple decimal points",
                        value, line, col,
                    )
                    return
                while self.current() in "0123456789abcdefABCDEF_":
                    value += self.advance()
            if self.current() in ("p", "P"):
                is_float = True
                value += self.advance()
                if self.current() in ("+", "-"):
                    value += self.advance()
                while self.current().isdigit():
                    value += self.advance()
            # suffix
            while self.current() in "uUlLfF":
                value += self.advance()
            self.add_token(FLOAT if is_float else INTEGER, value, line, col)
            return

        # Octal / Binary (C23 0b…)
        if self.current() == "0" and self.peek() in ("b", "B"):
            value += self.advance() + self.advance()
            if self.current() not in "01":
                self.add_error(
                    "[C Error] Invalid binary literal – no digits after '0b'",
                    value, line, col,
                )
                return
            while self.current() in "01_":
                value += self.advance()
            while self.current() in "uUlL":
                value += self.advance()
            self.add_token(INTEGER, value, line, col)
            return

        # Decimal / Float / Octal
        while self.current().isdigit() or self.current() == "_":
            value += self.advance()

        if self.current() == "." and self.peek() != ".":
            is_float = True
            decimal_count += 1
            value += self.advance()
            # Check for multiple decimal points
            if self.current() == "." and self.peek().isdigit():
                self.add_error(
                    "[C Error] Malformed numeric literal – multiple decimal points",
                    value, line, col,
                )
                return
            while self.current().isdigit():
                value += self.advance()

        if self.current() in ("e", "E"):
            is_float = True
            value += self.advance()
            if self.current() in ("+", "-"):
                value += self.advance()
            if not self.current().isdigit():
                self.add_error(
                    "[C Error] Malformed float literal – expected digits after exponent",
                    value, line, col,
                )
                return
            while self.current().isdigit():
                value += self.advance()

        # suffix  f/F/l/L/u/U
        while self.current() in "uUlLfF":
            suffix = self.current()
            if suffix in ("f", "F"):
                is_float = True
            value += self.advance()

        # Octal validation
        if not is_float and value.startswith("0") and len(value) > 1:
            if any(d in value for d in "89"):
                self.add_error(
                    f"[C Error] Invalid octal literal '{value}' – digits 8 or 9 are not valid in octal",
                    value, line, col,
                )
                return

        self.add_token(FLOAT if is_float else INTEGER, value, line, col)

    # ── Identifier / keyword ──────────────────────────────────────────────
    def _read_identifier(self, line: int, col: int):
        value = ""
        while not self.at_end() and (self.current().isalnum() or self.current() == "_"):
            value += self.advance()
        ttype = KEYWORD if value in C_KEYWORDS else IDENTIFIER
        self.add_token(ttype, value, line, col)
