"""Tests for scripts/release_preflight.py: the commit being released must have passed its CI checks."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_preflight.py"
CI = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"


@pytest.fixture(scope="module")
def preflight() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_preflight", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SUITE = 500  # the check suite of the ci.yml push run on main
SUITES = {SUITE}
PR_SUITE = 600  # the check suite of the same commit's pull request run


def run(
    name: str, run_id: int, conclusion: str | None = "success", status: str = "completed", app: str = "github-actions", suite: int = SUITE
) -> dict:
    return {"id": run_id, "name": name, "status": status, "conclusion": conclusion, "app": app, "check_suite": suite}


def all_green(preflight: ModuleType) -> list[dict]:
    return [run(name, i) for i, name in enumerate(preflight.REQUIRED, start=100)]


def test_every_required_check_green_means_the_commit_may_be_released(preflight: ModuleType) -> None:
    assert preflight.problems(all_green(preflight), SUITES) == []


def test_other_checks_do_not_matter(preflight: ModuleType) -> None:
    runs = [*all_green(preflight), run("Coverage signals (Codecov, SonarCloud)", 1, "failure"), run("CodeQL", 2, "failure", app="github-advanced-security")]
    assert preflight.problems(runs, SUITES) == []


def test_a_required_check_that_never_ran_is_reported_by_name(preflight: ModuleType) -> None:
    runs = [r for r in all_green(preflight) if r["name"] != "Hassfest"]
    assert preflight.problems(runs, SUITES) == [preflight.MSG_MISSING.format(name="Hassfest")]


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "skipped", "timed_out", "neutral", "action_required", None])
def test_a_required_check_that_did_not_succeed_blocks_the_release(preflight: ModuleType, conclusion: str | None) -> None:
    runs = all_green(preflight)
    runs[0] = run(preflight.REQUIRED[0], 100, conclusion)
    assert preflight.problems(runs, SUITES) == [preflight.MSG_FAILED.format(name=preflight.REQUIRED[0])]


@pytest.mark.parametrize("status", ["queued", "in_progress", "waiting", "pending"])
def test_a_required_check_still_running_blocks_the_release_with_its_own_message(preflight: ModuleType, status: str) -> None:
    runs = all_green(preflight)
    runs[1] = run(preflight.REQUIRED[1], 101, None, status)
    assert preflight.problems(runs, SUITES) == [preflight.MSG_RUNNING.format(name=preflight.REQUIRED[1])]


def test_a_rerun_counts_instead_of_the_old_failure(preflight: ModuleType) -> None:
    runs = [r for r in all_green(preflight) if r["name"] != "HACS validation"]
    runs += [run("HACS validation", 4, "failure"), run("HACS validation", 5000, "success")]  # a network error, then a re-run
    assert preflight.problems(runs, SUITES) == []


def test_a_newer_failure_beats_an_older_success(preflight: ModuleType) -> None:
    runs = [*all_green(preflight), run("Tests (pytest)", 9999, "failure")]
    assert preflight.problems(runs, SUITES) == [preflight.MSG_FAILED.format(name="Tests (pytest)")]


def test_a_check_with_the_right_name_from_another_app_does_not_count(preflight: ModuleType) -> None:
    runs = [r for r in all_green(preflight) if r["name"] != "Lint (ruff)"] + [run("Lint (ruff)", 1, "success", app="some-other-app")]
    assert preflight.problems(runs, SUITES) == [preflight.MSG_MISSING.format(name="Lint (ruff)")]


def test_several_problems_are_all_listed(preflight: ModuleType) -> None:
    runs = [r for r in all_green(preflight) if r["name"] not in {"Hassfest", "Release bookkeeping"}]
    assert len(preflight.problems(runs, SUITES)) == 2


def test_malformed_runs_are_ignored_not_crashing(preflight: ModuleType) -> None:
    junk = [{}, {"name": 5, "id": 1, "app": "github-actions"}, {"name": "Hassfest", "app": "github-actions"}, {"name": "Hassfest", "id": "7", "app": "github-actions"}]
    runs = [r for r in all_green(preflight) if r["name"] != "Hassfest"] + junk
    assert preflight.problems(runs, SUITES) == [preflight.MSG_MISSING.format(name="Hassfest")]


def test_required_names_are_the_job_names_of_ci_yml(preflight: ModuleType) -> None:
    """A renamed job would otherwise turn every release into 'check is missing'."""
    names = set(re.findall(r"^    name: (.+)$", CI.read_text(encoding="utf-8"), re.MULTILINE))
    assert set(preflight.REQUIRED) <= names, sorted(set(preflight.REQUIRED) - names)


def test_hacs_validation_is_required_to_release_though_not_to_merge(preflight: ModuleType) -> None:
    assert "HACS validation" in preflight.REQUIRED


def test_the_documentation_impact_check_is_not_required_because_it_never_runs_on_main(preflight: ModuleType) -> None:
    assert "Documentation impact declaration" not in preflight.REQUIRED


COMMIT = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"


def write_lines(path: Path, runs: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in runs) + "\n", encoding="utf-8")
    return path


def write_mainline(path: Path, commits: list[str]) -> Path:
    path.write_text("\n".join(commits) + "\n", encoding="utf-8")
    return path


def push_run(commit: str = COMMIT, suite: int = SUITE, event: str = "push", branch: str = "main") -> dict:
    return {"id": 77, "check_suite_id": suite, "event": event, "head_branch": branch, "head_sha": commit}


def run_main(
    preflight: ModuleType,
    tmp_path: Path,
    runs: list[dict],
    mainline: list[str] | None = None,
    commit: str = COMMIT,
    workflow_runs: list[dict] | None = None,
) -> int:
    runs_file = write_lines(tmp_path / "runs.jsonl", runs)
    workflow_file = write_lines(tmp_path / "workflow-runs.jsonl", [push_run()] if workflow_runs is None else workflow_runs)
    mainline_file = write_mainline(tmp_path / "mainline.txt", [OTHER, COMMIT] if mainline is None else mainline)
    return preflight.main([str(runs_file), str(workflow_file), str(mainline_file), commit])


def test_main_succeeds_on_a_mainline_commit_with_green_checks(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_main(preflight, tmp_path, all_green(preflight)) == 0
    assert "on main" in capsys.readouterr().out


def test_main_fails_and_names_the_check_on_stderr(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runs = all_green(preflight)
    runs[2] = run(preflight.REQUIRED[2], 102, "failure")
    assert run_main(preflight, tmp_path, runs) == 1
    assert preflight.REQUIRED[2] in capsys.readouterr().err


def test_main_fails_on_an_empty_checks_file(preflight: ModuleType, tmp_path: Path) -> None:
    assert run_main(preflight, tmp_path, []) == 1


def test_main_fails_when_the_commit_is_not_in_the_mainline_even_with_green_checks(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_main(preflight, tmp_path, all_green(preflight), mainline=[OTHER]) == 1
    assert preflight.MSG_NOT_MAINLINE in capsys.readouterr().err


def test_main_reports_both_a_side_commit_and_a_failing_check(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runs = all_green(preflight)
    runs[0] = run(preflight.REQUIRED[0], 100, "failure")
    assert run_main(preflight, tmp_path, runs, mainline=[]) == 1
    err = capsys.readouterr().err
    assert preflight.MSG_NOT_MAINLINE in err
    assert preflight.REQUIRED[0] in err


@pytest.mark.parametrize("content", ["not json\n", "[1, 2]\n", "42\n"])
def test_main_fails_cleanly_on_a_file_that_is_not_json_lines(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str) -> None:
    runs_file = tmp_path / "runs.jsonl"
    runs_file.write_text(content, encoding="utf-8")
    workflow_file = write_lines(tmp_path / "workflow-runs.jsonl", [push_run()])
    mainline_file = write_mainline(tmp_path / "mainline.txt", [COMMIT])
    assert preflight.main([str(runs_file), str(workflow_file), str(mainline_file), COMMIT]) == 1
    assert content.strip() not in capsys.readouterr().err


def test_main_fails_cleanly_on_missing_files(preflight: ModuleType, tmp_path: Path) -> None:
    runs_file = write_lines(tmp_path / "runs.jsonl", all_green(preflight))
    workflow_file = write_lines(tmp_path / "workflow-runs.jsonl", [push_run()])
    nope = str(tmp_path / "nope")
    assert preflight.main([nope, nope, nope, COMMIT]) == 1
    assert preflight.main([str(runs_file), nope, nope, COMMIT]) == 1
    assert preflight.main([str(runs_file), str(workflow_file), nope, COMMIT]) == 1


def test_main_wants_exactly_four_arguments(preflight: ModuleType) -> None:
    assert preflight.main([]) == 2
    assert preflight.main(["a"]) == 2
    assert preflight.main(["a", "b", "c"]) == 2
    assert preflight.main(["a", "b", "c", "d", "e"]) == 2


def test_conclusion_text_from_the_api_is_never_echoed(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runs = all_green(preflight)
    runs[0] = run(preflight.REQUIRED[0], 100, "::error::injected")
    assert run_main(preflight, tmp_path, runs) == 1
    assert "injected" not in capsys.readouterr().err


# --- the mainline: first-parent history of main, not general ancestry -------------------


def test_on_mainline_finds_a_full_sha_in_the_list(preflight: ModuleType) -> None:
    assert preflight.on_mainline(COMMIT, [OTHER, COMMIT])
    assert preflight.on_mainline(f"  {COMMIT.upper()}\n", [f"{COMMIT}\n"])


@pytest.mark.parametrize("commit", ["", " ", "0123456", COMMIT[:39], COMMIT + "0", "g" * 40, "refs/heads/main", "HEAD"])
def test_on_mainline_rejects_anything_that_is_not_a_full_sha(preflight: ModuleType, commit: str) -> None:
    assert not preflight.on_mainline(commit, [commit, COMMIT])


def test_on_mainline_does_not_match_a_prefix_or_a_substring(preflight: ModuleType) -> None:
    assert not preflight.on_mainline(COMMIT, [COMMIT[:20], COMMIT + "0", "x" + COMMIT])
    assert not preflight.on_mainline(COMMIT, [])


def git(repo: Path, *args: str) -> str:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid", "PATH": "/usr/bin:/bin"}
    out = subprocess.run(["/usr/bin/git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout
    return out.strip()


def test_a_commit_of_a_merged_branch_is_not_on_the_mainline_but_the_merge_commit_is(preflight: ModuleType, tmp_path: Path) -> None:
    """The case from the review: with merge commits, the release-bump commit of a pull request branch is an
    ancestor of main, so `git merge-base --is-ancestor` accepts it; the first-parent history does not."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("1")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "checkout", "-q", "-b", "release-pr")
    (repo / "a.txt").write_text("version bump")
    git(repo, "commit", "-q", "-am", "bump the version")
    bump = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "main")
    (repo / "b.txt").write_text("another change on main")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "another change on main")
    git(repo, "merge", "-q", "--no-ff", "-m", "Merge pull request", "release-pr")
    merge = git(repo, "rev-parse", "HEAD")
    side_is_ancestor = subprocess.run(["/usr/bin/git", "-C", str(repo), "merge-base", "--is-ancestor", bump, "main"]).returncode == 0
    assert side_is_ancestor, "precondition: the old check would have accepted the side commit"
    mainline = git(repo, "rev-list", "--first-parent", "main").splitlines()
    assert preflight.on_mainline(merge, mainline)
    assert not preflight.on_mainline(bump, mainline)


