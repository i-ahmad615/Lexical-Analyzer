"""
syntax_checker.py  –  Post-tokenization syntax rule checker.

Operates on the already-produced token list to detect common structural
errors that a lexer alone cannot catch:

C / C++:
  • Missing semicolons at end of statements
  • Unmatched / unclosed  { ( [
  • Extra closing         } ) ]

Python:
  • Missing colon after compound-statement headers  (if/for/while/def/class …)
  • Unmatched / unclosed  ( [ {
  • Extra closing          ) ] }

Each error dict matches the format used everywhere else:
  { "type": "ERROR", "value": ..., "line": n, "column": n, "message": "..." }
"""

from .tokens import make_error, KEYWORD, OPERATOR, DELIMITER, PREPROCESSOR

# ── helpers ────────────────────────────────────────────────────────────────

def _err(msg, value, line, col):
    return make_error(msg, value, line, col)


# ══════════════════════════════════════════════════════════════════════════
#  C / C++
# ══════════════════════════════════════════════════════════════════════════

# Token types that can legitimately END a statement
_STMT_END_TYPES = {"IDENTIFIER", "INTEGER", "FLOAT", "STRING", "CHAR",
                   "BOOLEAN", "NONE"}

# Delimiter values that, when last on a line, may end a statement
_STMT_END_DELIMS = {")", "]"}

# Operator values that end a statement  (post-increment / post-decrement)
_STMT_END_OPS = {"++", "--"}

# Keywords that START a new line but do NOT themselves need a semicolon
# before them (so the previous line without `;` is fine if it's the
# header of a block-statement).
_BLOCK_STARTERS = {
    "if", "else", "for", "while", "do", "switch",
    "try", "catch", "finally",
    # C++ class / namespace / struct headers
    "class", "namespace", "struct", "union", "enum",
    "public", "private", "protected",
    # preprocessor-like tokens are already their own type
}

# Lines whose last real token is one of these do NOT need a semicolon.
_NO_SEMI_LAST_KW = {
    "if", "else", "for", "while", "do", "switch",
    "class", "namespace", "struct", "union", "enum",
    "try", "catch", "finally",
    "public", "private", "protected",
    "default",
}

# Keywords that DO need a semicolon after their line
_NEEDS_SEMI_KW = {"return", "break", "continue", "goto", "throw", "delete"}


def check_c_syntax(tokens: list, lang: str = "C") -> list:
    """
    Check token stream for C / C++ structural errors.
    Returns a list of error dicts.
    """
    errors = []
    prefix = f"[{lang} Error]"

    # ── 1. Bracket matching ────────────────────────────────────────────
    stack = []          # each entry: (char, line, col)
    pairs = {")": "(", "]": "[", "}": "{"}
    openers = set("([{")
    closers = set(")]}")

    for tok in tokens:
        if tok["type"] == "ERROR":
            continue
        if tok["type"] == DELIMITER:
            v = tok["value"]
            if v in openers:
                stack.append((v, tok["line"], tok["column"]))
            elif v in closers:
                expected = pairs[v]
                if not stack:
                    errors.append(_err(
                        f"{prefix} Unexpected '{v}' – no matching '{expected}'",
                        v, tok["line"], tok["column"],
                    ))
                elif stack[-1][0] != expected:
                    op, ol, oc = stack[-1]
                    errors.append(_err(
                        f"{prefix} Mismatched bracket: '{v}' at line {tok['line']} "
                        f"does not close '{op}' opened at line {ol}",
                        v, tok["line"], tok["column"],
                    ))
                    stack.pop()
                else:
                    stack.pop()

    for (ch, line, col) in stack:
        errors.append(_err(
            f"{prefix} Unclosed '{ch}' – missing matching closing bracket",
            ch, line, col,
        ))

    # ── 2. Missing semicolons ──────────────────────────────────────────
    # Group tokens by line, ignore preprocessor lines and blank lines.
    lines_map: dict[int, list] = {}
    for tok in tokens:
        if tok["type"] == "ERROR":
            continue
        ln = tok["line"]
        lines_map.setdefault(ln, []).append(tok)

    # Track brace depth so we only check inside function bodies.
    # (Declarations at file scope also need `;` but outer-level `}`
    #  closing a function is fine.)
    # We use a simple pass: brace_depth ≥ 0 for everything.

    # Build ordered line list
    sorted_lines = sorted(lines_map.keys())

    # We need to know brace depth per line — build a running total
    brace_depth = 0
    brace_by_line: dict[int, int] = {}   # depth ENTERING that line
    for ln in sorted_lines:
        brace_by_line[ln] = brace_depth
        for tok in lines_map[ln]:
            if tok["type"] == DELIMITER:
                if tok["value"] == "{":
                    brace_depth += 1
                elif tok["value"] == "}":
                    brace_depth = max(0, brace_depth - 1)

    for ln in sorted_lines:
        toks = lines_map[ln]
        if not toks:
            continue

        # Skip preprocessor lines
        if toks[0]["type"] == PREPROCESSOR:
            continue

        # Find the last meaningful token on this line
        last = toks[-1]

        # Line ends with `;` or `{` or `}` or `,` → fine
        if last["type"] == DELIMITER and last["value"] in (";", "{", "}", ",", ":"):
            continue

        # Line ends with a line-continuation operator or block-header keyword
        if last["type"] == KEYWORD and last["value"] in _NO_SEMI_LAST_KW:
            continue

        # Line ends with an operator that bridges to next line (e.g.  +  &&  =)
        if last["type"] == OPERATOR and last["value"] not in _STMT_END_OPS:
            continue

        # Line ends with `//` comment? (shouldn't happen – comments stripped)

        # Now decide if this line SHOULD end with `;`
        needs_semi = False

        if last["type"] in _STMT_END_TYPES:
            needs_semi = True
        elif last["type"] == DELIMITER and last["value"] in _STMT_END_DELIMS:
            # `)` could be end of function call or end of `if/for/while (…)`
            # Find the first token on this line to check
            first_kw = None
            for t in toks:
                if t["type"] == KEYWORD:
                    first_kw = t["value"]
                    break
            if first_kw in _NO_SEMI_LAST_KW:
                needs_semi = False
            else:
                needs_semi = True
        elif last["type"] == OPERATOR and last["value"] in _STMT_END_OPS:
            needs_semi = True
        elif last["type"] == KEYWORD and last["value"] in _NEEDS_SEMI_KW:
            needs_semi = True

        if needs_semi and brace_by_line.get(ln, 0) > 0:
            errors.append(_err(
                f"{prefix} Missing semicolon ';' at end of statement",
                last["value"], ln, last["column"] + len(str(last["value"])),
            ))

    return errors


