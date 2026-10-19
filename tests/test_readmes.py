"""The README exists in every language the integration is translated into, with the same structure and working links."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parent.parent
FILES = ["README.md"] + [f"README.{code}.md" for code in ("pl", "uk", "ru", "de", "es", "fr", "it")]


def _anchor(heading: str) -> str:
    """The anchor GitHub makes of a heading: lower case, punctuation and emoji dropped, words joined by dashes (the emoji leaves a leading dash)."""
    text = re.sub(r"[^\w ]", "", heading.lower().replace("-", " "), flags=re.UNICODE)
    return "-" + re.sub(r"\s+", "-", text.strip())


@pytest.mark.parametrize("name", FILES)
def test_every_link_inside_a_readme_points_to_a_heading_of_it(name):
    """The table of contents and the links in the text jump to a section that exists in that language."""
    text = (ROOT / name).read_text(encoding="utf-8")
    anchors = {_anchor(m.group(1)) for m in re.finditer(r"^## (.+)$", text, re.MULTILINE)}
    for target in re.findall(r"\]\(#([^)]+)\)", text):
        assert f"-{target.lstrip('-')}" in anchors, f"{name}: no heading for #{target}"


@pytest.mark.parametrize("name", FILES)
def test_every_readme_has_the_same_sections_and_the_language_switch(name):
    """Eleven sections, the same screenshots and a switch that links to every other language, so none is a dead end."""
    text = (ROOT / name).read_text(encoding="utf-8")
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^## ", text, re.MULTILINE)) == len(re.findall(r"^## ", english, re.MULTILINE)) == 11
    assert re.findall(r"user-attachments/assets/[0-9a-f-]+", text) == re.findall(r"user-attachments/assets/[0-9a-f-]+", english)
    for other in FILES:
        assert other == name or f'href="{other}"' in text, f"{name} does not link to {other}"
