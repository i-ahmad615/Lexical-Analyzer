"""
Python Lexer  –  fully handles:
  • Single-line comments           (# …)
  • Triple-quoted strings          (\"\"\"…\"\"\"  and  '''…''')
  • f-strings                      (f"…"  f'…'  f\"\"\"…\"\"\")
  • b-strings / r-strings / rb…
  • Regular strings                ("…"  '…')
  • Integer literals               (decimal, hex 0x…, octal 0o…, binary 0b…, with _ separators)
  • Float / complex literals
  • All Python operators inc. walrus :=, ** , //
  • All Python delimiters
  • All Python 3 keywords
  • INDENT / DEDENT tokens for significant whitespace
  • Specific [Python Error] messages
"""

from .base_lexer import BaseLexer
from .tokens import (
    KEYWORD, IDENTIFIER, INTEGER, FLOAT, STRING, F_STRING,
    OPERATOR, DELIMITER, BOOLEAN, NONE_TOKEN, NEWLINE,
    INDENT, DEDENT, ERROR
)

PY_KEYWORDS = frozenset({
    "False", "None", "True",
    "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del",
    "elif", "else", "except", "finally", "for",
    "from", "global", "if", "import", "in",
    "is", "lambda", "nonlocal", "not", "or",
    "pass", "raise", "return", "try", "while",
    "with", "yield",
})

# Longest operators first
PY_OPERATORS = [
    "**=", "//=", "<<=", ">>=",
    "->", ":=", "**", "//", "<<", ">>",
    "<=", ">=", "==", "!=", "+=", "-=",
    "*=", "/=", "%=", "&=", "|=", "^=",
    "@=",
    "+", "-", "*", "/", "%", "=", "<", ">",
    "&", "|", "^", "~", "!", ".", "@",
]

PY_DELIMITERS = set("(){}[];,:#\\")

STRING_PREFIXES = frozenset({
    "r", "R", "b", "B", "f", "F",
    "rb", "rB", "Rb", "RB", "br", "bR", "Br", "BR",
    "fr", "fR", "Fr", "FR", "rf", "rF", "Rf", "RF",
    "u", "U",
})


