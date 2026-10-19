"""Tests for scripts/check_pr_docs_impact.py, the pull request documentation-impact check."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_pr_docs_impact.py"
PR_TEMPLATE = ROOT / ".github" / "pull_request_template.md"

TEMPLATE_BODY = """## Documentation impact

- [ ] Docs updated
- [ ] No doc update needed: <state the reason>
"""


@pytest.fixture(scope="module")
def docs_impact() -> ModuleType:
    """The script scripts/check_pr_docs_impact.py loaded as a module (it is not a package)."""
    spec = importlib.util.spec_from_file_location("check_pr_docs_impact", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def body(docs_updated: bool = False, no_update: str | None = None, newline: str = "\n") -> str:
    """A pull request body with the Documentation impact section: which box is ticked, with which reason, and which line ending."""
    lines = [
        "## Documentation impact",
        "",
        f"- [{'x' if docs_updated else ' '}] Docs updated",
        f"- [{'x' if no_update is not None else ' '}] No doc update needed: {no_update or '<state the reason>'}",
    ]
    return newline.join(lines) + newline


def in_section(text: str) -> str:
    """The given text placed under the Documentation impact heading."""
    return f"## Documentation impact\n\n{text}"


def write_event(path: Path, pr_body: str | None, login: str = "solarssk") -> str:
    """Write a GitHub pull request event file (body, author, base and head SHA) and return its path as a string."""
    event = {
        "pull_request": {
            "body": pr_body,
            "user": {"login": login},
            "base": {"sha": "b" * 40},
            "head": {"sha": "a" * 40},
        }
    }
    path.write_text(json.dumps(event), encoding="utf-8")
    return str(path)


# --- the declaration -------------------------------------------------------------


def test_untouched_template_fails(docs_impact: ModuleType) -> None:
    problems = docs_impact.evaluate(TEMPLATE_BODY, ["README.md"])
    assert problems == [docs_impact.MSG_NONE]


def test_both_boxes_fail(docs_impact: ModuleType) -> None:
    problems = docs_impact.evaluate(body(docs_updated=True, no_update="CI only"), ["README.md"])
    assert problems == [docs_impact.MSG_BOTH]


def test_placeholder_reason_does_not_count(docs_impact: ModuleType) -> None:
    ticked = in_section("- [x] Docs updated\n- [x] No doc update needed: <state the reason>\n")
    assert docs_impact.read_declaration(ticked) == (True, False)
    only_placeholder = in_section("- [x] No doc update needed: <state the reason>\n")
    assert docs_impact.read_declaration(only_placeholder) == (False, False)
    assert docs_impact.evaluate(only_placeholder, []) == [docs_impact.MSG_NEEDS_REASON]


@pytest.mark.parametrize("mark", ["x", "X"])
def test_the_tick_may_be_lower_or_upper_case(docs_impact: ModuleType, mark: str) -> None:
    docs = in_section(f"- [{mark}] Docs updated\n- [ ] No doc update needed: <state the reason>\n")
    no_docs = in_section(f"- [ ] Docs updated\n- [{mark}] No doc update needed: tests only\n")
    assert docs_impact.read_declaration(docs) == (True, False)
    assert docs_impact.read_declaration(no_docs) == (False, True)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_docs_updated_needs_a_doc_path(docs_impact: ModuleType, newline: str) -> None:
    declared = body(docs_updated=True, newline=newline)
    assert docs_impact.evaluate(declared, ["README.md", "custom_components/ztm_warsaw/sensor.py"]) == []
    problems = docs_impact.evaluate(declared, ["custom_components/ztm_warsaw/sensor.py"])
    assert problems == [docs_impact.MSG_DOCS_NOT_CHANGED]


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_no_doc_update_must_not_touch_a_doc_path(docs_impact: ModuleType, newline: str) -> None:
    declared = body(no_update="test-only change", newline=newline)
    assert docs_impact.evaluate(declared, ["tests/test_sensor.py"]) == []
    problems = docs_impact.evaluate(declared, ["tests/test_sensor.py", "CHANGELOG.md"])
    assert problems == [docs_impact.MSG_DOCS_CHANGED]


# --- what counts as documentation ------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["README.md", "info.md", "CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md", "AGENTS.md", "CODE_OF_CONDUCT.md", "docs/x.md", "docs/a/b.png"],
)
def test_documentation_paths_count(docs_impact: ModuleType, path: str) -> None:
    assert docs_impact.is_doc_path(path)
    assert docs_impact.evaluate(body(docs_updated=True), [path]) == []


@pytest.mark.parametrize(
    "path",
    [
        "README.md.bak",
        "README.md5",
        "docs.md.txt",
        "tests/docs/x.md",
        "custom_components/ztm_warsaw/README.md",
        ".github/pull_request_template.md",
        "custom_components/ztm_warsaw/translations/en.json",
        "hacs.json",
        "LICENSE",
    ],
)
def test_other_paths_do_not_count(docs_impact: ModuleType, path: str) -> None:
    assert not docs_impact.is_doc_path(path)
    assert docs_impact.evaluate(body(docs_updated=True), [path]) == [docs_impact.MSG_DOCS_NOT_CHANGED]


# --- the real pull request template ----------------------------------------------


def test_the_repository_template_is_an_untouched_declaration(docs_impact: ModuleType) -> None:
    template = PR_TEMPLATE.read_text(encoding="utf-8")
    assert docs_impact.read_declaration(template) == (False, False)


def test_ticking_one_box_of_the_repository_template_is_exactly_one_declaration(docs_impact: ModuleType) -> None:
    template = PR_TEMPLATE.read_text(encoding="utf-8")
    docs = template.replace("- [ ] Docs updated", "- [x] Docs updated")
    no_docs = template.replace("- [ ] No doc update needed: <state the reason>", "- [x] No doc update needed: tests only")
    assert docs_impact.read_declaration(docs) == (True, False)
    assert docs_impact.read_declaration(no_docs) == (False, True)


# --- main() ----------------------------------------------------------------------


def test_main_ignores_non_pull_request_events(docs_impact: ModuleType, tmp_path: Path) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"ref": "refs/heads/main"}), encoding="utf-8")
    assert docs_impact.main(str(event), lambda _base, _head: pytest.fail("must not diff")) == 0
    assert docs_impact.main("", lambda _base, _head: pytest.fail("must not diff")) == 0


def test_main_skips_dependabot_by_author_not_by_branch(docs_impact: ModuleType, tmp_path: Path) -> None:
    no_diff = lambda _base, _head: pytest.fail("must not diff")  # noqa: E731
    assert docs_impact.main(write_event(tmp_path / "a.json", None, "dependabot[bot]"), no_diff) == 0
    # An ordinary account is checked even if its branch is called dependabot/...
    assert docs_impact.main(write_event(tmp_path / "b.json", TEMPLATE_BODY, "someone")) == 1
    # ... and so is an account whose name merely contains the bot's.
    assert docs_impact.main(write_event(tmp_path / "c.json", TEMPLATE_BODY, "dependabot-fan")) == 1


def test_main_handles_a_null_body(docs_impact: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    no_diff = lambda _base, _head: pytest.fail("must not diff")  # noqa: E731
    assert docs_impact.main(write_event(tmp_path / "null.json", None), no_diff) == 1
    assert docs_impact.MSG_NO_SECTION in capsys.readouterr().out


def test_main_diffs_base_and_head_from_the_event(docs_impact: ModuleType, tmp_path: Path) -> None:
    seen: list[tuple[str, str]] = []

    def fake_diff(base: str, head: str) -> list[str]:
        """A stand-in for the git diff that records the base and head it is asked about and lists README.md as changed."""
        seen.append((base, head))
        return ["README.md"]

    event = write_event(tmp_path / "event.json", body(docs_updated=True))
    assert docs_impact.main(event, fake_diff) == 0
    assert seen == [("b" * 40, "a" * 40)]
    event = write_event(tmp_path / "event2.json", body(no_update="no behavior change"))
    assert docs_impact.main(event, fake_diff) == 1


def test_main_messages_are_constants_and_say_how_to_fix(
    docs_impact: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hostile = in_section("- [x] Docs updated\n- [x] No doc update needed: ::error::pwned %0A\n")
    assert docs_impact.main(write_event(tmp_path / "h.json", hostile), lambda _b, _h: ["a.py"]) == 1
    out = capsys.readouterr().out
    assert "pwned" not in out
    assert docs_impact.MSG_BOTH in out
    assert docs_impact.MSG_EDIT_HINT in out


# --- the real git diff -----------------------------------------------------------


@pytest.fixture
def git_repo(docs_impact: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty git repository in a temporary directory, made the working directory, with the script pointed at the real git."""
    git = shutil.which("git")
    assert git is not None
    monkeypatch.setattr(docs_impact, "GIT", git)
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    run_git("init", "-q", "-b", "main")
    return repo


