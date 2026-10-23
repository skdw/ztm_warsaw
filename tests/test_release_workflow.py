"""The release from main: it waits for every job CI releases on, and only a beta is published without a hand."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(name: str) -> dict:
    """A workflow file as a dict."""
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def test_the_release_job_waits_for_every_job_the_preflight_requires():
    """A job missing from ``needs`` would let a release start while a required check is still running or has failed."""
    spec = importlib.util.spec_from_file_location("release_preflight", ROOT / "scripts" / "release_preflight.py")
    preflight = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preflight)
    jobs = _load("ci.yml")["jobs"]
    by_name = {job["name"]: job_id for job_id, job in jobs.items()}
    assert set(jobs["release"]["needs"]) >= {by_name[name] for name in preflight.REQUIRED}


def test_the_release_job_runs_only_on_a_push_to_main_and_calls_the_release_workflow():
    """On a pull request the job is skipped, so it never needs write permissions there."""
    job = _load("ci.yml")["jobs"]["release"]
    assert "refs/heads/main" in job["if"]
    assert "'push'" in job["if"]
    assert job["uses"] == "./.github/workflows/release.yml"


def test_the_release_workflow_can_be_called_and_still_starts_on_a_version_tag():
    """``on`` is read by YAML as the boolean True."""
    triggers = _load("release.yml")[True]
    assert "workflow_call" in triggers
    assert triggers["push"]["tags"]


def test_a_beta_is_published_as_a_pre_release_and_a_stable_version_stays_a_draft():
    """Publishing a stable version is the maintainer's decision; a beta goes out by itself."""
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    beta, stable = text.index('if [[ "$TAG" == *b[0-9]* ]]'), text.index("else", text.index('if [[ "$TAG" == *b[0-9]* ]]'))
    assert "--prerelease" in text[beta:stable]
    assert "--draft" not in text[beta:stable]
    assert "--draft" in text[stable:]


def test_a_version_that_has_a_tag_is_skipped():
    """Every later push to main finds the tag of the version and does nothing."""
    job = _load("release.yml")["jobs"]["release"]
    assert job["if"] == "needs.plan.outputs.skip != 'true'"


def test_every_push_to_main_has_a_ci_run_of_its_own_so_no_version_commit_is_skipped():
    """A concurrency group keeps one pending run: with one group for main, a run of a commit that bumped the version could be cancelled."""
    group = _load("ci.yml")["concurrency"]["group"]
    assert "github.sha" in group
    assert "!= 'refs/heads/main'" in _load("ci.yml")["concurrency"]["cancel-in-progress"]  # nothing on main is cancelled
