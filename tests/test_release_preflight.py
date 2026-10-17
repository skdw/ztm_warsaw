"""Tests for scripts/release_preflight.py: the commit being released must have passed its CI checks."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_preflight.py"
CI = ROOT / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def preflight() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_preflight", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(name: str, run_id: int, conclusion: str | None = "success", status: str = "completed", app: str = "github-actions") -> dict:
    return {"id": run_id, "name": name, "status": status, "conclusion": conclusion, "app": app}


def all_green(preflight: ModuleType) -> list[dict]:
    return [run(name, i) for i, name in enumerate(preflight.REQUIRED, start=100)]


def test_every_required_check_green_means_the_commit_may_be_released(preflight: ModuleType) -> None:
    assert preflight.problems(all_green(preflight)) == []


def test_other_checks_do_not_matter(preflight: ModuleType) -> None:
    runs = [*all_green(preflight), run("Coverage signals (Codecov, SonarCloud)", 1, "failure"), run("CodeQL", 2, "failure", app="github-advanced-security")]
    assert preflight.problems(runs) == []


def test_a_required_check_that_never_ran_is_reported_by_name(preflight: ModuleType) -> None:
    runs = [r for r in all_green(preflight) if r["name"] != "Hassfest"]
    assert preflight.problems(runs) == [preflight.MSG_MISSING.format(name="Hassfest")]


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "skipped", "timed_out", "neutral", "action_required", None])
def test_a_required_check_that_did_not_succeed_blocks_the_release(preflight: ModuleType, conclusion: str | None) -> None:
    runs = all_green(preflight)
    runs[0] = run(preflight.REQUIRED[0], 100, conclusion)
    assert preflight.problems(runs) == [preflight.MSG_FAILED.format(name=preflight.REQUIRED[0])]


@pytest.mark.parametrize("status", ["queued", "in_progress", "waiting", "pending"])
def test_a_required_check_still_running_blocks_the_release_with_its_own_message(preflight: ModuleType, status: str) -> None:
    runs = all_green(preflight)
    runs[1] = run(preflight.REQUIRED[1], 101, None, status)
    assert preflight.problems(runs) == [preflight.MSG_RUNNING.format(name=preflight.REQUIRED[1])]


def test_a_rerun_counts_instead_of_the_old_failure(preflight: ModuleType) -> None:
    runs = [r for r in all_green(preflight) if r["name"] != "HACS validation"]
    runs += [run("HACS validation", 4, "failure"), run("HACS validation", 5000, "success")]  # a network error, then a re-run
    assert preflight.problems(runs) == []


def test_a_newer_failure_beats_an_older_success(preflight: ModuleType) -> None:
    runs = [*all_green(preflight), run("Tests (pytest)", 9999, "failure")]
    assert preflight.problems(runs) == [preflight.MSG_FAILED.format(name="Tests (pytest)")]


def test_a_check_with_the_right_name_from_another_app_does_not_count(preflight: ModuleType) -> None:
    runs = [r for r in all_green(preflight) if r["name"] != "Lint (ruff)"] + [run("Lint (ruff)", 1, "success", app="some-other-app")]
    assert preflight.problems(runs) == [preflight.MSG_MISSING.format(name="Lint (ruff)")]


def test_several_problems_are_all_listed(preflight: ModuleType) -> None:
    runs = [r for r in all_green(preflight) if r["name"] not in {"Hassfest", "Release bookkeeping"}]
    assert len(preflight.problems(runs)) == 2


def test_malformed_runs_are_ignored_not_crashing(preflight: ModuleType) -> None:
    junk = [{}, {"name": 5, "id": 1, "app": "github-actions"}, {"name": "Hassfest", "app": "github-actions"}, {"name": "Hassfest", "id": "7", "app": "github-actions"}]
    runs = [r for r in all_green(preflight) if r["name"] != "Hassfest"] + junk
    assert preflight.problems(runs) == [preflight.MSG_MISSING.format(name="Hassfest")]


def test_required_names_are_the_job_names_of_ci_yml(preflight: ModuleType) -> None:
    """A renamed job would otherwise turn every release into 'check is missing'."""
    names = set(re.findall(r"^    name: (.+)$", CI.read_text(encoding="utf-8"), re.MULTILINE))
    assert set(preflight.REQUIRED) <= names, sorted(set(preflight.REQUIRED) - names)


def test_hacs_validation_is_required_to_release_though_not_to_merge(preflight: ModuleType) -> None:
    assert "HACS validation" in preflight.REQUIRED


def test_the_documentation_impact_check_is_not_required_because_it_never_runs_on_main(preflight: ModuleType) -> None:
    assert "Documentation impact declaration" not in preflight.REQUIRED


def write_lines(path: Path, runs: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in runs) + "\n", encoding="utf-8")
    return path


def test_main_succeeds_on_a_green_file(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert preflight.main([str(write_lines(tmp_path / "runs.jsonl", all_green(preflight)))]) == 0
    assert "succeeded" in capsys.readouterr().out


def test_main_fails_and_names_the_check_on_stderr(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runs = all_green(preflight)
    runs[2] = run(preflight.REQUIRED[2], 102, "failure")
    assert preflight.main([str(write_lines(tmp_path / "runs.jsonl", runs))]) == 1
    assert preflight.REQUIRED[2] in capsys.readouterr().err


def test_main_fails_on_an_empty_file(preflight: ModuleType, tmp_path: Path) -> None:
    assert preflight.main([str(write_lines(tmp_path / "runs.jsonl", []))]) == 1


@pytest.mark.parametrize("content", ["not json\n", "[1, 2]\n", "42\n"])
def test_main_fails_cleanly_on_a_file_that_is_not_json_lines(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str) -> None:
    path = tmp_path / "runs.jsonl"
    path.write_text(content, encoding="utf-8")
    assert preflight.main([str(path)]) == 1
    assert content.strip() not in capsys.readouterr().err


def test_main_fails_cleanly_on_a_missing_file(preflight: ModuleType, tmp_path: Path) -> None:
    assert preflight.main([str(tmp_path / "nope.jsonl")]) == 1


def test_main_wants_exactly_one_argument(preflight: ModuleType) -> None:
    assert preflight.main([]) == 2
    assert preflight.main(["a", "b"]) == 2


def test_conclusion_text_from_the_api_is_never_echoed(preflight: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runs = all_green(preflight)
    runs[0] = run(preflight.REQUIRED[0], 100, "::error::injected")
    assert preflight.main([str(write_lines(tmp_path / "runs.jsonl", runs))]) == 1
    assert "injected" not in capsys.readouterr().err
