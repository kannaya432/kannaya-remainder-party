import pytest
from pydantic import ValidationError

from helpers import make
from planner.sanitize import clean_ai_text, clean_text


def test_clean_text_strips_markup_controls_and_spoofing() -> None:
    raw = "  Hi <b>there</b>\n\t\u202eevil\u200b  "
    assert clean_text(raw) == "Hi b there /b evil"


def test_clean_text_keeps_indic_joiners() -> None:
    assert "\u200c" in clean_text("క\u200cష")


def test_clean_ai_text_removes_urls_and_truncates() -> None:
    out = clean_ai_text("Visit https://evil.example now www.x.com ok", 100)
    assert "http" not in out and "www" not in out
    long = clean_ai_text("word " * 100, 30)
    assert len(long) <= 30 and long.endswith("\u2026")


def test_model_cleans_free_text_and_dedupes() -> None:
    r = make(title=" A <i>B</i> ", dietary=["vegan", "vegan"], city="  ")
    assert r.title == "A i B /i"
    assert r.dietary == ["vegan"]
    assert r.city is None


@pytest.mark.parametrize(
    "override",
    [
        {"guest_count": 0},
        {"guest_count": 5001},
        {"budget": 0},
        {"title": "   "},
        {"title": "x" * 81},
        {"currency": "XXX"},
        {"event_type": "funeral"},
        {"priorities": ["food", "decor", "venue", "photography"]},
        {"unknown_field": 1},
        {"honoree_age": 30},  # wedding + age
    ],
)
def test_invalid_requests_rejected(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make(**override)


def test_birthday_accepts_age() -> None:
    assert make(event_type="birthday", honoree_age=7).honoree_age == 7
