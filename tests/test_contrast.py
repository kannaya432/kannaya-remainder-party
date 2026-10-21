"""WCAG contrast checks computed from the real stylesheet tokens."""

import re
from pathlib import Path

import pytest

CSS = (Path(__file__).parents[1] / "src/planner/static/app.css").read_text()


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def _themes() -> dict[str, dict[str, str]]:
    light_block = CSS.split("@media (prefers-color-scheme: dark)")[0]
    dark_block = CSS.split("@media (prefers-color-scheme: dark)")[1].split(
        "* {"
    )[0]
    light = _tokens(light_block)
    return {"light": light, "dark": {**light, **_tokens(dark_block)}}


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


TEXT_PAIRS = [
    ("ink", "ground"),
    ("ink", "surface"),
    ("muted", "ground"),
    ("muted", "surface"),
    ("on-primary", "primary"),
    ("alert", "surface"),
    ("alert", "ground"),
]
NON_TEXT_PAIRS = [("focus", "ground"), ("focus", "surface")]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(("fg", "bg"), TEXT_PAIRS)
def test_text_meets_wcag_aa(theme: str, fg: str, bg: str) -> None:
    tokens = _themes()[theme]
    assert contrast(tokens[fg], tokens[bg]) >= 4.5


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(("fg", "bg"), NON_TEXT_PAIRS)
def test_focus_indicator_meets_3_to_1(theme: str, fg: str, bg: str) -> None:
    tokens = _themes()[theme]
    assert contrast(tokens[fg], tokens[bg]) >= 3.0


def test_known_ratio_is_computed_correctly() -> None:
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
