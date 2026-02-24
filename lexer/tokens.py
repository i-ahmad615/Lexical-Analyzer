"""
Token type definitions shared across all lexers.
Each token is represented as a dict:
  {
    "type"    : str   – token category,
    "value"   : str   – raw lexeme,
    "line"    : int   – 1-based line number,
    "column"  : int   – 1-based column number,
  }

Error entries carry an additional "message" key.
"""

# ── Generic ────────────────────────────────────────────────────────────────
KEYWORD        = "KEYWORD"
IDENTIFIER     = "IDENTIFIER"
INTEGER        = "INTEGER"
FLOAT          = "FLOAT"
STRING         = "STRING"
CHAR           = "CHAR"
OPERATOR       = "OPERATOR"
DELIMITER      = "DELIMITER"
COMMENT        = "COMMENT"          # kept internally; stripped before output
PREPROCESSOR   = "PREPROCESSOR"     # C / C++ only  (#include, #define …)
BOOLEAN        = "BOOLEAN"          # Python True/False, C++ true/false
NONE_TOKEN     = "NONE"             # Python None
NEWLINE        = "NEWLINE"          # Python significant newline
INDENT         = "INDENT"           # Python indentation increase
DEDENT         = "DEDENT"           # Python indentation decrease
F_STRING        = "F_STRING"         # Python f-string

# ── Error ──────────────────────────────────────────────────────────────────
ERROR          = "ERROR"


def make_token(ttype: str, value: str, line: int, col: int) -> dict:
    return {"type": ttype, "value": value, "line": line, "column": col}


def make_error(message: str, value: str, line: int, col: int) -> dict:
    return {
        "type": ERROR,
        "value": value,
        "line": line,
        "column": col,
        "message": message,
    }