# ══════════════════════════════════════════════════════════════════════════
#  Python
# ══════════════════════════════════════════════════════════════════════════

# Keywords that introduce a compound statement and MUST be followed by `:`
# at the END of that logical line.
_PY_COMPOUND_KW = {
    "if", "elif", "else", "for", "while",
    "def", "class", "with", "try", "except",
    "finally", "async",
}

# `else`, `try`, `finally`, `except` do not always have an expression
# but still need a colon.
_PY_COLON_REQUIRED = _PY_COMPOUND_KW


def check_python_syntax(tokens: list) -> list:
    """
    Check token stream for Python structural errors.
    Returns list of error dicts.
    """
    errors = []
    prefix = "[Python Error]"

    # ── 1. Bracket matching ────────────────────────────────────────────
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    openers = set("([{")
    closers = set(")]}")

    for tok in tokens:
        if tok["type"] == "ERROR":
            continue
        if tok["type"] == DELIMITER:
            v = tok["value"]
            if v in openers:
                stack.append((v, tok["line"], tok["column"]))
            elif v in closers:
                expected = pairs[v]
                if not stack:
                    errors.append(_err(
                        f"{prefix} Unexpected '{v}' – no matching '{expected}'",
                        v, tok["line"], tok["column"],
                    ))
                elif stack[-1][0] != expected:
                    op, ol, oc = stack[-1]
                    errors.append(_err(
                        f"{prefix} Mismatched bracket: '{v}' at line {tok['line']} "
                        f"does not close '{op}' opened at line {ol}",
                        v, tok["line"], tok["column"],
                    ))
                    stack.pop()
                else:
                    stack.pop()

    for (ch, line, col) in stack:
        errors.append(_err(
            f"{prefix} Unclosed '{ch}' – missing matching closing bracket",
            ch, line, col,
        ))

    # ── 2. Missing colon after compound-statement headers ──────────────
    # Strategy: group tokens by logical line using line numbers.
    # Inside brackets (paren_depth > 0), lines are joined.

    logical_lines: list[list] = []
    current: list = []
    p_depth = 0
    last_line = None

    for tok in tokens:
        if tok["type"] in ("INDENT", "DEDENT"):
            continue
        if tok["type"] == "ERROR":
            current.append(tok)
            continue
        
        # Detect logical line breaks BEFORE appending the token
        if last_line is not None and tok["line"] != last_line and p_depth == 0:
            if current:
                logical_lines.append(current)
                current = []
        
        # Now append the token to current line
        current.append(tok)
        
        # Track bracket depth
        if tok["type"] == DELIMITER and tok["value"] in "([{":
            p_depth += 1
        elif tok["type"] == DELIMITER and tok["value"] in ")]}":
            p_depth = max(0, p_depth - 1)
        
        last_line = tok["line"]

    if current:
        logical_lines.append(current)

    for line_toks in logical_lines:
        # Filter out ERROR tokens for analysis
        real = [t for t in line_toks if t["type"] != "ERROR"]
        if not real:
            continue

        first = real[0]
        last  = real[-1]

        # Does this logical line start with a compound-statement keyword?
        if first["type"] != KEYWORD or first["value"] not in _PY_COLON_REQUIRED:
            continue

        # The line should end with `:` (a DELIMITER)
        if last["type"] == DELIMITER and last["value"] == ":":
            continue

        # If the last token is already an error, skip (already reported)
        if last["type"] == "ERROR":
            continue

        kw = first["value"]
        errors.append(_err(
            f"{prefix} Missing colon ':' after '{kw}' statement header",
            kw, first["line"], last["column"] + len(str(last["value"])),
        ))

    return errors
