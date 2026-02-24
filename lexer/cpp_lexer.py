"""
C++ Lexer  –  extends CLexer with:
  • All C++ keywords (including C++11/14/17/20)
  • Scope-resolution operator  ::
  • Raw string literals         R"delimiter(…)delimiter"
  • true / false / nullptr as BOOLEAN / keyword tokens
  • .*  and  ->*  operators (pointer-to-member)
  • Template-related angle-bracket nuances are left to the parser layer
  • User-defined literals  (suffix after numeric / string / char)
  • Error messages labelled [C++ Error]
"""

from .c_lexer import CLexer, C_OPERATORS
from .tokens import KEYWORD, IDENTIFIER, INTEGER, FLOAT, STRING, BOOLEAN

CPP_EXTRA_KEYWORDS = frozenset({
    # OOP / type system
    "class", "namespace", "template", "typename", "virtual", "override",
    "final", "explicit", "friend", "operator", "this", "using",
    "public", "private", "protected", "new", "delete",
    # bool
    "bool", "true", "false",
    # exceptions
    "try", "catch", "throw", "noexcept",
    # casts
    "static_cast", "dynamic_cast", "reinterpret_cast", "const_cast",
    # misc C++11+
    "nullptr", "constexpr", "consteval", "constinit",
    "decltype", "auto", "static_assert", "thread_local",
    "alignas", "alignof", "typeid",
    # C++20
    "concept", "requires", "co_await", "co_return", "co_yield",
    "export", "import", "module",
    # misc
    "inline", "mutable", "volatile",
    # wchar / char types
    "wchar_t", "char8_t", "char16_t", "char32_t",
})

# Merge with C keywords for membership testing
CPP_ALL_KEYWORDS: frozenset  # populated below

from .c_lexer import C_KEYWORDS
CPP_ALL_KEYWORDS = C_KEYWORDS | CPP_EXTRA_KEYWORDS

# C++ adds a few extra operators beyond C
CPP_EXTRA_OPS = ["->*", ".*", "::", "..."]

ALL_CPP_OPERATORS = CPP_EXTRA_OPS + C_OPERATORS  # longest-first preference


class CppLexer(CLexer):
    """Lexer for the C++ programming language."""

    def _scan_token(self):
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

        # ── raw string literal  R"tag(…)tag" ─────────────────────────────
        if ch == "R" and self.peek() == '"':
            self._read_raw_string(line, col, prefix="R")
            return

        # ── prefixed raw strings  LR"…"  u8R"…"  u16R"…"  etc. ──────────
        for pfx in ("LR", "uR", "UR", "u8R"):
            end = self.pos + len(pfx)
            if self.source[self.pos:end] == pfx and (end < len(self.source) and self.source[end] == '"'):
                for _ in pfx:
                    self.advance()
                self._read_raw_string(line, col, prefix=pfx)
                return

        # ── prefixed string / char literals ───────────────────────────────
        if ch in ("L", "u", "U") and self.peek() == '"':
            prefix = ch
            self.advance()
            self._read_string(line, col, prefix=prefix)
            return
        if ch == "u" and self.peek() == "8" and self.peek(2) == '"':
            self.advance(); self.advance()
            self._read_string(line, col, prefix="u8")
            return
        if ch in ("L", "u", "U") and self.peek() == "'":
            self.advance()
            self._read_char(line, col)
            return

        # ── regular string ────────────────────────────────────────────────
        if ch == '"':
            self._read_string(line, col)
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
            self._read_identifier_cpp(line, col)
            return

        # ── operators (C++ superset) ──────────────────────────────────────
        for op in ALL_CPP_OPERATORS:
            if self.source[self.pos: self.pos + len(op)] == op:
                for _ in op:
                    self.advance()
                from .tokens import OPERATOR
                self.add_token(OPERATOR, op, line, col)
                return

        # ── delimiters ────────────────────────────────────────────────────
        from .c_lexer import C_DELIMITERS
        from .tokens import DELIMITER
        if ch in C_DELIMITERS:
            self.advance()
            self.add_token(DELIMITER, ch, line, col)
            return

        # ── unknown ───────────────────────────────────────────────────────
        self.advance()
        self.add_error(
            f"[C++ Error] Unknown character '{ch}' (ASCII {ord(ch)})",
            ch, line, col,
        )

    # ── Identifier / keyword (C++ keyword set) ────────────────────────────
    def _read_identifier_cpp(self, line: int, col: int):
        value = ""
        while not self.at_end() and (self.current().isalnum() or self.current() == "_"):
            value += self.advance()
        if value in ("true", "false"):
            ttype = BOOLEAN
        elif value in CPP_ALL_KEYWORDS:
            ttype = KEYWORD
        else:
            ttype = IDENTIFIER
        self.add_token(ttype, value, line, col)

    # ── Raw string literal ────────────────────────────────────────────────
    def _read_raw_string(self, line: int, col: int, prefix: str = "R"):
        """Parse  R"delimiter(content)delimiter"  """
        self.advance()          # consume R
        self.advance()          # consume "
        # collect delimiter (up to 16 chars, terminated by '(')
        delimiter = ""
        while not self.at_end() and self.current() != "(" and self.current() != "\n":
            if len(delimiter) >= 16:
                self.add_error(
                    "[C++ Error] Raw string delimiter too long (max 16 characters)",
                    prefix + '"' + delimiter,
                    line, col,
                )
                return
            delimiter += self.advance()

        if self.current() != "(":
            self.add_error(
                "[C++ Error] Malformed raw string literal – expected '(' after delimiter",
                prefix + '"' + delimiter,
                line, col,
            )
            return
        self.advance()          # consume (

        closing = ")" + delimiter + '"'
        content = prefix + '"' + delimiter + "("

        while not self.at_end():
            # look for closing sequence
            end = self.pos + len(closing)
            if self.source[self.pos:end] == closing:
                content += closing
                for _ in closing:
                    self.advance()
                self.add_token(STRING, content, line, col)
                return
            content += self.advance()

        self.add_error(
            f"[C++ Error] Unterminated raw string literal – expected ')%s\"'" % delimiter,
            content, line, col,
        )

    # Override _read_number to give C++ error messages and handle UDL suffixes
    def _read_number(self, line: int, col: int):
        # Delegate to parent
        super()._read_number(line, col)
        # Replace any error messages to say [C++ Error] instead of [C Error]
        for tok in self.tokens[-3:]:
            if tok.get("type") == "ERROR":
                tok["message"] = tok.get("message", "").replace("[C Error]", "[C++ Error]")
        # Handle user-defined literal suffix (C++11): starts with _
        last = self.tokens[-1] if self.tokens else None
        if last and last["type"] in (INTEGER, FLOAT, STRING):
            if not self.at_end() and (self.current() == "_" or self.current().isalpha()):
                udl = ""
                while not self.at_end() and (self.current().isalnum() or self.current() == "_"):
                    udl += self.advance()
                last["value"] += udl
