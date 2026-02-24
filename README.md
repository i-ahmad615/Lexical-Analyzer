# Lexical Analyzer

A fully-featured browser-based **Lexical Analyzer** that tokenizes C, C++, and Python source code with:

- ✅ **Language auto-detection** (heuristic scoring) + manual language selection
- ✅ **Comment elimination** before tokenization
- ✅ **Language-specific error messages** with line & column information
- ✅ **Rich token categorization** (keywords, identifiers, literals, operators, delimiters, preprocessor, etc.)
- ✅ **Responsive UI** works on both desktop and mobile
- ✅ **Stats & chart** showing token-type distribution

---

## Project Structure

```
analyzer/
├── app.py                  # Flask server – API + static file serving
├── requirements.txt        # Python dependencies
│
├── lexer/
│   ├── __init__.py
│   ├── tokens.py           # Token type constants & factory helpers
│   ├── base_lexer.py       # Shared cursor / navigation helpers
│   ├── c_lexer.py          # C lexer (C89 / C99 / C11)
│   ├── cpp_lexer.py        # C++ lexer (C++11 to C++20)
│   ├── python_lexer.py     # Python 3 lexer
│   └── detector.py         # Language auto-detector
│
├── templates/
│   └── index.html          # Single-page frontend
│
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```

---

## Local Setup

### Prerequisites
- Python ≥ 3.10

### Install & Run

```bash
# 1. Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the development server
python app.py
```

Open your browser at **http://127.0.0.1:5000**

---

## API Reference

### `POST /api/analyze`

**Request body:**
```json
{
  "code":     "<source code string>",
  "language": "c" | "cpp" | "python"   // optional – auto-detected if omitted
}
```

**Response:**
```json
{
  "language":   "cpp",
  "confidence": "high",
  "tokens": [
    { "type": "PREPROCESSOR", "value": "#include <iostream>", "line": 1, "column": 1 },
    ...
  ],
  "errors": [
    { "type": "ERROR", "value": "089", "line": 14, "column": 15, "message": "[C Error] Invalid octal literal …" }
  ],
  "stats": {
    "total": 47,
    "by_type": { "KEYWORD": 8, "IDENTIFIER": 12, ... },
    "error_count": 1
  }
}
```

### `POST /api/detect`

Quick language detection without full tokenization.

**Request:** `{ "code": "..." }`  
**Response:** `{ "detected_language": "python", "confidence": "high", "scores": { "c": 2, "cpp": 2, "python": 15 } }`

### `GET /api/languages`

Returns the list of supported languages.

---

## Deployment Options

### Option 1 – Render.com ⭐ (recommended, free tier)

1. Push this project to a **GitHub repository**
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your repo
4. Set:
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app`
5. Deploy → Render gives you a free `.onrender.com` URL

### Option 2 – Railway.app

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub**
3. Railway auto-detects Python and runs `gunicorn app:app`
4. Set environment variable `PORT` if needed (Railway injects it automatically)

### Option 3 – PythonAnywhere (free tier)

1. Sign up at [pythonanywhere.com](https://www.pythonanywhere.com)
2. Upload files via Files tab or `git clone`
3. Configure a **WSGI** app pointing to `app:app`
4. Done – you get a free `<username>.pythonanywhere.com` subdomain

### Option 4 – Vercel (frontend) + Railway (backend)

If you want a CDN-hosted frontend:
1. Deploy the backend to Railway (steps above)
2. Deploy only `templates/` + `static/` to Vercel as a static site
3. Change `API_BASE` in `app.js` to your Railway URL

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Run analysis |
| `Tab` in editor | Insert 4 spaces |

---

## Supported Token Types

| Type | Description |
|------|-------------|
| `KEYWORD` | Language reserved word |
| `IDENTIFIER` | Variable / function name |
| `INTEGER` | Integer literal (dec/hex/oct/bin) |
| `FLOAT` | Floating-point literal |
| `STRING` | String literal |
| `CHAR` | Character literal (C/C++) |
| `F_STRING` | f-string (Python) |
| `OPERATOR` | Arithmetic, logical, bitwise operators |
| `DELIMITER` | Brackets, semicolons, commas, etc. |
| `PREPROCESSOR` | `#include`, `#define`, etc. (C/C++) |
| `BOOLEAN` | `true`/`false` / `True`/`False` |
| `NONE` | Python `None` |
| `NEWLINE` | Significant newline (Python) |
| `INDENT` | Indentation increase (Python) |
| `DEDENT` | Indentation decrease (Python) |
| `ERROR` | Lexical error with message |
