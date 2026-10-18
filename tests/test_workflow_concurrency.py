"""The Documentation impact workflow must never have a run cancelled.

Its check is required to merge. When the newest run of a required check on the head commit is cancelled,
GitHub shows the check as not passed and the pull request stays blocked until the run is repeated by hand.
Two runs for one commit are normal for this workflow (a push, then a description edit a few seconds later),
and with any shared concurrency group GitHub cancels one of them.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def concurrency_of(name: str) -> dict:
    workflow = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert "concurrency" in workflow, f"{name} has no top-level concurrency block (the playbook's verify-tier wants one)"
    return workflow["concurrency"]


def test_docs_impact_never_cancels_a_run():
    block = concurrency_of("docs-impact.yml")
    assert block["cancel-in-progress"] is False
    assert "github.run_id" in block["group"], "one group per run, so no run can replace another"


def test_docs_impact_group_does_not_depend_on_the_pull_request_or_the_commit():
    group = concurrency_of("docs-impact.yml")["group"]
    for shared in ("pull_request.number", "head.sha", "github.ref", "github.sha"):
        assert shared not in group, f"{shared} in the group would let two runs for one pull request share it"
