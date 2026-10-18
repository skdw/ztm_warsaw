"""The icon of a line by its number."""

import pytest

from custom_components.ztm_warsaw.utils import get_line_icon


@pytest.mark.parametrize(
    ("line", "icon"),
    [
        ("5", "mdi:tram"),
        ("18", "mdi:tram"),
        ("S1", "mdi:train"),
        ("S12", "mdi:train"),
        ("M1", "mdi:train-variant"),
        ("151", "mdi:bus"),
        ("N25", "mdi:bus"),
        ("L-1", "mdi:bus"),
        ("523", "mdi:bus"),
        ("ZZZ", "mdi:bus"),
    ],
)
def test_line_icons(line, icon):
    assert get_line_icon(line) == icon
