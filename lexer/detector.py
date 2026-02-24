"""
Language Detector  –  heuristic-based scoring system.

Each language accumulates a score from pattern matches.
The language with the highest score wins.  A minimum threshold
ensures "unknown" is returned when no language matches well.

Languages supported: c, cpp, python
"""

import re
from typing import Optional


# ── Pattern sets ──────────────────────────────────────────────────────────

# Patterns that STRONGLY indicate a specific language
_CPP_STRONG = [
    r"\bclass\b",
    r"\bnamespace\b",
    r"\btemplate\s*<",
    r"\bcout\b",
    r"\bcin\b",
    r"\bstd\s*::",
    r"\bnullptr\b",
    r"\bpublic\s*:",
    r"\bprivate\s*:",
    r"\bprotected\s*:",
    r"#include\s*<[^>]+>",     # #include <iostream> etc.
    r"\bnew\s+\w",
    r"\bdelete\s+\w",
    r"\boverride\b",
    r"\bvirtual\b",
    r"\bconstexpr\b",
    r"\bauto\s+\w+\s*=",
    r"->",
    r"::",
    r"\[\[",                   # attributes [[nodiscard]]
]

_C_STRONG = [
    r"#include\s*<stdio\.h>",
    r"#include\s*<stdlib\.h>",
    r"#include\s*<string\.h>",
    r"#include\s*<math\.h>",
    r"\bprintf\s*\(",
    r"\bscanf\s*\(",
    r"\bmalloc\s*\(",
    r"\bfree\s*\(",
    r"\bstruct\s+\w+\s*{",
    r"\btypedef\s+struct\b",
    r"\bvoid\s+\w+\s*\(",
    r"\bint\s+main\s*\(",
]

_PYTHON_STRONG = [
    r"\bdef\s+\w+\s*\(",
    r"\bimport\s+\w",
    r"\bfrom\s+\w+\s+import\b",
    r"\bprint\s*\(",
    r"\bclass\s+\w+\s*[:(]",
    r"\bself\b",
    r"\bNone\b",
    r"\bTrue\b",
    r"\bFalse\b",
    r"\belif\b",
    r"\blambda\b",
    r"^\s*#.*$",               # Python comments
    r'"""',
    r"f['\"]",
    r"\brange\s*\(",
    r"\blen\s*\(",
    r"\blist\s*\(",
    r"\bdict\s*\(",
]

# Patterns that WEAKLY suggest a language (shared syntax elements)
_C_WEAK = [
    r"[{};]",
    r"#include",
    r"#define",
    r"\bint\b",
    r"\bfor\s*\(",
    r"\bwhile\s*\(",
    r"\bif\s*\(",
]

_CPP_WEAK = [
    r"\bbool\b",
    r"<<",
    r">>",
]

_PYTHON_WEAK = [
    r":\s*$",                  # end-of-line colon
    r"\bfor\s+\w+\s+in\b",
    r"\bwith\b",
    r"\byield\b",
    r"\basync\b",
    r"\bawait\b",
]


def _score(source: str, strong_patterns: list, weak_patterns: list) -> int:
    score = 0
    for p in strong_patterns:
        if re.search(p, source, re.MULTILINE):
            score += 3
    for p in weak_patterns:
        if re.search(p, source, re.MULTILINE):
            score += 1
    return score


class LanguageDetector:
    """
    Detect whether source code is C, C++, or Python.

    Usage:
        lang, confidence = LanguageDetector.detect(source_code)
        # lang ∈ {"c", "cpp", "python", "unknown"}
        # confidence ∈ {"high", "medium", "low", "none"}
    """

    UNKNOWN   = "unknown"
    LANGUAGES = ("c", "cpp", "python")

    @staticmethod
    def detect(source: str) -> tuple[str, str]:
        """
        Returns (language, confidence).
        confidence is one of: "high", "medium", "low", "none"
        """
        if not source or not source.strip():
            return LanguageDetector.UNKNOWN, "none"

        scores = {
            "cpp":    _score(source, _CPP_STRONG,    _CPP_WEAK),
            "c":      _score(source, _C_STRONG,      _C_WEAK),
            "python": _score(source, _PYTHON_STRONG, _PYTHON_WEAK),
        }

        # C++ is a superset of C; if both score > 0,
        # presence of any C++ exclusive feature breaks the tie toward C++.
        cpp_exclusive = [r"::", r"\bnamespace\b", r"\btemplate\b",
                         r"\bcout\b", r"\bnullptr\b", r"\boverride\b"]
        if any(re.search(p, source) for p in cpp_exclusive):
            scores["cpp"] += 5

        best_lang  = max(scores, key=lambda k: scores[k])
        best_score = scores[best_lang]

        if best_score == 0:
            return LanguageDetector.UNKNOWN, "none"

        # Confidence based on score gap and absolute score
        second_best = sorted(scores.values(), reverse=True)[1]
        gap = best_score - second_best

        if best_score >= 9 and gap >= 3:
            confidence = "high"
        elif best_score >= 5 or gap >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        return best_lang, confidence

    @staticmethod
    def detect_and_explain(source: str) -> dict:
        """
        Returns a detailed dict with language, confidence, and per-language scores.
        """
        lang, conf = LanguageDetector.detect(source)
        scores = {
            "cpp":    _score(source, _CPP_STRONG,    _CPP_WEAK),
            "c":      _score(source, _C_STRONG,      _C_WEAK),
            "python": _score(source, _PYTHON_STRONG, _PYTHON_WEAK),
        }
        return {
            "detected_language": lang,
            "confidence":        conf,
            "scores":            scores,
        }
