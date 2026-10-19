"""The wiki source (docs/wiki/) is checked in every run, and the checker is tested on broken sources."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_wiki_docs.py"
spec = importlib.util.spec_from_file_location("check_wiki_docs", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def make(tmp_path: Path, **overrides: str | None) -> Path:
    """A source with every expected page; ``overrides`` replaces or (None) removes a page."""
    for name in checker.EXPECTED:
        (tmp_path / f"{name}.md").write_text(f"# {name}\n\nSee [Home](Home).\n", encoding="utf-8")
    for name, text in overrides.items():
        page = tmp_path / f"{name}.md"
        if text is None:
            page.unlink()
        else:
            page.write_text(text, encoding="utf-8")
    return tmp_path


def test_the_real_wiki_source_is_fine():
    assert checker.check(checker.DEFAULT_DIR) == []


def test_a_complete_source_passes(tmp_path):
    assert checker.check(make(tmp_path)) == []


def test_a_missing_page_is_reported(tmp_path):
    assert checker.check(make(tmp_path, **{"2.-Concepts": None})) == ["missing page: 2.-Concepts.md"]


def test_a_link_to_nowhere_is_reported(tmp_path):
    problems = checker.check(make(tmp_path, Home="# Home\n\n[x](Nowhere)\n"))
    assert problems == ["Home.md links to a page that does not exist: Nowhere"]


def test_links_with_a_fragment_a_title_angle_brackets_or_to_the_web_are_fine(tmp_path):
    text = '# Home\n\n[a](2.-Concepts#service-day) [b](https://example.org/x) [c](#top) [d](<Home>) [e](Home "the title")\n'
    assert checker.check(make(tmp_path, Home=text)) == []


def test_a_title_or_angle_brackets_do_not_hide_a_broken_link(tmp_path):
    problems = checker.check(make(tmp_path, Home='# Home\n\n[a](Nowhere "t") [b](<Elsewhere>)\n'))
    assert problems == [
        "Home.md links to a page that does not exist: Nowhere",
        "Home.md links to a page that does not exist: Elsewhere",
    ]


def test_an_email_address_is_reported(tmp_path):
    problems = checker.check(make(tmp_path, Home="# Home\n\nWrite to someone@example.org\n"))
    assert problems == ["Home.md contains something that looks like an e-mail address"]


def test_a_page_without_a_title_is_reported(tmp_path):
    assert checker.check(make(tmp_path, Home="no title here\n")) == ["Home.md does not start with a '# Title' line"]


def test_a_file_that_is_not_a_page_is_reported(tmp_path):
    make(tmp_path)
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    assert checker.check(tmp_path) == ["not a page (the wiki takes Markdown only): notes.txt"]


def test_a_reference_style_link_to_nowhere_is_reported(tmp_path):
    text = "# Home\n\nSee [Concepts][c] and [other][o].\n\n[c]: Nowhere\n[o]: <Elsewhere> \"a title\"\n"
    assert checker.check(make(tmp_path, Home=text)) == [
        "Home.md links to a page that does not exist: Nowhere",
        "Home.md links to a page that does not exist: Elsewhere",
    ]


def test_a_reference_style_link_that_resolves_is_fine(tmp_path):
    text = "# Home\n\nSee [Concepts][c] and [web][w].\n\n[c]: 2.-Concepts#anchor\n[w]: https://example.org/page\n"
    assert checker.check(make(tmp_path, Home=text)) == []


def test_a_folder_is_reported_because_rsync_would_publish_it(tmp_path):
    make(tmp_path)
    (tmp_path / "images").mkdir()
    assert checker.check(tmp_path) == ["not a plain file (no folders or links in the wiki source): images"]


def test_a_link_to_a_file_is_reported_even_when_its_target_looks_like_a_page(tmp_path):
    make(tmp_path)
    (tmp_path / "evil.md").symlink_to(tmp_path / "Home.md")  # starts with '# ', so only the link check can see it
    assert checker.check(tmp_path) == ["not a plain file (no folders or links in the wiki source): evil.md"]


def test_a_page_that_is_not_utf8_is_a_clean_problem_not_a_crash(tmp_path):
    make(tmp_path)
    (tmp_path / "Home.md").write_bytes(b"# Home\n\xff\xfe")
    assert checker.check(tmp_path) == ["Home.md is not UTF-8 text"]


def test_the_problem_lines_are_short_texts_without_the_page_prose(tmp_path):
    prose = "A SENTENCE OF THE PAGE THAT MUST NOT BE PRINTED"
    problems = checker.check(make(tmp_path, Home=f"{prose}\n"))
    assert problems == ["Home.md does not start with a '# Title' line"]
    assert prose not in "".join(problems)


def test_main_refuses_a_directory_that_does_not_exist():
    assert checker.main(["check_wiki_docs.py", "/nonexistent-dir-xyz"]) == 1


def test_main_returns_zero_for_the_real_source():
    assert checker.main(["check_wiki_docs.py"]) == 0
