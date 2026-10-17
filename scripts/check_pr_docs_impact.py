"""Verifies a pull request's "Documentation impact" declaration against its own diff.

Python port of the playbook's scripts/check-pr-docs-impact.mjs (docs/ci-cookbook.md
#12b), with the same rules: select exactly one option, "No doc update needed" needs
a real reason (the template placeholder does not count), "Docs updated" needs a
changed doc path, and "No doc update needed" must not coexist with one. Runs only
on pull_request events; on anything else it exits cleanly.

One deliberate difference from the original, which searches the whole description:
only the ``## Documentation impact`` section counts. A ticked item quoted in another
section, or sitting in a code block or an HTML comment, is not a declaration.

Every message printed here is a constant: the pull request body, branch names and
file names never reach the log or a workflow command.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

# Quoted or hidden text never counts: fenced code blocks (an unterminated fence runs to
# the end, as GitHub renders it) and HTML comments are removed before looking for the section.
FENCE = re.compile(r"^(```|~~~)[^\n]*\n.*?(?:^\1[^\n]*$|\Z)", re.MULTILINE | re.DOTALL)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
SECTION_HEADING = re.compile(r"^## Documentation impact[ \t]*$", re.MULTILINE | re.IGNORECASE)
NEXT_HEADING = re.compile(r"^#{1,2} ", re.MULTILINE)

DOCS_UPDATED = re.compile(r"^- \[[xX]\] Docs updated\s*$", re.MULTILINE)
NO_DOC_UPDATE_TICKED = re.compile(r"^- \[[xX]\] No doc update needed:", re.MULTILINE)
NO_DOC_UPDATE = re.compile(r"^- \[[xX]\] No doc update needed: (?!<state the reason>\s*$)\S.+$", re.MULTILINE)

MSG_NO_SECTION = "The pull request description has no '## Documentation impact' section; keep the section from the pull request template."
MSG_NONE = "Select one Documentation impact option: tick 'Docs updated', or tick 'No doc update needed:' and give the reason."
MSG_BOTH = "Both Documentation impact options are ticked; select exactly one."
MSG_NEEDS_REASON = "'No doc update needed' is ticked without a real reason after the colon (the template placeholder does not count)."
MSG_DOCS_NOT_CHANGED = "'Docs updated' is selected but no documentation file changed in this pull request."
MSG_DOCS_CHANGED = "A documentation file changed in this pull request; select 'Docs updated' instead."
MSG_GIT_FAILED = "git could not list the files changed between the base and head commits (see the git error above)."
MSG_EDIT_HINT = "Edit the pull request description to fix this: re-running the job reuses the old description."

# The absolute path is deliberate: resolving an executable through PATH is what
# static analysis flags, and the hosted runner image installs git here.
GIT = "/usr/bin/git"


def is_doc_path(path: str) -> bool:
    """Documentation is a Markdown file in the repository root, or anything under docs/.

    A change to code, tests, CI, templates or translations alone is the case for
    "No doc update needed".
    """
    return path.startswith("docs/") or ("/" not in path and path.endswith(".md"))


def declaration_section(body: str) -> str | None:
    """Return the text of the ``## Documentation impact`` section, or None if there is none.

    The section runs to the next level-1 or level-2 heading (or the end). Code blocks and
    HTML comments are removed first, and Windows line endings are normalised.
    """
    text = HTML_COMMENT.sub("", FENCE.sub("", body.replace("\r\n", "\n")))
    heading = SECTION_HEADING.search(text)
    if heading is None:
        return None
    rest = text[heading.end() :]
    following = NEXT_HEADING.search(rest)
    return rest[: following.start()] if following else rest


def read_declaration(body: str) -> tuple[bool, bool]:
    """Return (docs_updated, no_doc_update) as declared in the Documentation impact section."""
    section = declaration_section(body)
    if section is None:
        return False, False
    return bool(DOCS_UPDATED.search(section)), bool(NO_DOC_UPDATE.search(section))


def evaluate(body: str, changed_files: Sequence[str]) -> list[str]:
    """Return the problems found; an empty list means the declaration is consistent."""
    section = declaration_section(body)
    if section is None:
        return [MSG_NO_SECTION]
    docs_updated, no_doc_update = read_declaration(body)
    if docs_updated and no_doc_update:
        return [MSG_BOTH]
    if not docs_updated and not no_doc_update:
        return [MSG_NEEDS_REASON if NO_DOC_UPDATE_TICKED.search(section) else MSG_NONE]
    docs_changed = any(is_doc_path(path) for path in changed_files)
    if docs_updated and not docs_changed:
        return [MSG_DOCS_NOT_CHANGED]
    if no_doc_update and docs_changed:
        return [MSG_DOCS_CHANGED]
    return []


def git_changed_files(base_sha: str, head_sha: str) -> list[str]:
    """Paths changed on the pull request side, from the merge base of the two commits.

    ``--no-renames`` lists both ends of a move (a doc moved out of docs/ must still
    show its old path), and ``-z`` keeps non-ASCII paths unquoted. git's own stderr
    is left alone so a failure explains itself in the log.
    """
    out = subprocess.run(
        [GIT, "diff", "--name-only", "--no-renames", "-z", f"{base_sha}...{head_sha}"],
        check=True,
        stdout=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    ).stdout
    return [path for path in out.split("\0") if path]


def main(
    event_path: str | None = None,
    changed_files: Callable[[str, str], list[str]] = git_changed_files,
) -> int:
    event_path = event_path if event_path is not None else os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return 0
    event: dict[str, Any] = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pull_request = event.get("pull_request")
    if not pull_request:
        return 0

    # Automated dependency PRs cannot fill in a hand-written template body. Match
    # the author, never the branch name: anyone can open a PR from a branch
    # called dependabot/...
    if (pull_request.get("user") or {}).get("login") == "dependabot[bot]":
        return 0

    body = pull_request.get("body") or ""
    docs_updated, no_doc_update = read_declaration(body)
    # The diff is only needed when the declaration itself is well formed.
    files: list[str] = []
    if docs_updated != no_doc_update:
        try:
            files = changed_files(pull_request["base"]["sha"], pull_request["head"]["sha"])
        except subprocess.CalledProcessError:
            print(f"::error::{MSG_GIT_FAILED}")
            return 1
    problems = evaluate(body, files)
    if problems:
        for problem in problems:
            print(f"::error::{problem}")
        print(MSG_EDIT_HINT)
        return 1
    print("Documentation impact declaration is consistent with the diff.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
