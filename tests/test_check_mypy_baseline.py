"""Tests for scripts/check_mypy_baseline.py: mypy's diagnostics must match .github/mypy-baseline.txt exactly."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_mypy_baseline.py"
CI = ROOT / ".github" / "workflows" / "ci.yml"

CLIENT = 'custom_components/ztm_warsaw/client.py: error: Unsupported operand types for < ("float" and "None")  [operator]'
CONFIG = 'custom_components/ztm_warsaw/config_flow.py: error: Unused "type: ignore" comment  [unused-ignore]'
NEW = "custom_components/ztm_warsaw/sensor.py: error: Incompatible return value type  [return-value]"

OUTPUT = """\
custom_components/ztm_warsaw/config_flow.py:153: error: Unused "type: ignore" comment  [unused-ignore]
custom_components/ztm_warsaw/client.py:200:17: error: Unsupported operand types for < ("float" and "None")  [operator]
custom_components/ztm_warsaw/client.py:200:17: note: Right operand is of type "float | None"
custom_components/ztm_warsaw/sensor.py:488: note: By default the bodies of untyped functions are not checked  [annotation-unchecked]
Found 2 errors in 2 files (checked 8 source files)
"""

HEADER = "# Known mypy diagnostics.\n# A second line.\n"


@pytest.fixture(scope="module")
def baseline() -> ModuleType:
    """The script scripts/check_mypy_baseline.py loaded as a module (it is not a package)."""
    spec = importlib.util.spec_from_file_location("check_mypy_baseline", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_baseline(path: Path, entries: list[str], header: str = HEADER) -> Path:
    """Write a baseline file with a header and the given entries, and return its path."""
    path.write_text(header + "".join(f"{e}\n" for e in entries), encoding="utf-8")
    return path


def main(baseline: ModuleType, path: Path, status: int, output: str, *args: str) -> int:
    """Run the script's `main` with a fake mypy that returns the given status and output, against the baseline at `path`."""
    return baseline.main(list(args), runner=lambda: (status, output), baseline_path=path)


# --- reading mypy's output ---------------------------------------------------------------


def test_normalize_drops_positions_notes_and_the_summary_and_sorts(baseline: ModuleType) -> None:
    assert baseline.normalize(OUTPUT) == [CLIENT, CONFIG]


def test_normalize_accepts_both_forms_of_position(baseline: ModuleType) -> None:
    out = "a/b.py:3: error: one  [x]\na/b.py:3:9: error: two  [y]\n"
    assert baseline.normalize(out) == ["a/b.py: error: one  [x]", "a/b.py: error: two  [y]"]


def test_normalize_keeps_a_diagnostic_that_occurs_twice(baseline: ModuleType) -> None:
    out = "a.py:1: error: same  [x]\na.py:9: error: same  [x]\n"
    assert baseline.normalize(out) == ["a.py: error: same  [x]", "a.py: error: same  [x]"]


def test_normalize_of_a_clean_run_is_empty(baseline: ModuleType) -> None:
    assert baseline.normalize("Success: no issues found in 8 source files\n") == []


def test_parse_baseline_skips_comments_and_blank_lines_and_sorts(baseline: ModuleType) -> None:
    assert baseline.parse_baseline(f"# c\n\n{CONFIG}\n# d\n{CLIENT}\n") == [CLIENT, CONFIG]


def test_baseline_header_is_the_leading_comment_block(baseline: ModuleType) -> None:
    assert baseline.baseline_header(f"{HEADER}\n{CLIENT}\n# not part of it\n") == f"{HEADER}\n"
    assert baseline.baseline_header(f"{CLIENT}\n") == ""
    assert baseline.baseline_header("") == ""


# --- the check ---------------------------------------------------------------------------


