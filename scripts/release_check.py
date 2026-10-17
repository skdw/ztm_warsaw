"""Checks that the release bookkeeping agrees with itself, and writes the release notes.

Two callers:

* CI, on every pull request and push (no RELEASE_TAG): the version in
  custom_components/ztm_warsaw/manifest.json must have a CHANGELOG.md section with
  real content, so a release commit that forgets one of the two fails at review
  time instead of at tag time.
* a release workflow, on a version tag (RELEASE_TAG is the pushed tag): additionally
  the tag must be ``v`` + the manifest version, and the notes are written to
  NOTES_OUT for ``gh release create --notes-file``. A RELEASE_TAG that is set but
  empty is an error, not a request to skip the tag check.

A stable version (1.2.0) takes its notes from the ``## [1.2.0]`` section. A beta
(1.2.0b1) has no section of its own and takes them from ``## [Unreleased]``.

Messages are built from constants only. The tag arrives from the environment and
is never echoed, so nothing here can be turned into a workflow command.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

MANIFEST = Path("custom_components/ztm_warsaw/manifest.json")
CHANGELOG = Path("CHANGELOG.md")

STABLE_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
BETA_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+b[0-9]+")
# A link reference definition: up to three spaces, [label]:, a destination, an optional title.
LINK_REFERENCE = re.compile(r"""^ {0,3}\[[^\]]+\]:[ \t]*<?\S+>?(?:[ \t]+(?:"[^"]*"|'[^']*'|\([^)]*\)))?[ \t]*$""")
# A comment that is never closed hides the rest of the section, as Markdown renders it.
HTML_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
SECTION_END = re.compile(r"^ {0,3}#{1,2}(?:[ \t]|$)")


class ReleaseCheckError(Exception):
    """A check failed. The message is a constant and never contains input values."""


def has_content(section: str) -> bool:
    """True if the section holds at least one line that is not blank, a heading or a comment.

    A Keep a Changelog skeleton (headings only) or a TODO comment is not release notes.
    """
    text = HTML_COMMENT.sub("", section)
    return any(line.strip() and not line.lstrip().startswith("#") for line in text.split("\n"))


def extract_section(changelog: str, name: str) -> str:
    """Return the trimmed body of the ``## [name]`` section, or an empty string.

    The heading is ``## [name]`` (brackets may be backslash-escaped), followed by nothing,
    whitespace or a link; ``## [1.2.0]suffix`` is another heading. The section ends at
    the next level-1 or level-2 heading. Link reference definitions
    (``[1.2.0]: https://...``) are not notes and are dropped. A section with no
    real content (see ``has_content``) counts as empty.
    """
    lines = changelog.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    heading = re.compile(rf"^ {{0,3}}##[ \t]+\\?\[{re.escape(name)}\\?\](?:[ \t(\[].*)?$")
    start = next((i for i, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        return ""
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if SECTION_END.match(lines[i]):
            end = i
            break
    body = "\n".join(line for line in lines[start + 1 : end] if not LINK_REFERENCE.match(line)).strip()
    return body if has_content(body) else ""


def check(root: Path, tag: str | None) -> str:
    """Validate the bookkeeping under ``root`` and return the release notes."""
    try:
        version = json.loads((root / MANIFEST).read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise ReleaseCheckError("manifest.json is missing, not valid JSON, or has no version.") from err

    if not isinstance(version, str) or not (
        STABLE_VERSION.fullmatch(version) or BETA_VERSION.fullmatch(version)
    ):
        raise ReleaseCheckError("manifest.json version is not X.Y.Z or X.Y.ZbN.")

    if tag is not None and tag != f"v{version}":
        raise ReleaseCheckError(
            "The pushed tag is not v + the manifest.json version. Bump the version in the release commit and re-tag."
        )

    try:
        changelog = (root / CHANGELOG).read_text(encoding="utf-8")
    except OSError as err:
        raise ReleaseCheckError("CHANGELOG.md is missing.") from err

    section = "Unreleased" if BETA_VERSION.fullmatch(version) else version
    notes = extract_section(changelog, section)
    if not notes:
        raise ReleaseCheckError(
            "CHANGELOG.md has no section with real content for the manifest.json version "
            "(a beta uses [Unreleased]). Move the Unreleased notes under the version heading."
        )
    return notes


def main(env: Mapping[str, str] | None = None, root: Path | None = None) -> int:
    env = os.environ if env is None else env
    # Unset means a pull request run. Set but empty is passed on as-is and fails the
    # tag comparison, so an empty expression in a release workflow cannot skip the check.
    tag = env.get("RELEASE_TAG")
    try:
        notes = check(root or Path("."), tag)
    except ReleaseCheckError as err:
        print(f"release-check: {err}", file=sys.stderr)
        return 1
    notes_out = env.get("NOTES_OUT")
    if notes_out:
        try:
            Path(notes_out).write_text(f"{notes}\n", encoding="utf-8")
        except OSError:
            print("release-check: the release notes file could not be written.", file=sys.stderr)
            return 1
    print("release-check: manifest.json version, tag and CHANGELOG.md agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