def run_git(*args: str) -> str:
    """Run git with a throwaway identity and no signing, and return its stripped output; a failure raises."""
    git = shutil.which("git")
    assert git is not None
    identity = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"]
    return subprocess.run([git, *identity, *args], check=True, capture_output=True, text=True).stdout.strip()


def commit(repo: Path, files: dict[str, str | None], message: str) -> str:
    """Write (or, for None, remove) the given files, commit them, and return the new commit's SHA."""
    for name, content in files.items():
        target = repo / name
        if content is None:
            run_git("rm", "-q", name)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        run_git("add", name)
    run_git("commit", "-q", "-m", message)
    return run_git("rev-parse", "HEAD")


def test_git_diff_lists_the_pull_request_side_only(docs_impact: ModuleType, git_repo: Path) -> None:
    base = commit(git_repo, {"README.md": "one\n", "a.py": "1\n"}, "base")
    run_git("checkout", "-q", "-b", "feature")
    head = commit(git_repo, {"b.py": "2\n", "CHANGELOG.md": "# c\n"}, "feature work")
    # main moves on after the branch point; those files are not part of the pull request.
    run_git("checkout", "-q", "main")
    moved_base = commit(git_repo, {"later_on_main.py": "3\n"}, "main moves on")
    assert sorted(docs_impact.git_changed_files(moved_base, head)) == ["CHANGELOG.md", "b.py"]
    assert sorted(docs_impact.git_changed_files(base, head)) == ["CHANGELOG.md", "b.py"]


