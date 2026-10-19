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
# An entry starts with a verb, not with a noun phrase ("The integration now ...") or a condition ("If you ...").
NOT_A_VERB = {"the", "a", "an", "this", "that", "these", "those", "it", "its", "there", "now", "if", "when", "our", "your", "no", "all", "every", "each", "some"}


def newest_section(text: str) -> str:
    return re.split(r"^## \[", text, flags=re.MULTILINE)[1]


def problems_of(section: str) -> list[str]:
    """What is wrong with a section: a line that is not a heading, a blank line, one short bullet or the upgrade note."""
    problems = []
    for line in section.splitlines()[1:]:  # the first line is the version heading
        if not line.strip() or line.startswith("###") or line.startswith("Upgrading from"):
            continue
        if not line.startswith("- "):
            problems.append(f"an entry is one line, this one continues or is not an entry: {line}")
            continue
        text = LINK_TARGET.sub("]", line)
        words = re.findall(r"[A-Za-z]+", text[2:])
        if len(text) > MAX_TEXT:
            problems.append(f"too long (the details belong in the pull request): {line}")
        if not PULL_LINK.search(line):
            problems.append(f"no link to the pull request with the details: {line}")
        if re.search(r"\. [A-Z]", text):
            problems.append(f"more than one sentence: {line}")
        if not words or words[0].lower() in NOT_A_VERB:
            problems.append(f"does not start with a verb: {line}")
    return problems


def entries_of(section: str) -> list[str]:
    return [line for line in section.splitlines() if line.startswith("- ")]


def test_the_newest_section_has_entries():
    assert len(entries_of(newest_section(CHANGELOG.read_text(encoding="utf-8")))) >= 3


def test_the_newest_section_is_in_the_style():
    assert problems_of(newest_section(CHANGELOG.read_text(encoding="utf-8"))) == []


GOOD = "- Add a calendar entity per sensor ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))"


def section(*lines: str) -> str:
    return "\n".join(["Unreleased]", "", "### Added", "", *lines, ""])


def test_a_good_entry_passes():
    assert problems_of(section(GOOD)) == []


def test_a_continuation_line_is_reported():
    for continuation in ("  and more details on the next line", "and more details without an indent"):
        problems = problems_of(section(GOOD, continuation))
        assert len(problems) == 1
        assert problems[0].startswith("an entry is one line")


def test_a_noun_phrase_or_a_condition_is_not_a_verb():
    for start in ("The integration now adds", "A calendar entity", "If you use", "Now every sensor has"):
        line = f"- {start} a calendar ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))"
        assert problems_of(section(line)) == [f"does not start with a verb: {line}"]


def test_bold_markup_does_not_hide_the_first_word():
    line = "- **The** calendar ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))"
    assert any("does not start with a verb" in p for p in problems_of(section(line)))


def test_long_unlinked_or_two_sentence_entries_are_reported():
    long_line = "- Add " + "x" * 200 + " ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))"
    assert len(problems_of(section(long_line))) == 1
    assert len(problems_of(section("- Add a calendar"))) == 1
    two = "- Add a calendar. Then fix it ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))"
    assert len(problems_of(section(two))) == 1
