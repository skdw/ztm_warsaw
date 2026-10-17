"""Tests for scripts/release_check.py: manifest version, tag and CHANGELOG.md must agree."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_check.py"

CHANGELOG = """# Changelog

## [Unreleased]

### Fixed

- Pending fix.

## [1.2.0] - 2026-10-30

### Added

- Support for tokens from dane.um.warszawa.pl.

## [1.1.4] - 2026-05-19

### Fixed

- Options change no longer crashes.

[Unreleased]: https://example.invalid/compare/v1.2.0...HEAD
[1.1.4]: https://example.invalid/releases/tag/v1.1.4
"""


@pytest.fixture(scope="module")
def release_check() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_check", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_repo(root: Path, version: str, changelog: str | None = CHANGELOG) -> Path:
    manifest = root / "custom_components" / "ztm_warsaw" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"domain": "ztm_warsaw", "version": version}), encoding="utf-8")
    if changelog is not None:
        (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return root


def test_stable_version_takes_its_own_section(release_check: ModuleType, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "1.2.0")
    notes = release_check.check(repo, "v1.2.0")
    assert "Support for tokens" in notes
    assert "Pending fix" not in notes
    assert "Options change" not in notes


def test_last_section_drops_link_references(release_check: ModuleType, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "1.1.4")
    notes = release_check.check(repo, None)
    assert notes.endswith("Options change no longer crashes.")
    assert "example.invalid" not in notes


def test_beta_takes_the_unreleased_section(release_check: ModuleType, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "1.3.0b1")
    assert release_check.check(repo, "v1.3.0b1") == "### Fixed\n\n- Pending fix."


@pytest.mark.parametrize("tag", ["v1.1.1", "1.2.0", "v.1.2.0", "v1.2.0b1", "v1.2.0 ", ""])
def test_tag_must_be_v_plus_the_manifest_version(release_check: ModuleType, tmp_path: Path, tag: str) -> None:
    repo = make_repo(tmp_path, "1.2.0")
    with pytest.raises(release_check.ReleaseCheckError, match="pushed tag"):
        release_check.check(repo, tag)


def test_no_tag_means_a_pull_request_run(release_check: ModuleType, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "1.2.0")
    assert release_check.check(repo, None)


@pytest.mark.parametrize(
    "version", ["1.2", "v1.2.0", "1.2.0-beta", "1.2.0rc1", "", "1.2.0b", "1.2.0\n", "١.٢.٣", " 1.2.0", 12]
)
def test_manifest_version_must_be_x_y_z_or_beta(release_check: ModuleType, tmp_path: Path, version: str) -> None:
    repo = make_repo(tmp_path, version)
    with pytest.raises(release_check.ReleaseCheckError, match="X.Y.Z or X.Y.ZbN"):
        release_check.check(repo, None)


def test_missing_or_empty_section_fails(release_check: ModuleType, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "1.2.1")
    with pytest.raises(release_check.ReleaseCheckError, match="real content"):
        release_check.check(repo, None)
    empty = tmp_path / "empty"
    make_repo(empty, "1.2.1", "# Changelog\n\n## [1.2.1] - 2026-11-01\n\n## [1.2.0] - 2026-10-30\n\n- Something.\n")
    with pytest.raises(release_check.ReleaseCheckError, match="real content"):
        release_check.check(empty, None)


def test_missing_files_fail(release_check: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(release_check.ReleaseCheckError, match="manifest.json is missing"):
        release_check.check(tmp_path, None)
    repo = make_repo(tmp_path / "no_changelog", "1.2.0", changelog=None)
    with pytest.raises(release_check.ReleaseCheckError, match="CHANGELOG.md is missing"):
        release_check.check(repo, None)


def test_main_writes_notes_and_never_echoes_the_tag(
    release_check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = make_repo(tmp_path, "1.2.0")
    out = tmp_path / "notes.md"
    assert release_check.main({"RELEASE_TAG": "v1.2.0", "NOTES_OUT": str(out)}, repo) == 0
    assert out.read_text(encoding="utf-8").startswith("### Added")

    hostile = "v1.2.0\n::error::pwned"
    assert release_check.main({"RELEASE_TAG": hostile}, repo) == 1
    captured = capsys.readouterr()
    assert "pwned" not in captured.out + captured.err
    assert "::" not in captured.err.replace("release-check: ", "")


# --- sections that look present but are not release notes ---------------------------


@pytest.mark.parametrize(
    "section",
    [
        "### Added\n\n### Changed\n\n### Fixed\n",
        "<!-- TODO: write the notes -->\n",
        "<!--\nmulti-line\ncomment\n-->\n\n### Added\n",
        "\n\n   \n",
        "[1.2.0]: https://example.invalid/releases/tag/v1.2.0\n",
    ],
)
def test_a_skeleton_section_is_not_release_notes(release_check: ModuleType, tmp_path: Path, section: str) -> None:
    repo = make_repo(tmp_path, "1.2.0", f"# Changelog\n\n## [Unreleased]\n\n- x\n\n## [1.2.0] - 2026-10-30\n\n{section}")
    with pytest.raises(release_check.ReleaseCheckError, match="real content"):
        release_check.check(repo, None)


def test_a_section_with_one_real_line_is_enough(release_check: ModuleType, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "1.2.0", "# Changelog\n\n## [1.2.0] - 2026-10-30\n\n### Added\n\n- One real line.\n")
    assert release_check.check(repo, None).endswith("- One real line.")


def test_the_version_must_match_the_whole_heading_name(release_check: ModuleType, tmp_path: Path) -> None:
    changelog = "# Changelog\n\n## [1.1.40] - 2026-10-30\n\n- Not this release.\n\n## [1.1.4b1] - 2026-10-01\n\n- Nor this.\n"
    repo = make_repo(tmp_path, "1.1.4", changelog)
    with pytest.raises(release_check.ReleaseCheckError, match="real content"):
        release_check.check(repo, None)


def test_a_section_ends_at_any_level_two_heading(release_check: ModuleType, tmp_path: Path) -> None:
    changelog = "# Changelog\n\n## [1.2.0] - 2026-10-30\n\n- Real note.\n\n## Older releases\n\nSee GitHub Releases.\n"
    repo = make_repo(tmp_path, "1.2.0", changelog)
    notes = release_check.check(repo, None)
    assert "Real note" in notes
    assert "GitHub Releases" not in notes


def test_a_windows_changelog_works(release_check: ModuleType, tmp_path: Path) -> None:
    changelog = "# Changelog\r\n\r\n## [1.2.0] - 2026-10-30\r\n\r\n- Real note.\r\n"
    repo = make_repo(tmp_path, "1.2.0", changelog)
    assert release_check.check(repo, None) == "- Real note."


# --- main() ----------------------------------------------------------------------


def test_an_empty_release_tag_is_an_error_not_a_skipped_check(
    release_check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = make_repo(tmp_path, "1.2.0")
    assert release_check.main({}, repo) == 0
    assert release_check.main({"RELEASE_TAG": ""}, repo) == 1
    assert "pushed tag" in capsys.readouterr().err


def test_the_notes_file_ends_with_exactly_one_newline(release_check: ModuleType, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "1.2.0")
    out = tmp_path / "notes.md"
    assert release_check.main({"RELEASE_TAG": "v1.2.0", "NOTES_OUT": str(out)}, repo) == 0
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_an_unwritable_notes_file_fails_with_a_constant_message(
    release_check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = make_repo(tmp_path, "1.2.0")
    missing_directory = tmp_path / "nope" / "notes.md"
    assert release_check.main({"NOTES_OUT": str(missing_directory)}, repo) == 1
    assert "could not be written" in capsys.readouterr().err