def test_git_diff_shows_both_ends_of_a_moved_doc(docs_impact: ModuleType, git_repo: Path) -> None:
    base = commit(git_repo, {"docs/old.md": "the same content, long enough to be detected as a rename\n" * 5}, "base")
    run_git("checkout", "-q", "-b", "feature")
    run_git("mv", "docs/old.md", "archive_old.md")
    run_git("commit", "-q", "-m", "move the doc out of docs/")
    head = run_git("rev-parse", "HEAD")
    changed = docs_impact.git_changed_files(base, head)
    assert sorted(changed) == ["archive_old.md", "docs/old.md"]
    # Moving a doc out of docs/ is a documentation change.
    assert docs_impact.evaluate(body(docs_updated=True), changed) == []


def test_git_diff_keeps_non_ascii_paths_readable(docs_impact: ModuleType, git_repo: Path) -> None:
    base = commit(git_repo, {"README.md": "x\n"}, "base")
    run_git("checkout", "-q", "-b", "feature")
    head = commit(git_repo, {"docs/zażółć.md": "tekst\n"}, "polskie znaki")
    changed = docs_impact.git_changed_files(base, head)
    assert changed == ["docs/zażółć.md"]
    assert docs_impact.is_doc_path(changed[0])


def test_git_diff_of_an_empty_change_is_empty(docs_impact: ModuleType, git_repo: Path) -> None:
    base = commit(git_repo, {"README.md": "x\n"}, "base")
    assert docs_impact.git_changed_files(base, base) == []


