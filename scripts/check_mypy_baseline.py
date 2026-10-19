"""Runs mypy on the integration and compares its diagnostics exactly with .github/mypy-baseline.txt.

CI (the "mypy" step of .github/workflows/ci.yml) and contributors run the same thing:

    python scripts/check_mypy_baseline.py            check
    python scripts/check_mypy_baseline.py --update   rewrite the entries of the baseline

A plain ``mypy custom_components/ztm_warsaw`` on a clean checkout prints the known
errors and exits with status 1, so it cannot tell a contributor whether they added one.

The baseline is an exact list, not a count. It holds one line per known diagnostic,
with the line and column numbers dropped so that unrelated edits do not change it. The
check fails when mypy reports a diagnostic that is not in the list (so fixing one error
cannot hide a new one), when the list still holds an error mypy no longer reports (so the
list shrinks as errors are fixed), and when mypy cannot run at all. When the list is
empty, replace this check with a plain ``mypy custom_components/ztm_warsaw``.

Messages are constants; the only text from outside is mypy's own output, printed as it is.
"""

from __future__ import annotations

import difflib
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

BASELINE = Path(".github/mypy-baseline.txt")
TARGET = "custom_components/ztm_warsaw"
DEFAULT_HEADER = (
    "# Known mypy diagnostics: path, message and code, with line numbers dropped so that\n"
    "# unrelated edits do not change the list. Compared exactly by scripts/check_mypy_baseline.py\n"
    "# (the \"mypy\" step of workflows/ci.yml): a diagnostic missing from this list fails the job,\n"
    "# and so does an entry that mypy no longer reports. Remove an entry in the pull request that\n"
    "# fixes it; `python scripts/check_mypy_baseline.py --update` rewrites the entries.\n"
)

# Drops "path:LINE:COL: " or "path:LINE: " from the front of a diagnostic.
POSITION = re.compile(r"^([^:]+):[0-9]+(:[0-9]+)?: ")

Runner = Callable[[], "tuple[int, str]"]


def run_mypy() -> tuple[int, str]:
    """Run mypy on the integration; return its exit status and its output (stdout and stderr)."""
    done = subprocess.run(
        [sys.executable, "-m", "mypy", TARGET],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return done.returncode, done.stdout


def normalize(output: str) -> list[str]:
    """The error lines of mypy's output without line and column numbers, sorted."""
    errors = [POSITION.sub(r"\1: ", line) for line in output.splitlines() if ": error:" in line]
    return sorted(errors)


def parse_baseline(text: str) -> list[str]:
    """The entries of a baseline file: every line that is not blank and not a comment, sorted."""
    return sorted(line for line in text.splitlines() if line and not line.startswith("#"))


def baseline_header(text: str) -> str:
    """The leading comment and blank lines of a baseline file, kept when the entries are rewritten."""
    header = []
    for line in text.splitlines(keepends=True):
        if line.strip() and not line.startswith("#"):
            break
        header.append(line)
    return "".join(header)


def render_baseline(header: str, entries: Sequence[str]) -> str:
    """The text of a baseline file: its header, then one diagnostic per line."""
    return header + "".join(f"{entry}\n" for entry in entries)


def error(message: str) -> None:
    """Print an error to stderr, as a GitHub Actions annotation when it runs in Actions."""
    prefix = "::error::" if os.environ.get("GITHUB_ACTIONS") == "true" else "error: "
    print(f"{prefix}{message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None, runner: Runner = run_mypy, baseline_path: Path = BASELINE) -> int:
    """Compare mypy's diagnostics with the baseline (or rewrite it with --update); the exit status is 0 if they agree, 1 if not or if mypy did not run, 2 for a wrong usage. The mypy runner and the baseline path are parameters so that tests can replace them."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in ([], ["--update"]):
        print("usage: check_mypy_baseline.py [--update]", file=sys.stderr)
        return 2

    status, output = runner()
    print(output, end="" if output.endswith("\n") else "\n")
    current = normalize(output)
    # 0: clean; 1: mypy found errors. Anything else, or a failure with no diagnostic, is not a result.
    if status > 1 or (status != 0 and not current):
        error(f"mypy failed to run (exit status {status})")
        return 1

    existing = baseline_path.read_text(encoding="utf-8") if baseline_path.exists() else ""
    if args == ["--update"]:
        header = baseline_header(existing) or DEFAULT_HEADER
        baseline_path.write_text(render_baseline(header, current), encoding="utf-8")
        print(f"{baseline_path} now lists {len(current)} diagnostic(s).")
        return 0

    expected = parse_baseline(existing)
    if expected == current:
        print(f"mypy diagnostics match {baseline_path}")
        return 0
    diff = difflib.unified_diff(expected, current, "mypy-expected", "mypy-current", lineterm="")
    print("\n".join(diff))
    error(f"mypy diagnostics differ from {baseline_path} ('-' lines are listed but gone, '+' lines are new)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