def test_a_fast_forwarded_release_commit_is_on_the_mainline(preflight: ModuleType, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("1")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "checkout", "-q", "-b", "release-pr")
    (repo / "a.txt").write_text("2")
    git(repo, "commit", "-q", "-am", "bump")
    bump = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--ff-only", "release-pr")
    assert preflight.on_mainline(bump, git(repo, "rev-list", "--first-parent", "main").splitlines())


def test_release_runs_never_cancel_each_other_and_do_not_share_one_pending_slot() -> None:
    """A concurrency group keeps one pending run and cancels older pending ones: with one group for every tag,
    three tags pushed close together would lose a draft. The group is per ref and nothing is cancelled."""
    text = RELEASE.read_text(encoding="utf-8")
    block = re.search(r"^concurrency:\n((?:  .+\n)+)", text, re.MULTILINE)
    assert block is not None
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in block.group(1)
    assert "cancel-in-progress: false" in block.group(1)


# --- provenance: the checks must come from the push run of ci.yml on main -------------------


def test_checks_of_the_pull_request_run_do_not_count_for_a_fast_forwarded_commit(preflight: ModuleType) -> None:
    """A fast-forwarded release commit is also the head of its pull request, so it already carries successful,
    same-named runs of that pull request; before the push run on main has registered its jobs they would pass."""
    pull_request_checks = [run(name, i, suite=PR_SUITE) for i, name in enumerate(preflight.REQUIRED, start=300)]
    assert preflight.problems(pull_request_checks, SUITES) == [preflight.MSG_MISSING.format(name=n) for n in preflight.REQUIRED]


