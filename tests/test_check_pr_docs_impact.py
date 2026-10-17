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
    spec = importlib.util.spec_from_file_location("check_pr_docs_impact", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def body(docs_updated: bool = False, no_update: str | None = None, newline: str = "\n") -> str:
    lines = [
        "## Documentation impact",
        "",
        f"- [{'x' if docs_updated else ' '}] Docs updated",
        f"- [{'x' if no_update is not None else ' '}] No doc update needed: {no_update or '<state the reason>'}",
    ]
    return newline.join(lines) + newline


def write_event(path: Path, pr_body: str | None, login: str = "solarssk") -> str:
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
    ticked = "- [x] Docs updated\n- [x] No doc update needed: <state the reason>\n"
    assert docs_impact.read_declaration(ticked) == (True, False)
    only_placeholder = "- [x] No doc update needed: <state the reason>\n"
    assert docs_impact.read_declaration(only_placeholder) == (False, False)
    assert docs_impact.evaluate(only_placeholder, []) == [docs_impact.MSG_NEEDS_REASON]


@pytest.mark.parametrize("mark", ["x", "X"])
def test_the_tick_may_be_lower_or_upper_case(docs_impact: ModuleType, mark: str) -> None:
    docs = f"- [{mark}] Docs updated\n- [ ] No doc update needed: <state the reason>\n"
    no_docs = f"- [ ] Docs updated\n- [{mark}] No doc update needed: tests only\n"
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
    assert docs_impact.MSG_NONE in capsys.readouterr().out


def test_main_diffs_base_and_head_from_the_event(docs_impact: ModuleType, tmp_path: Path) -> None:
    seen: list[tuple[str, str]] = []

    def fake_diff(base: str, head: str) -> list[str]:
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
    hostile = "- [x] Docs updated\n- [x] No doc update needed: ::error::pwned %0A\n"
    assert docs_impact.main(write_event(tmp_path / "h.json", hostile), lambda _b, _h: ["a.py"]) == 1
    out = capsys.readouterr().out
    assert "pwned" not in out
    assert docs_impact.MSG_BOTH in out
    assert docs_impact.MSG_EDIT_HINT in out


# --- the real git diff -----------------------------------------------------------


@pytest.fixture
def git_repo(docs_impact: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    git = shutil.which("git")
    assert git is not None
    monkeypatch.setattr(docs_impact, "GIT", git)
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    run_git("init", "-q", "-b", "main")
    return repo


def run_git(*args: str) -> str:
    git = shutil.which("git")
    assert git is not None
    identity = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"]
    return subprocess.run([git, *identity, *args], check=True, capture_output=True, text=True).stdout.strip()


def commit(repo: Path, files: dict[str, str | None], message: str) -> str:
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
