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
# An entry starts with one of these verbs (add yours when a new one is needed: the list is what makes "starts with a verb"
# a checkable rule, a denylist of noun openers cannot be).
VERBS = {
    "accept", "add", "allow", "apply", "ask", "block", "bump", "change", "check", "clear", "close", "compute", "convert",
    "count", "create", "delete", "detect", "disable", "document", "download", "drop", "enable", "ensure", "expect",
    "extend", "fail", "fix", "give", "handle", "hide", "improve", "include", "install", "keep", "let", "limit", "list",
    "load", "log", "make", "mark", "match", "merge", "migrate", "move", "name", "open", "pin", "prevent", "publish",
    "raise", "read", "record", "refresh", "refuse", "reject", "release", "reload", "remove", "rename", "replace",
    "report", "require", "resolve", "restore", "retry", "return", "revert", "rewrite", "run", "save", "scan", "send",
    "set", "share", "show", "simplify", "skip", "split", "start", "stop", "strip", "support", "switch", "take", "test",
    "trim", "turn", "update", "use", "validate", "verify", "wait", "warn", "write",
}


def has_content(section: str) -> bool:
    """Whether a section holds anything but its heading line, blank lines and empty '###' headings: an empty section
    is skipped, text that is not a bullet (a malformed first entry) is content and gets checked."""
    return any(line.strip() and not line.startswith("###") for line in section.splitlines()[1:])


def newest_section(text: str) -> str:
    """The first section with content: [Unreleased], or after a stable cut (it is empty then) the version just released."""
    sections = re.split(r"^## \[", text, flags=re.MULTILINE)[1:]
    return next(sec for sec in sections if has_content(sec))


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
        if not words or words[0].lower() not in VERBS:
            problems.append(f"does not start with a verb of the list in tests/test_changelog_style.py: {line}")
    return problems


def entries_of(section: str) -> list[str]:
    return [line for line in section.splitlines() if line.startswith("- ")]


def test_the_newest_section_has_entries():
    assert len(entries_of(newest_section(CHANGELOG.read_text(encoding="utf-8")))) >= 1


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


def test_anything_that_is_not_a_listed_verb_is_rejected():
    for start in ("The integration now adds", "A calendar entity", "If you use", "Calendar entities are supported", "Fast"):
        line = f"- {start} a calendar ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))"
        assert len(problems_of(section(line))) == 1, start
        assert "does not start with a verb" in problems_of(section(line))[0]


def test_a_stable_cut_leaves_an_empty_unreleased_and_the_released_section_is_checked():
    text = "# Changelog\n\n## [Unreleased]\n\n## [1.2.0] - 2026-11-01\n\n### Added\n\n" + GOOD + "\n\n## [1.1.4]\n\n- Old long entry\n"
    assert newest_section(text).startswith("1.2.0]")
    assert problems_of(newest_section(text)) == []


def test_bold_markup_does_not_hide_the_first_word():
    line = "- **The** calendar ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))"
    assert any("does not start with a verb" in p for p in problems_of(section(line)))
    assert problems_of(section("- **Add** a calendar ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))")) == []


def test_long_unlinked_or_two_sentence_entries_are_reported():
    long_line = "- Add " + "x" * 200 + " ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))"
    assert len(problems_of(section(long_line))) == 1
    assert len(problems_of(section("- Add a calendar"))) == 1
    two = "- Add a calendar. Then fix it ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))"
    assert len(problems_of(section(two))) == 1


def test_text_that_is_not_a_bullet_in_unreleased_is_checked_not_skipped():
    text = "# Changelog\n\n## [Unreleased]\n\n### Added\n\nAdd a calendar without the dash\n\n## [1.2.0] - 2026-11-01\n\n### Added\n\n" + GOOD + "\n"
    chosen = newest_section(text)
    assert chosen.startswith("Unreleased]")
    assert problems_of(chosen) == ["an entry is one line, this one continues or is not an entry: Add a calendar without the dash"]


def test_an_unreleased_section_with_only_empty_headings_is_skipped():
    text = "# Changelog\n\n## [Unreleased]\n\n### Added\n\n### Fixed\n\n## [1.2.0] - 2026-11-01\n\n### Added\n\n" + GOOD + "\n"
    assert newest_section(text).startswith("1.2.0]")


def test_one_entry_in_unreleased_after_a_release_is_enough():
    text = "# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n" + GOOD + "\n\n## [1.2.0] - 2026-11-01\n\n- Old\n"
    assert newest_section(text).startswith("Unreleased]")
    assert problems_of(newest_section(text)) == []
