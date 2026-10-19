"""The badge that is the pin of a line on the map card (it draws initials like "L1M" without a picture)."""
import base64
import xml.etree.ElementTree as ET

import pytest

from custom_components.ztm_warsaw.utils import get_line_badge

PREFIX = "data:image/svg+xml;base64,"


def _svg(line):
    """The SVG text of the badge of a line, decoded from its data URI."""
    badge = get_line_badge(line)
    assert badge is not None
    assert badge.startswith(PREFIX)
    return base64.b64decode(badge[len(PREFIX):]).decode()


@pytest.mark.parametrize(
    ("line", "colour"),
    [("176", "#c62828"), ("9", "#1565c0"), ("S2", "#2e7d32"), ("M1", "#6a1b9a"), ("N01", "#263238"), ("s2", "#2e7d32"), ("m1", "#6a1b9a"), ("E-1", "#c62828")],
)
def test_badge_shows_the_line_in_the_colour_of_its_kind(line, colour):
    svg = _svg(line)
    root = ET.fromstring(svg)  # well-formed XML
    text = next(el for el in root.iter() if el.tag.endswith("text"))
    assert text.text == line.upper()
    assert f'fill="{colour}"' in svg


@pytest.mark.parametrize("line", ["", "12345", "1 2", "<b>", '1"/><script>', "1)", "é1", "1_2", "-"*5])
def test_badge_refuses_anything_that_is_not_a_plain_line_code(line):
    assert get_line_badge(line) is None


def test_badge_is_safe_inside_an_unquoted_css_url():
    """The frontend writes the picture as `background-image: url(<picture>)` without quotes."""
    badge = get_line_badge("176")
    assert not any(c in badge for c in " ()\"'\\\n")
