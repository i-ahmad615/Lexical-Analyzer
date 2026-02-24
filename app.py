"""
app.py  –  Flask backend for the Lexical Analyzer

Endpoints
─────────
GET  /                    Serve the frontend SPA (index.html)
POST /api/analyze         Tokenize source code
POST /api/detect          Language auto-detection only
GET  /api/languages       Return list of supported languages
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

from lexer import CLexer, CppLexer, PythonLexer, check_c_syntax, check_python_syntax
from lexer.detector import LanguageDetector

# ── App Setup ──────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TMPL_DIR   = os.path.join(BASE_DIR, "templates")

app = Flask(
    __name__,
    static_folder   = STATIC_DIR,
    template_folder = TMPL_DIR,
)
CORS(app)   # Allow cross-origin requests (useful when frontend is on a CDN)

# ── Language registry ──────────────────────────────────────────────────────
LEXER_MAP = {
    "c":      CLexer,
    "cpp":    CppLexer,
    "python": PythonLexer,
    "py":     PythonLexer,   # alias
}

LANGUAGE_DISPLAY = {
    "c":      {"label": "C",       "icon": "🔵"},
    "cpp":    {"label": "C++",     "icon": "🟣"},
    "python": {"label": "Python",  "icon": "🟡"},
}


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(TMPL_DIR, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.route("/api/languages", methods=["GET"])
def get_languages():
    """Return the list of supported languages."""
    return jsonify({
        "languages": [
            {"id": lang, **meta}
            for lang, meta in LANGUAGE_DISPLAY.items()
        ]
    })


@app.route("/api/detect", methods=["POST"])
def detect_language():
    """
    Body: { "code": "..." }
    Returns: { "detected_language": "...", "confidence": "...", "scores": {...} }
    """
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")

    if not code.strip():
        return jsonify({"error": "No source code provided"}), 400

    result = LanguageDetector.detect_and_explain(code)
    return jsonify(result)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Body:
        {
          "code":     "<source code>",
          "language": "c" | "cpp" | "python"   (optional – auto-detected if absent)
        }

    Returns:
        {
          "language":   "c" | "cpp" | "python",
          "confidence": "high" | "medium" | "low" | "none",
          "tokens":     [ { type, value, line, column }, … ],
          "errors":     [ { type, value, line, column, message }, … ],
          "stats":      { total, by_type: { TYPE: count }, error_count }
        }
    """
    data = request.get_json(silent=True) or {}
    code     = data.get("code", "")
    language = data.get("language", "").lower().strip()

    # Normalise alias
    if language == "py":
        language = "python"

    if not code.strip():
        return jsonify({"error": "No source code provided"}), 400

    # Auto-detect if not supplied
    confidence = "user-specified"
    if not language or language not in LEXER_MAP:
        language, confidence = LanguageDetector.detect(code)
        if language == "unknown":
            return jsonify({
                "error": (
                    "Could not auto-detect the programming language. "
                    "Please select C, C++, or Python explicitly."
                ),
                "scores": LanguageDetector.detect_and_explain(code)["scores"],
            }), 422

    LexerClass = LEXER_MAP[language]
    result     = LexerClass(code).tokenize()

    tokens = result["tokens"]
    errors = result["errors"][:]

    # ── Syntax checking (post-tokenization structural rules) ───────────────
    try:
        if language in ("c", "cpp"):
            lang_label = "C" if language == "c" else "C++"
            syntax_errors = check_c_syntax(tokens, lang=lang_label)
        else:
            syntax_errors = check_python_syntax(tokens)
        # Merge syntax errors; avoid duplicating errors already found by lexer
        existing_positions = {(e["line"], e["column"]) for e in errors}
        for se in syntax_errors:
            if (se["line"], se["column"]) not in existing_positions:
                errors.append(se)
    except Exception:
        pass  # never let the checker crash the whole response

    # Sort all errors by line then column
    errors.sort(key=lambda e: (e["line"], e["column"]))

    # ── Statistics ─────────────────────────────────────────────────────────
    by_type: dict[str, int] = {}
    for tok in tokens:
        by_type[tok["type"]] = by_type.get(tok["type"], 0) + 1

    stats = {
        "total":       len(tokens),
        "by_type":     by_type,
        "error_count": len(errors),
    }

    return jsonify({
        "language":   language,
        "confidence": confidence,
        "tokens":     tokens,
        "errors":     errors,
        "stats":      stats,
    })


# ── Dev-server entry-point ─────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    print(f"  Lexical Analyzer API  →  http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
