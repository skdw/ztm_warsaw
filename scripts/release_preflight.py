"""Checks that the commit being released passed the CI checks that matter.

Used by .github/workflows/release.yml after a version tag is pushed. The workflow
saves the check runs of the tagged commit (``gh api .../commits/<sha>/check-runs``,
one JSON object per line: id, name, status, conclusion, app) and passes the file here.
Every check in REQUIRED must have completed with ``success``, as reported by the
GitHub Actions app; for a check that ran more than once (a re-run) the newest run
counts. A check from any other app, with the same name, does not count.

REQUIRED is the set of jobs of ci.yml that run on a push to main. It is the branch
protection list minus "Documentation impact declaration" (that check only runs on
pull requests, so a merge commit never has it) plus "HACS validation" (not required
to merge, because it needs the network, but required to release). The names are the
``name:`` of the jobs in ci.yml; a test keeps the two in step.

Messages are built from constants only: the check names below, never text from the
API.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

REQUIRED = (
    "Lint (ruff)",
    "Type check (mypy)",
    "Tests (pytest)",
    "Hassfest",
    "Dependency audit (pip-audit)",
    "Secret scan (gitleaks)",
    "Lint workflows (actionlint, zizmor)",
    "Release bookkeeping",
    "HACS validation",
)
APP = "github-actions"

MSG_MISSING = "The tagged commit has no '{name}' check from GitHub Actions. Wait for CI on main to finish, or push the tag on a commit that went through main."
MSG_RUNNING = "The '{name}' check on the tagged commit has not finished. Re-run this workflow when it has."
MSG_FAILED = "The '{name}' check on the tagged commit did not succeed. Fix it (or re-run it if it was a network error) before releasing."


def newest_runs(runs: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """The newest GitHub Actions run of each check name (the highest id)."""
    newest: dict[str, Mapping[str, Any]] = {}
    for run in runs:
        name = run.get("name")
        if run.get("app") != APP or not isinstance(name, str):
            continue
        run_id = run.get("id")
        if not isinstance(run_id, int):
            continue
        previous = newest.get(name)
        if previous is None or run_id > previous["id"]:
            newest[name] = run
    return newest


def problems(runs: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return what keeps the commit from being released; an empty list means it may be."""
    newest = newest_runs(runs)
    found: list[str] = []
    for name in REQUIRED:
        run = newest.get(name)
        if run is None:
            found.append(MSG_MISSING.format(name=name))
        elif run.get("status") != "completed":
            found.append(MSG_RUNNING.format(name=name))
        elif run.get("conclusion") != "success":
            found.append(MSG_FAILED.format(name=name))
    return found


def read_runs(path: Path) -> list[dict[str, Any]]:
    """Parse the JSON-lines file written by the workflow; a line that is not an object is an error."""
    runs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        run = json.loads(line)
        if not isinstance(run, dict):
            raise ValueError("the check-runs file holds a line that is not a JSON object")
        runs.append(run)
    return runs


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: release_preflight.py <check-runs.jsonl>", file=sys.stderr)
        return 2
    try:
        runs = read_runs(Path(args[0]))
    except (OSError, ValueError):
        print("release-preflight: the check-runs file is missing or not valid JSON lines.", file=sys.stderr)
        return 1
    found = problems(runs)
    if found:
        for problem in found:
            print(f"release-preflight: {problem}", file=sys.stderr)
        return 1
    print("release-preflight: every required CI check on the tagged commit succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
