"""The newest section of CHANGELOG.md keeps its entries short: one line that starts with a verb and links the pull request.

Long entries are a habit of generated text; the details belong in the pull request, which the entry links to.
Older sections are history and are left as they are.
"""

from __future__ import annotations

import re
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
MAX_TEXT = 190  # characters of an entry without its links
LINK_TARGET = re.compile(r"\]\([^)]*\)")
PULL_LINK = re.compile(r"\[#\d+\]\(https://github\.com/solarssk/ztm_warsaw/pull/\d+\)")


def newest_section_entries() -> list[str]:
    text = CHANGELOG.read_text(encoding="utf-8")
    sections = re.split(r"^## \[", text, flags=re.MULTILINE)[1:]
    return [line for line in sections[0].splitlines() if line.startswith("- ")]


def test_the_newest_section_has_entries():
    assert len(newest_section_entries()) >= 3


def test_every_entry_is_short():
    too_long = [e for e in newest_section_entries() if len(LINK_TARGET.sub("]", e)) > MAX_TEXT]
    assert too_long == [], f"shorten these (the details belong in the pull request): {too_long}"


def test_every_entry_links_a_pull_request():
    unlinked = [e for e in newest_section_entries() if not PULL_LINK.search(e)]
    assert unlinked == [], f"link the pull request with the details: {unlinked}"


def test_every_entry_is_one_sentence_without_a_trailing_full_stop_inside():
    several = [e for e in newest_section_entries() if re.search(r"\. [A-Z]", LINK_TARGET.sub("]", e))]
    assert several == [], f"one sentence per entry: {several}"