def test_a_failing_git_diff_fails_the_check_with_a_constant_message(
    docs_impact: ModuleType, git_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit(git_repo, {"README.md": "x\n"}, "base")
    event = write_event(tmp_path / "event.json", body(docs_updated=True))  # base and head are not real commits
    assert docs_impact.main(event) == 1
    assert docs_impact.MSG_GIT_FAILED in capsys.readouterr().out


# --- only the Documentation impact section counts -----------------------------------

UNTOUCHED = "- [ ] Docs updated\n- [ ] No doc update needed: <state the reason>\n"


def test_a_ticked_item_quoted_in_another_section_is_not_a_declaration(docs_impact: ModuleType) -> None:
    description = (
        "## Description\n\nThe template says:\n\n- [x] Docs updated\n\n"
        f"## Documentation impact\n\n{UNTOUCHED}\n## Checklist\n\n- [x] No doc update needed: not this one\n"
    )
    assert docs_impact.read_declaration(description) == (False, False)
    assert docs_impact.evaluate(description, ["README.md"]) == [docs_impact.MSG_NONE]


def test_a_ticked_item_after_the_section_does_not_count(docs_impact: ModuleType) -> None:
    description = f"## Documentation impact\n\n{UNTOUCHED}\n---\n\n## Checklist\n\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(description) == (False, False)


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_a_ticked_item_in_a_code_block_does_not_count(docs_impact: ModuleType, fence: str) -> None:
    description = in_section(f"{UNTOUCHED}\n{fence}\n- [x] Docs updated\n{fence}\n")
    assert docs_impact.read_declaration(description) == (False, False)


def test_an_unterminated_code_block_hides_everything_after_it(docs_impact: ModuleType) -> None:
    description = in_section(f"{UNTOUCHED}\n```\n- [x] Docs updated\n")
    assert docs_impact.read_declaration(description) == (False, False)
    real_first = in_section("- [x] Docs updated\n- [ ] No doc update needed: <state the reason>\n\n```\nnever closed\n")
    assert docs_impact.read_declaration(real_first) == (True, False)


def test_a_ticked_item_in_an_html_comment_does_not_count(docs_impact: ModuleType) -> None:
    description = in_section(f"<!--\n- [x] Docs updated\n-->\n{UNTOUCHED}")
    assert docs_impact.read_declaration(description) == (False, False)


def test_a_quoted_or_indented_item_is_not_a_declaration(docs_impact: ModuleType) -> None:
    description = in_section("> - [x] Docs updated\n    - [x] No doc update needed: indented\n" + UNTOUCHED)
    assert docs_impact.read_declaration(description) == (False, False)


def test_a_description_without_the_section_is_rejected_with_its_own_message(docs_impact: ModuleType) -> None:
    description = "## Description\n\n- [x] Docs updated\n"
    assert docs_impact.evaluate(description, ["README.md"]) == [docs_impact.MSG_NO_SECTION]
    assert docs_impact.evaluate("", []) == [docs_impact.MSG_NO_SECTION]


def test_the_heading_may_differ_in_case_and_trailing_spaces(docs_impact: ModuleType) -> None:
    description = "## documentation IMPACT  \n\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(description) == (True, False)


def test_a_lower_level_heading_does_not_end_the_section(docs_impact: ModuleType) -> None:
    description = "## Documentation impact\n\n### Why\n\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(description) == (True, False)


def test_a_windows_description_is_read_like_a_unix_one(docs_impact: ModuleType) -> None:
    description = "## Description\r\n\r\ntext\r\n\r\n## Documentation impact\r\n\r\n- [x] Docs updated\r\n\r\n## Checklist\r\n"
    assert docs_impact.read_declaration(description) == (True, False)


# --- the text a reader sees: comments and code blocks as GitHub renders them -----------


def test_an_unterminated_html_comment_hides_the_rest_of_the_description(docs_impact: ModuleType) -> None:
    description = "## Description\n\n<!-- forgot to close this\n\n## Documentation impact\n\n- [x] Docs updated\n"
    assert docs_impact.declaration_section(description) is None
    assert docs_impact.evaluate(description, ["README.md"]) == [docs_impact.MSG_NO_SECTION]


def test_an_unterminated_comment_started_mid_line_also_hides_the_rest(docs_impact: ModuleType) -> None:
    description = in_section(f"{UNTOUCHED}text <!-- never closed\n- [x] Docs updated\n")
    assert docs_impact.read_declaration(description) == (False, False)


def test_a_tick_before_an_unterminated_comment_still_counts(docs_impact: ModuleType) -> None:
    description = in_section("- [x] Docs updated\n- [ ] No doc update needed: <state the reason>\n<!-- never closed\n")
    assert docs_impact.read_declaration(description) == (True, False)


def test_text_around_a_closed_comment_stays_visible(docs_impact: ModuleType) -> None:
    description = in_section("- [x] Docs updated <!-- reviewer note --> \n- [ ] No doc update needed: <state the reason><!---->\n")
    assert docs_impact.read_declaration(description) == (True, False)
    mid_line_start = in_section("note <!-- start\nend -->\n- [x] Docs updated\n")
    assert docs_impact.read_declaration(mid_line_start) == (True, False)


@pytest.mark.parametrize("indent", ["", " ", "  ", "   "])
def test_a_fence_indented_by_up_to_three_spaces_is_a_code_block(docs_impact: ModuleType, indent: str) -> None:
    description = in_section(f"{UNTOUCHED}{indent}```\n- [x] Docs updated\n{indent}```\n")
    assert docs_impact.read_declaration(description) == (False, False)


def test_four_spaces_of_indentation_is_not_a_fence(docs_impact: ModuleType) -> None:
    description = in_section("    ```\n- [x] Docs updated\n- [ ] No doc update needed: <state the reason>\n")
    assert docs_impact.read_declaration(description) == (True, False)


def test_a_fence_needs_a_matching_closing_fence(docs_impact: ModuleType) -> None:
    long_fence = in_section(f"{UNTOUCHED}````\n```\n- [x] Docs updated\n```\n````\n")
    assert docs_impact.read_declaration(long_fence) == (False, False)  # the inner ``` does not close a 4-backtick fence
    other_char = in_section(f"{UNTOUCHED}```\n~~~\n- [x] Docs updated\n~~~\n```\n")
    assert docs_impact.read_declaration(other_char) == (False, False)  # ~~~ does not close a ``` fence
    reopened = in_section("```\ncode\n```\n- [x] Docs updated\n- [ ] No doc update needed: <state the reason>\n")
    assert docs_impact.read_declaration(reopened) == (True, False)  # a closed fence ends


def test_a_backtick_fence_with_a_backtick_in_its_info_string_is_inline_code(docs_impact: ModuleType) -> None:
    description = in_section("``` not a `fence`\n- [x] Docs updated\n- [ ] No doc update needed: <state the reason>\n")
    assert docs_impact.read_declaration(description) == (True, False)


def test_whichever_of_a_fence_and_a_comment_starts_first_wins(docs_impact: ModuleType) -> None:
    fence_in_comment = in_section(f"<!--\n```\n-->\n{UNTOUCHED}- [x] Docs updated\n")
    assert docs_impact.read_declaration(fence_in_comment) == (True, False)  # the fence marker sat inside the comment, so no fence opened
    comment_in_fence = in_section("```\n<!--\n```\n- [x] Docs updated\n- [ ] No doc update needed: <state the reason>\n")
    assert docs_impact.read_declaration(comment_in_fence) == (True, False)  # the comment never started


def test_a_heading_indented_by_up_to_three_spaces_ends_the_section(docs_impact: ModuleType) -> None:
    three = "## Documentation impact\n\n- [ ] Docs updated\n   ## Checklist\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(three) == (False, False)
    four = "## Documentation impact\n\n    ## not a heading\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(four) == (True, False)


def test_a_section_heading_may_be_indented_by_up_to_three_spaces(docs_impact: ModuleType) -> None:
    assert docs_impact.read_declaration("   ## Documentation impact\n\n- [x] Docs updated\n") == (True, False)
    assert docs_impact.read_declaration("    ## Documentation impact\n\n- [x] Docs updated\n") == (False, False)


def test_a_stray_closing_arrow_does_not_close_a_later_comment(docs_impact: ModuleType) -> None:
    description = in_section(f"{UNTOUCHED}--> <!-- never closed\n- [x] Docs updated\n")
    assert docs_impact.read_declaration(description) == (False, False)


def test_text_before_a_comment_is_kept_once_even_after_a_stray_closing_arrow(docs_impact: ModuleType) -> None:
    assert docs_impact.visible_text("a --> b <!-- c --> d") == "a --> b  d"


def test_text_after_a_comment_that_opens_a_line_is_part_of_the_comment_block(docs_impact: ModuleType) -> None:
    # CommonMark HTML block: the whole line that contains the closing arrow is raw HTML.
    glued = in_section("<!-- c -->- [x] Docs updated\n")
    assert docs_impact.read_declaration(glued) == (False, False)
    multi = in_section("<!-- c\nstill comment -->- [x] Docs updated\n")
    assert docs_impact.read_declaration(multi) == (False, False)


def test_text_after_a_comment_that_opens_mid_line_stays_visible(docs_impact: ModuleType) -> None:
    assert docs_impact.visible_text("a <!-- c -->\n- [x] Docs updated") == "a \n- [x] Docs updated"
    assert docs_impact.visible_text("a <!-- c\nd --> e\nf") == "a \n e\nf"


def test_a_setext_heading_ends_the_section(docs_impact: ModuleType) -> None:
    for underline in ("---", "===", "  --", "="):
        body = f"## Documentation impact\n\n- [ ] Docs updated\n\nNext\n{underline}\n- [x] Docs updated\n"
        assert docs_impact.read_declaration(body) == (False, False), underline


def test_a_rule_after_a_list_item_or_a_blank_line_is_not_a_setext_heading(docs_impact: ModuleType) -> None:
    after_item = "## Documentation impact\n\n- [x] Docs updated\n---\n"
    after_blank = "## Documentation impact\n\n- [x] Docs updated\n\n---\n"
    assert docs_impact.read_declaration(after_item) == (True, False)
    assert docs_impact.read_declaration(after_blank) == (True, False)


def test_a_comment_that_closes_on_its_own_opening_line_hides_nothing_after_it(docs_impact: ModuleType) -> None:
    description = in_section("<!-->\n- [x] Docs updated\n")
    assert docs_impact.read_declaration(description) == (True, False)


def test_an_inline_comment_after_a_block_comment_keeps_the_text_after_its_arrow(docs_impact: ModuleType) -> None:
    assert docs_impact.visible_text("<!-- a\nb -->\nnote <!-- c\nd --> e") == "note \n e"


def test_a_rule_after_a_blank_line_does_not_end_the_section(docs_impact: ModuleType) -> None:
    description = "## Documentation impact\n\n- [ ] Docs updated\n\n---\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(description) == (True, False)


@pytest.mark.parametrize("heading", ["#", "##"])
def test_an_empty_atx_heading_ends_the_section(docs_impact: ModuleType, heading: str) -> None:
    description = f"## Documentation impact\n\n- [ ] Docs updated\n\n{heading}\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(description) == (False, False)


@pytest.mark.parametrize(
    "text",
    ["#hashtag", "#5", "-foo", "+x", "*x", "1.x", "<3 you", "Text\n    indented continuation", "Text\n\ttabbed continuation"],
)
def test_text_that_only_looks_like_a_block_marker_is_a_setext_heading(docs_impact: ModuleType, text: str) -> None:
    body = f"## Documentation impact\n\n- [ ] Docs updated\n\n{text}\n---\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(body) == (False, False)


@pytest.mark.parametrize("block", ["- item", "1. item", "> quote", "    indented code", "***"])
def test_a_rule_after_another_block_does_not_end_the_section(docs_impact: ModuleType, block: str) -> None:
    body = f"## Documentation impact\n\n- [ ] Docs updated\n\n{block}\n---\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(body) == (True, False)


@pytest.mark.parametrize("marker", ["+", "-", "*", "1.", "2.", "3)"])
def test_an_empty_list_item_cannot_interrupt_a_paragraph(docs_impact: ModuleType, marker: str) -> None:
    body = f"## Documentation impact\n\n- [ ] Docs updated\n\nText\n{marker}\n===\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(body) == (False, False)


@pytest.mark.parametrize("marker", ["2. x", "10) x", "7. x"])
def test_an_ordered_item_not_starting_at_one_cannot_interrupt_a_paragraph(docs_impact: ModuleType, marker: str) -> None:
    body = f"## Documentation impact\n\n- [ ] Docs updated\n\nText\n{marker}\n---\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(body) == (False, False)


@pytest.mark.parametrize("marker", ["1. x", "01. x", "- x", "* x"])
def test_a_list_item_that_can_interrupt_a_paragraph_does_end_it(docs_impact: ModuleType, marker: str) -> None:
    body = f"## Documentation impact\n\n- [ ] Docs updated\n\nText\n{marker}\n---\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(body) == (True, False)


def test_a_rule_after_a_paragraph_and_a_blank_line_does_not_end_the_section(docs_impact: ModuleType) -> None:
    body = "## Documentation impact\n\n- [ ] Docs updated\n\nSome text\n\n---\n- [x] Docs updated\n"
    assert docs_impact.read_declaration(body) == (True, False)
