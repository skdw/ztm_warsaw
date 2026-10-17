"""Verifies a pull request's "Documentation impact" declaration against its own diff.

Python port of the playbook's scripts/check-pr-docs-impact.mjs (docs/ci-cookbook.md
#12b), with the same rules: select exactly one option, "No doc update needed" needs
a real reason (the template placeholder does not count), "Docs updated" needs a
changed doc path, and "No doc update needed" must not coexist with one. Runs only
on pull_request events; on anything else it exits cleanly.

One deliberate difference from the original, which searches the whole description:
only the ``## Documentation impact`` section counts, and only the text a reader can see.
A ticked item quoted in another section, or sitting in a code block or an HTML comment
(closed or not), is not a declaration.

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

# Markdown allows a heading or a fence to be indented by up to three spaces.
FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
SECTION_HEADING = re.compile(r"^ {0,3}## Documentation impact[ \t]*$", re.MULTILINE | re.IGNORECASE)
ATX_H1_H2 = re.compile(r"^ {0,3}#{1,2}(?:[ \t]|$)")
SETEXT_UNDERLINE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
# A line that starts some other block (code, list, quote, heading, HTML, fence); any
# other non-blank line is paragraph text, which a setext underline turns into a heading.
OTHER_BLOCK = re.compile(r"^(?: {4}|\t| {0,3}(?:[-*+>#<]|\d{1,9}[.)]|`{3}|~{3}))")
HTML_COMMENT_BLOCK = re.compile(r"^ {0,3}<!--")

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


def visible_text(body: str) -> str:
    """Return the description as GitHub shows it: without code blocks and HTML comments.

    Scans line by line, so whichever of a fence and a comment starts first wins, as in
    Markdown. A fenced code block (indented by up to three spaces) ends at a matching
    closing fence; one that is never closed runs to the end of the description. An HTML
    comment ends at ``-->``; one that is never closed hides the rest of the description,
    which is how GitHub renders it. A comment that opens a line is an HTML block, so the
    text after its ``-->`` on that same line is hidden too. Windows line endings are
    normalised.
    """
    visible: list[str] = []
    fence: str | None = None
    in_comment = False
    comment_block = False
    for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if fence is not None:
            closing = FENCE_CLOSE.match(line)
            if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= len(fence):
                fence = None
            continue
        if in_comment:
            end = line.find("-->")
            if end == -1:
                continue
            in_comment = False
            if comment_block:
                continue
            line = line[end + 3 :]
        else:
            opening = FENCE_OPEN.match(line)
            # The info string of a backtick fence cannot contain a backtick (that is inline code).
            if opening and not (opening.group(1)[0] == "`" and "`" in opening.group(2)):
                fence = opening.group(1)
                continue
            if HTML_COMMENT_BLOCK.match(line):
                # A comment that opens a line is an HTML block: it runs to the line that
                # contains the closing arrow, and that whole line belongs to the block.
                in_comment = comment_block = "-->" not in line[line.index("<!--") + 2 :]
                continue
        kept: list[str] = []
        rest = line
        while True:
            start = rest.find("<!--")
            if start == -1:
                kept.append(rest)
                break
            kept.append(rest[:start])
            end = rest.find("-->", start + 4)
            if end == -1:
                in_comment = True
                comment_block = False
                break
            rest = rest[end + 3 :]
        visible.append("".join(kept))
    return "\n".join(visible)


def declaration_section(body: str) -> str | None:
    """Return the text of the ``## Documentation impact`` section, or None if there is none.

    The section runs to the next level-1 or level-2 heading (or the end) of the text a
    reader sees (see ``visible_text``). A setext heading (text over ``---`` or ``===``) ends it as well.
    """
    text = visible_text(body)
    heading = SECTION_HEADING.search(text)
    if heading is None:
        return None
    lines = text[heading.end() :].split("\n")
    for i, line in enumerate(lines):
        if ATX_H1_H2.match(line):
            return "\n".join(lines[:i])
        # Paragraph text over "---" or "===" is a heading too: the text line starts it.
        if i and SETEXT_UNDERLINE.match(line) and lines[i - 1].strip() and not OTHER_BLOCK.match(lines[i - 1]):
            return "\n".join(lines[: i - 1])
    return "\n".join(lines)


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
