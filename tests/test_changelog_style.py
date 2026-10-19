"""The newest section of CHANGELOG.md is release notes for the people who use the integration, and it stays short.

Each entry is one line: a bold title and one short, friendly sentence about what the user gets. Long, technical entries are a
habit of generated text; the details belong in the pull request. Older sections are history and are left as they are.
"""

from __future__ import annotations

import re
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
MAX_ENTRY = 340  # characters of an entry line, links included
TITLE = re.compile(r"^- \*\*[^*]{2,70}\*\*:?\s*(.*)$")  # "- **Title**: a short sentence"; group 1 is the sentence
MAX_SENTENCES = 2


def has_content(section: str) -> bool:
    """Whether a section holds anything but its heading line, blank lines and empty '###' headings: an empty section
    is skipped, text that is not a bullet (a malformed first entry) is content and gets checked."""
    return any(line.strip() and not line.startswith("###") for line in section.splitlines()[1:])


def newest_section(text: str) -> str:
    """The first section with content: [Unreleased], or after a stable cut (it is empty then) the version just released."""
    sections = re.split(r"^## \[", text, flags=re.MULTILINE)[1:]
    return next(sec for sec in sections if has_content(sec))


def entries_of(section: str) -> list[str]:
    """The bullet lines of a changelog section."""
    return [line for line in section.splitlines() if line.startswith("- ")]


def problems_of(section: str) -> list[str]:
    """What is wrong with a section. Before its first '###' heading prose is welcome (the greeting); after it there are
    only headings, blank lines and one-line entries with a bold title."""
    problems = []
    in_entries = False
    for line in section.splitlines()[1:]:  # the first line is the version heading
        if line.startswith("###"):
            in_entries = True
            continue
        if not line.strip() or not in_entries:
            continue
        if not line.startswith("- "):
            problems.append(f"an entry is one line, this one continues or is not an entry: {line}")
        elif not (title := TITLE.match(line)):
            problems.append(f"an entry opens with a bold title, like '- **Title**: a short sentence': {line}")
        elif len(title.group(1).strip(" :.")) < 8:
            problems.append(f"a title is followed by a short sentence about what the user gets: {line}")
        elif len(line) > MAX_ENTRY:
            problems.append(f"too long (the details belong in the pull request): {line}")
        elif len(re.findall(r"[.!?](?:\s|$)", re.sub(r"\]\([^)]*\)", "]", title.group(1)))) > MAX_SENTENCES:
            problems.append(f"at most {MAX_SENTENCES} short sentences: {line}")
    return problems


def test_the_newest_section_has_entries():
    assert len(entries_of(newest_section(CHANGELOG.read_text(encoding="utf-8")))) >= 1


def test_the_newest_section_is_in_the_style():
    assert problems_of(newest_section(CHANGELOG.read_text(encoding="utf-8"))) == []


GOOD = "- **A calendar**: switch it on to see the day's departures."


def section(*lines: str) -> str:
    """A changelog section as the style check sees it: a greeting, an `### Added` heading and the given lines."""
    return "\n".join(["Unreleased]", "", "Hey everyone, a long friendly greeting is fine here.", "", "### Added", "", *lines, ""])


def test_a_good_entry_and_a_greeting_pass():
    assert problems_of(section(GOOD)) == []


def test_a_continuation_line_is_reported():
    for continuation in ("  and more details on the next line", "and more details without an indent"):
        problems = problems_of(section(GOOD, continuation))
        assert len(problems) == 1
        assert problems[0].startswith("an entry is one line")


def test_an_entry_without_a_bold_title_is_reported():
    for line in ("- Add a calendar entity", "- A **calendar** for you", "-**Calendar** no space", "- **x** too short a title"):
        assert len(problems_of(section(line))) == 1, line


def test_a_title_without_a_sentence_is_reported():
    for line in ("- **A calendar**", "- **A calendar**:", "- **A calendar**: ok", "- **A calendar**:   "):
        problems = problems_of(section(line))
        assert len(problems) == 1, line
        assert problems[0].startswith("a title is followed by a short sentence")


def test_more_than_two_sentences_are_reported():
    ok = "- **A calendar**: switch it on. It shows the day."
    too_many = "- **A calendar**: switch it on. It shows the day. Then use it in automations."
    assert problems_of(section(ok)) == []
    assert problems_of(section(too_many)) == [f"at most 2 short sentences: {too_many}"]


def test_a_link_in_a_sentence_is_not_counted_as_a_sentence():
    line = "- **Get a token**: see [the portal](https://dane.um.warszawa.pl/pl/key-api) and paste it. Then you are done."
    assert problems_of(section(line)) == []


def test_an_entry_that_is_too_long_is_reported():
    long_line = "- **A calendar**: " + "words " * 80
    assert len(problems_of(section(long_line))) == 1


def test_a_stable_cut_leaves_an_empty_unreleased_and_the_released_section_is_checked():
    text = "# Changelog\n\n## [Unreleased]\n\n## [1.2.0] - 2026-11-01\n\n### Added\n\n" + GOOD + "\n\n## [1.1.4]\n\n- Old long entry\n"
    assert newest_section(text).startswith("1.2.0]")
    assert problems_of(newest_section(text)) == []


def test_text_that_is_not_a_bullet_after_the_first_heading_is_checked_not_skipped():
    text = "# Changelog\n\n## [Unreleased]\n\n### Added\n\nA calendar without the dash\n\n## [1.2.0] - 2026-11-01\n\n### Added\n\n" + GOOD + "\n"
    chosen = newest_section(text)
    assert chosen.startswith("Unreleased]")
    assert problems_of(chosen) == ["an entry is one line, this one continues or is not an entry: A calendar without the dash"]


def test_an_unreleased_section_with_only_empty_headings_is_skipped():
    text = "# Changelog\n\n## [Unreleased]\n\n### Added\n\n### Fixed\n\n## [1.2.0] - 2026-11-01\n\n### Added\n\n" + GOOD + "\n"
    assert newest_section(text).startswith("1.2.0]")


def test_one_entry_in_unreleased_after_a_release_is_enough():
    text = "# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n" + GOOD + "\n\n## [1.2.0] - 2026-11-01\n\n- Old\n"
    assert newest_section(text).startswith("Unreleased]")
    assert problems_of(newest_section(text)) == []