def test_a_pull_request_success_does_not_hide_a_failing_push_run_check(preflight: ModuleType) -> None:
    runs = [*all_green(preflight), run("Tests (pytest)", 9000, suite=PR_SUITE)]  # newer id, wrong suite
    runs = [r if r["name"] != "Tests (pytest)" or r["check_suite"] == PR_SUITE else run("Tests (pytest)", 150, "failure") for r in runs]
    assert preflight.problems(runs, SUITES) == [preflight.MSG_FAILED.format(name="Tests (pytest)")]


def test_without_a_push_run_there_is_one_clear_problem(preflight: ModuleType) -> None:
    assert preflight.problems(all_green(preflight), set()) == [preflight.MSG_NO_PUSH_RUN]


def test_push_suites_keeps_only_push_runs_on_main_for_this_commit(preflight: ModuleType) -> None:
    runs = [
        push_run(),
        push_run(suite=1, event="pull_request"),
        push_run(suite=2, branch="some-branch"),
        push_run(suite=3, commit=OTHER),
        push_run(suite=4, commit=COMMIT.upper()),
        {"check_suite_id": "5", "event": "push", "head_branch": "main", "head_sha": COMMIT},
        {"event": "push", "head_branch": "main", "head_sha": COMMIT},
        {},
    ]
    assert preflight.push_suites(runs, COMMIT) == {SUITE, 4}


def test_main_refuses_a_commit_whose_only_green_checks_belong_to_its_pull_request(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pull_request_checks = [run(name, i, suite=PR_SUITE) for i, name in enumerate(preflight.REQUIRED, start=300)]
    code = run_main(preflight, tmp_path, pull_request_checks, workflow_runs=[push_run(suite=PR_SUITE, event="pull_request")])
    assert code == 1
    assert preflight.MSG_NO_PUSH_RUN in capsys.readouterr().err


def test_main_accepts_checks_of_the_push_run_even_when_a_pull_request_run_exists(preflight: ModuleType, tmp_path: Path) -> None:
    runs = [*all_green(preflight), *[run(name, i, "failure", suite=PR_SUITE) for i, name in enumerate(preflight.REQUIRED, start=900)]]
    assert run_main(preflight, tmp_path, runs, workflow_runs=[push_run(), push_run(suite=PR_SUITE, event="pull_request")]) == 0