class PythonLexer(BaseLexer):
    """Lexer for the Python 3 programming language."""

    def tokenize(self) -> dict:
        self._indent_stack = [0]
        self._at_line_start = True
        self._paren_depth = 0          # inside () [] {} → no INDENT/DEDENT

        while not self.at_end():
            if self._at_line_start and self._paren_depth == 0:
                self._handle_indentation()
            self._scan_token()

        # Emit remaining DEDENTs
        while len(self._indent_stack) > 1:
            self._indent_stack.pop()
            self.add_token(DEDENT, "", self.line, self.col)

        return {
            "tokens": [t for t in self.tokens if t["type"] not in ("COMMENT",)],
            "errors": self.errors,
        }

    # ── Indentation ────────────────────────────────────────────────────────
    def _handle_indentation(self):
        """Process leading whitespace on a new logical line."""
        indent_col = 0
        while self.current() in (" ", "\t"):
            indent_col += 1 if self.current() == " " else 4   # tab = 4 spaces
            self.advance()

        # blank line or comment – skip
        if self.current() in ("\n", "\r", "#", ""):
            return

        current_indent = self._indent_stack[-1]
        if indent_col > current_indent:
            self._indent_stack.append(indent_col)
            self.add_token(INDENT, "", self.line, 1)
        elif indent_col < current_indent:
            while self._indent_stack and self._indent_stack[-1] > indent_col:
                self._indent_stack.pop()
                self.add_token(DEDENT, "", self.line, 1)
            if not self._indent_stack or self._indent_stack[-1] != indent_col:
                self.add_error(
                    "[Python Error] Indentation error – unindent does not match any outer indentation level",
                    "", self.line, 1,
                )
        self._at_line_start = False

    # ── Main dispatcher ────────────────────────────────────────────────────
    def _scan_token(self):
        # Newlines (skip - don't emit as tokens)
        if self.current() in ("\r", "\n"):
            if self.current() == "\r" and self.peek() == "\n":
                self.advance()
            # Don't emit NEWLINE token - just track line position
            self.advance()
            self._at_line_start = True
            return

        # Space / tab (already consumed by indentation handler if at line start)
        if self.current() in (" ", "\t"):
            self.advance()
            return

        # Line continuation
        if self.current() == "\\" and self.peek() == "\n":
            self.advance(); self.advance()
            return

        line, col = self.line, self.col
        ch = self.current()

        # ── comment ────────────────────────────────────────────────────────
        if ch == "#":
            while not self.at_end() and self.current() != "\n":
                self.advance()
            return

        # ── string / bytes / f-string prefixed ────────────────────────────
        pfx = self._try_string_prefix()
        if pfx is not None:
            self._read_string(line, col, pfx)
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
        for op in PY_OPERATORS:
            if self.source[self.pos: self.pos + len(op)] == op:
                for _ in op:
                    self.advance()
                self.add_token(OPERATOR, op, line, col)
                return

        # ── delimiters ─────────────────────────────────────────────────────
        if ch in PY_DELIMITERS:
            if ch in "([{":
                self._paren_depth += 1
            elif ch in ")]}":
                if self._paren_depth > 0:
                    self._paren_depth -= 1
                else:
                    self.add_error(
                        f"[Python Error] Unmatched closing bracket '{ch}'",
                        ch, line, col,
                    )
            self.advance()
            self.add_token(DELIMITER, ch, line, col)
            return

        # ── unknown ────────────────────────────────────────────────────────
        self.advance()
        self.add_error(
            f"[Python Error] Invalid character '{ch}' (U+{ord(ch):04X}) in source code",
            ch, line, col,
        )

    # ── String prefix detection ────────────────────────────────────────────
    def _try_string_prefix(self):
        """
        Look ahead to detect a string prefix (r, b, f, rb, …) followed by
        a quote character.  Returns the prefix string or None.
        """
        for length in (3, 2, 1):
            candidate = self.source[self.pos: self.pos + length]
            if candidate.lower() in {p.lower() for p in STRING_PREFIXES}:
                rest = self.pos + length
                if rest < len(self.source) and self.source[rest] in ('"', "'"):
                    # also check for triple quotes
                    return candidate
        if self.current() in ('"', "'"):
            return ""
        return None

    # ── String reader ──────────────────────────────────────────────────────
    def _read_string(self, line: int, col: int, prefix: str):
        # Consume prefix chars
        for _ in prefix:
            self.advance()

        quote_char = self.current()
        if quote_char not in ('"', "'"):
            self.add_error(
                "[Python Error] Expected opening quote for string literal",
                prefix, line, col,
            )
            return

        # Triple or single?
        triple = (
            self.pos + 2 < len(self.source)
            and self.source[self.pos + 1] == quote_char
            and self.source[self.pos + 2] == quote_char
        )
        if triple:
            self.advance(); self.advance(); self.advance()
            closing = quote_char * 3
        else:
            self.advance()
            closing = quote_char

        is_raw    = "r" in prefix.lower()
        is_fstring = "f" in prefix.lower()
        value = prefix + (quote_char * 3 if triple else quote_char)

        while not self.at_end():
            # Check closing
            end = self.pos + len(closing)
            if self.source[self.pos:end] == closing:
                value += closing
                for _ in closing:
                    self.advance()
                ttype = F_STRING if is_fstring else STRING
                self.add_token(ttype, value, line, col)
                return

            ch = self.current()
            if not triple and ch in ("\n", "\r"):
                self.add_error(
                    f"[Python Error] Unterminated string literal (single-line string cannot span multiple lines)",
                    value, line, col,
                )
                return

            if ch == "\\" and not is_raw:
                self.advance()
                value += self._read_escape(self.line, self.col)
                continue

            value += self.advance()

        self.add_error(
            f"[Python Error] Unterminated {'triple-quoted ' if triple else ''}string literal – reached end of file",
            value, line, col,
        )

    # ── Number ────────────────────────────────────────────────────────────
    def _read_number(self, line: int, col: int):
        value = ""
        is_float   = False
        is_complex = False

        # Hex
        if self.current() == "0" and self.peek() in ("x", "X"):
            value += self.advance() + self.advance()
            if self.current() not in "0123456789abcdefABCDEF_":
                self.add_error(
                    "[Python Error] Invalid hexadecimal literal – no digits after '0x'",
                    value, line, col,
                )
                return
            while self.current() in "0123456789abcdefABCDEF_":
                value += self.advance()
            self.add_token(INTEGER, value, line, col)
            return

        # Binary
        if self.current() == "0" and self.peek() in ("b", "B"):
            value += self.advance() + self.advance()
            if self.current() not in "01_":
                self.add_error(
                    "[Python Error] Invalid binary literal – no digits after '0b'",
                    value, line, col,
                )
                return
            while self.current() in "01_":
                value += self.advance()
            self.add_token(INTEGER, value, line, col)
            return

        # Octal
        if self.current() == "0" and self.peek() in ("o", "O"):
            value += self.advance() + self.advance()
            if self.current() not in "01234567_":
                self.add_error(
                    "[Python Error] Invalid octal literal – no digits after '0o'",
                    value, line, col,
                )
                return
            while self.current() in "01234567_":
                value += self.advance()
            self.add_token(INTEGER, value, line, col)
            return

        # Decimal / float
        while self.current().isdigit() or self.current() == "_":
            value += self.advance()

        if self.current() == "." and self.peek() != ".":
            is_float = True
            value += self.advance()
            while self.current().isdigit() or self.current() == "_":
                value += self.advance()

        if self.current() in ("e", "E"):
            is_float = True
            value += self.advance()
            if self.current() in ("+", "-"):
                value += self.advance()
            if not self.current().isdigit():
                self.add_error(
                    "[Python Error] Malformed float literal – expected digits after exponent 'e'",
                    value, line, col,
                )
                return
            while self.current().isdigit() or self.current() == "_":
                value += self.advance()

        # Complex  j / J
        if self.current() in ("j", "J"):
            value += self.advance()
            is_complex = True

        # Leading zero error (Python 3 disallows 0123 – must be 0o123)
        if not is_float and not is_complex and value.startswith("0") and len(value) > 1 and value[1].isdigit():
            self.add_error(
                f"[Python Error] Invalid integer literal '{value}' – leading zeros are not allowed in Python 3 "
                "(use 0o for octal, 0x for hex, 0b for binary)",
                value, line, col,
            )
            return

        # Check for numeric overflow
        if not is_complex:
            try:
                if is_float:
                    float(value.replace('_', ''))
                else:
                    int(value.replace('_', ''))
            except (ValueError, OverflowError):
                self.add_error(
                    f"[Python Error] Numeric overflow – constant value too large for internal representation",
                    value, line, col,
                )
                return

        ttype = FLOAT if (is_float or is_complex) else INTEGER
        self.add_token(ttype, value, line, col)

    # ── Identifier / keyword ──────────────────────────────────────────────
    def _read_identifier(self, line: int, col: int):
        value = ""
        while not self.at_end() and (self.current().isalnum() or self.current() == "_"):
            value += self.advance()

        if value in ("True", "False"):
            ttype = BOOLEAN
        elif value == "None":
            ttype = NONE_TOKEN
        elif value in PY_KEYWORDS:
            ttype = KEYWORD
        else:
            ttype = IDENTIFIER
        self.add_token(ttype, value, line, col)
