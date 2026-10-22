"""The badge that is the pin of a line on the map card (it draws initials like "L1M" without a picture)."""
import base64
import xml.etree.ElementTree as ET

import pytest

from custom_components.ztm_warsaw.utils import get_line_badge, get_line_class, get_stop_badge

PREFIX = "data:image/svg+xml;base64,"


def _svg(line):
    """The SVG text of the badge of a line, decoded from its data URI."""
    badge = get_line_badge(line)
    assert badge is not None
    assert badge.startswith(PREFIX)
    return base64.b64decode(badge[len(PREFIX):]).decode()


def _parts(line):
    """The shape, the text and the whole root of the SVG of a line (the XML must be well formed)."""
    root = ET.fromstring(_svg(line))
    shape = next(el for el in root if el.tag.endswith(("circle", "rect")))
    text = next(el for el in root.iter() if el.tag.endswith("text"))
    return shape, text, root


@pytest.mark.parametrize(
    ("line", "line_class"),
    [
        ("126", "ordinary"), ("205", "ordinary"), ("327", "periodic"), ("411", "fast periodic"), ("523", "fast"),
        ("612", "ordinary"), ("714", "zone"), ("817", "zone periodic"), ("904", "special"), ("N25", "night"), ("n01", "night"),
        ("E-2", "express"), ("L1", "local"), ("Z1", "special"), ("ZM1", "special"), ("C9", "special"),
        ("9", "tram"), ("24", "tram"), ("M1", "metro"), ("m2", "metro"), ("S3", "rail"), ("s40", "rail"), ("A1", "ordinary"),
    ],
)
def test_the_class_of_a_line_follows_its_series_and_letters(line, line_class):
    assert get_line_class(line) == line_class


@pytest.mark.parametrize(
    ("line", "fill", "text", "ring", "tag", "dashed"),
    [
        ("126", "#f3ecfa", "#23282f", "#a23db5", "circle", False),  # an ordinary line: light, dark number, purple ring
        ("327", "#f3ecfa", "#23282f", "#a23db5", "circle", True),  # the same, dashed: periodic
        ("523", "#d93025", "#ffffff", "#ffffff", "circle", False),  # a fast line is red
        ("411", "#d93025", "#ffffff", "#ffffff", "circle", True),
        ("714", "#558b2f", "#ffffff", "#ffffff", "circle", False),
        ("817", "#558b2f", "#ffffff", "#ffffff", "circle", True),
        ("N25", "#34479a", "#ffffff", "#ffffff", "circle", False),  # white digits on blue
        ("E-2", "#e64a19", "#ffffff", "#ffffff", "circle", True),
        ("9", "#ffe9a8", "#2b2f36", "#f2a900", "circle", False),  # a tram: light yellow, no red (red means a fast line)
        ("M1", "#6a1b9a", "#ffffff", "#ffffff", "circle", False),  # the metro and the urban rail are round too: Home Assistant crops the picture to a circle
        ("S3", "#2e7d32", "#ffffff", "#ffffff", "circle", False),
    ],
)
def test_badge_shows_the_line_in_the_colours_and_shape_of_its_class(line, fill, text, ring, tag, dashed):
    shape, label, _ = _parts(line)
    assert shape.tag.endswith(tag)
    assert shape.get("fill") == fill
    assert shape.get("stroke") == ring
    assert (shape.get("stroke-dasharray") is not None) is dashed
    assert label.get("fill") == text
    assert label.text == line.upper()


def test_every_badge_has_the_same_border_width():
    """A tram or a metro badge must not look as if it had a heavier border than a bus one."""
    widths = {_parts(line)[0].get("stroke-width") for line in ("126", "327", "523", "N25", "E-2", "9", "M1", "S3", "L1", "714")}
    assert widths == {"3"}


def test_a_night_line_has_no_moon_and_its_number_is_as_big_as_any_other():
    """The moon of the first beta hid the digits at the size of a pin: a night line is told apart by its blue alone."""
    assert "<path" not in _svg("N25")
    _, night_text, _ = _parts("N25")
    _, day_text, _ = _parts("126")
    assert (night_text.get("font-size"), night_text.get("y")) == (day_text.get("font-size"), day_text.get("y"))


@pytest.mark.parametrize("line", ["", "12345", "1 2", "<b>", '1"/><script>', "1)", "é1", "1_2", "-" * 5])
def test_badge_refuses_anything_that_is_not_a_plain_line_code(line):
    assert get_line_badge(line) is None


def test_badge_is_safe_inside_an_unquoted_css_url():
    """The frontend writes the picture as `background-image: url(<picture>)` without quotes."""
    badge = get_line_badge("176")
    assert not any(c in badge for c in " ()\"'\\\n")


@pytest.mark.parametrize("line", ["126", "327", "523", "N25", "E-2", "9", "M1", "M2", "S3", "L1", "Z1"])
def test_every_badge_is_a_circle(line):
    """Home Assistant crops the picture of an entity to a circle: no class of line may be drawn as a square or a rectangle."""
    _, _, root = _parts(line)
    assert not [el for el in root.iter() if el.tag.endswith("rect")]
    assert [el for el in root.iter() if el.tag.endswith("circle")]


def test_the_badge_of_a_stop_pole_is_a_sign_with_its_number_and_is_not_a_line_badge():
    badge = get_stop_badge("05")
    assert badge is not None
    root = ET.fromstring(base64.b64decode(badge[len(PREFIX):]).decode())
    assert next(el for el in root.iter() if el.tag.endswith("text")).text == "05"
    assert not any(c in badge for c in " ()\"'\\\n")
    assert badge != get_line_badge("5")


@pytest.mark.parametrize("pole", ["", "123", "a1", "<b>", "1 2", "é1"])
def test_the_badge_of_a_stop_pole_refuses_anything_that_is_not_one_or_two_digits(pole):
    assert get_stop_badge(pole) is None