def test_matching_diagnostics_pass_whatever_the_line_numbers(baseline: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_baseline(tmp_path / "b.txt", [CLIENT, CONFIG])
    assert main(baseline, path, 1, OUTPUT) == 0
    assert "match" in capsys.readouterr().out


def test_a_new_diagnostic_fails_and_is_shown_with_a_plus(baseline: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_baseline(tmp_path / "b.txt", [CLIENT, CONFIG])
    output = OUTPUT + "custom_components/ztm_warsaw/sensor.py:9: error: Incompatible return value type  [return-value]\n"
    assert main(baseline, path, 1, output) == 1
    assert f"+{NEW}" in capsys.readouterr().out


def test_a_diagnostic_mypy_no_longer_reports_fails_and_is_shown_with_a_minus(baseline: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_baseline(tmp_path / "b.txt", [CLIENT, CONFIG, NEW])
    assert main(baseline, path, 1, OUTPUT) == 1
    assert f"-{NEW}" in capsys.readouterr().out


def test_fixing_one_error_and_adding_another_is_not_a_match(baseline: ModuleType, tmp_path: Path) -> None:
    """A count would let this through: the same number of errors, but not the same errors."""
    path = write_baseline(tmp_path / "b.txt", [CLIENT, CONFIG])
    swapped = "custom_components/ztm_warsaw/client.py:200: error: Unsupported operand types for < (\"float\" and \"None\")  [operator]\n" + \
        "custom_components/ztm_warsaw/sensor.py:9: error: Incompatible return value type  [return-value]\n"
    assert main(baseline, path, 1, swapped) == 1


def test_an_error_that_now_occurs_twice_is_not_a_match(baseline: ModuleType, tmp_path: Path) -> None:
    path = write_baseline(tmp_path / "b.txt", [CLIENT, CONFIG])
    doubled = OUTPUT + 'custom_components/ztm_warsaw/client.py:300: error: Unsupported operand types for < ("float" and "None")  [operator]\n'
    assert main(baseline, path, 1, doubled) == 1


def test_a_clean_run_against_an_empty_baseline_passes(baseline: ModuleType, tmp_path: Path) -> None:
    path = write_baseline(tmp_path / "b.txt", [])
    assert main(baseline, path, 0, "Success: no issues found in 8 source files\n") == 0


def test_a_clean_run_against_a_baseline_with_entries_fails(baseline: ModuleType, tmp_path: Path) -> None:
    path = write_baseline(tmp_path / "b.txt", [CLIENT])
    assert main(baseline, path, 0, "Success: no issues found in 8 source files\n") == 1


def test_a_missing_baseline_counts_as_empty(baseline: ModuleType, tmp_path: Path) -> None:
    assert main(baseline, tmp_path / "nope.txt", 0, "Success: no issues found\n") == 0
    assert main(baseline, tmp_path / "nope.txt", 1, OUTPUT) == 1


@pytest.mark.parametrize(
    ("status", "output"),
    [
        (2, "usage: mypy [-h] ...\n"),
        (2, OUTPUT),  # a crash after printing some diagnostics is still not a result
        (3, ""),
        (1, "/usr/bin/python: No module named mypy\n"),  # exit status 1, but not a diagnostic
    ],
)
def test_mypy_that_cannot_run_fails_even_against_a_matching_baseline(baseline: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], status: int, output: str) -> None:
    path = write_baseline(tmp_path / "b.txt", [CLIENT, CONFIG])
    assert main(baseline, path, status, output) == 1
    assert "failed to run" in capsys.readouterr().err


def test_the_error_is_a_workflow_command_only_in_github_actions(baseline: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    path = write_baseline(tmp_path / "b.txt", [CLIENT])
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    main(baseline, path, 1, OUTPUT)
    assert not capsys.readouterr().err.startswith("::error::")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    main(baseline, path, 1, OUTPUT)
    assert capsys.readouterr().err.startswith("::error::")


def test_unknown_arguments_are_refused(baseline: ModuleType, tmp_path: Path) -> None:
    path = write_baseline(tmp_path / "b.txt", [CLIENT])
    assert main(baseline, path, 1, OUTPUT, "--fix") == 2
    assert main(baseline, path, 1, OUTPUT, "--update", "extra") == 2


# --- --update ----------------------------------------------------------------------------


def test_update_rewrites_the_entries_and_keeps_the_header(baseline: ModuleType, tmp_path: Path) -> None:
    path = write_baseline(tmp_path / "b.txt", [NEW])
    assert main(baseline, path, 1, OUTPUT, "--update") == 0
    assert path.read_text(encoding="utf-8") == f"{HEADER}{CLIENT}\n{CONFIG}\n"
    assert main(baseline, path, 1, OUTPUT) == 0  # and the check agrees with what was written


def test_update_creates_a_missing_baseline_with_the_default_header(baseline: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "new.txt"
    assert main(baseline, path, 1, OUTPUT, "--update") == 0
    text = path.read_text(encoding="utf-8")
    assert text.startswith(baseline.DEFAULT_HEADER)
    assert baseline.parse_baseline(text) == [CLIENT, CONFIG]


def test_update_does_not_write_when_mypy_cannot_run(baseline: ModuleType, tmp_path: Path) -> None:
    path = write_baseline(tmp_path / "b.txt", [CLIENT, CONFIG])
    before = path.read_text(encoding="utf-8")
    assert main(baseline, path, 2, "usage: mypy\n", "--update") == 1
    assert path.read_text(encoding="utf-8") == before


# --- the repository's own files -----------------------------------------------------------


def test_the_ci_mypy_step_runs_this_script_and_nothing_else_inline() -> None:
    text = CI.read_text(encoding="utf-8")
    step = re.search(r"- name: mypy\n\s+run: (.+)\n", text)
    assert step is not None, "the mypy step must be a single command"
    assert step.group(1).strip() == "python scripts/check_mypy_baseline.py"


def test_the_real_baseline_file_is_a_sorted_list_of_positionless_errors(baseline: ModuleType) -> None:
    text = (ROOT / ".github" / "mypy-baseline.txt").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    assert lines == sorted(lines), "--update writes the entries sorted"
    assert baseline.parse_baseline(text) == lines
    assert all(": error:" in e and not re.match(r"^[^:]+:[0-9]+", e) for e in lines)
