"""Text sanitisation shared by request validation and AI output handling."""

import re
import unicodedata

# Invisible / bidi-control characters used for spoofing. ZWJ and ZWNJ
# (U+200C/D) are deliberately kept: Indic scripts and emoji need them.
_STRIP = frozenset(
    "\u200b\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
    "\u2060\u2066\u2067\u2068\u2069\ufeff"
)
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


def clean_text(value: str) -> str:
    """Normalises untrusted text to a single safe line.

    Applies NFKC, drops spoofing characters, turns other control characters
    and angle brackets into spaces, and collapses whitespace.

    Args:
        value: Raw text.

    Returns:
        The cleaned single-line text (possibly empty).
    """
    out: list[str] = []
    for ch in unicodedata.normalize("NFKC", value):
        if ch in _STRIP:
            continue
        if ch in "<>" or (
            unicodedata.category(ch)[0] in "CZ"
            and ch
            not in (
                "\u200c",
                "\u200d",
            )
        ):
            out.append(" ")
        else:
            out.append(ch)
    return " ".join("".join(out).split())


def clean_ai_text(value: str, max_length: int) -> str:
    """Cleans model output: no URLs, markup or control characters.

    Args:
        value: Text produced by the model.
        max_length: Maximum length; longer text is cut at a word boundary.

    Returns:
        Cleaned text, or an empty string if nothing usable remains.
    """
    text = clean_text(_URL.sub(" ", value))
    if len(text) <= max_length:
        return text
    cut = text[: max_length - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{cut}\u2026"
