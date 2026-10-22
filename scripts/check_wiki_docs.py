#!/usr/bin/env python3
"""Check the wiki source in docs/wiki/ before it is published (and in every pytest run).

The GitHub Wiki is a build output: its pages live in docs/wiki/ and .github/workflows/publish-wiki.yml copies
them to the wiki. This catches the drift that a copy cannot: a page that is gone, a link that goes nowhere, a
real e-mail address in an example, a folder or a link that rsync would copy into the wiki.
Anchors (``Page#section``) are not checked, only the page. Inline links and reference-style definitions
are both read; HTML ``<a>`` and ``<img>`` are not used in the wiki. Every message is a constant text plus a file name; no page content is printed.

Usage: python3 scripts/check_wiki_docs.py [wiki-source-dir]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "docs" / "wiki"

# The pages the wiki must have (names as the wiki shows them, without .md).
EXPECTED = (
    "Home",
    "0.-Installation",
    "1.-Configuration",
    "2.-Concepts",
    "3.-Examples",
    "4.-Troubleshooting",
    "5.-Roadmap",
    "6.-Contributing",
)

# Reference-style links: the target is on a definition line, "[name]: target" (also "[name]: <target> "title"").
DEFINITION = re.compile(r"^ {0,3}\[[^\]]+\]:\s*<?([^\s>]+)>?", re.MULTILINE)
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")  # [text](target), [text](<target>), [text](target "title")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def check(wiki_dir: Path) -> list[str]:
    """The problems found, as short texts; an empty list means the source is fine."""
    problems: list[str] = []
    pages = {p.stem: p for p in wiki_dir.glob("*.md") if p.is_file() and not p.is_symlink()}
    for name in EXPECTED:
        if name not in pages:
            problems.append(f"missing page: {name}.md")
    for entry in sorted(wiki_dir.iterdir(), key=lambda e: e.name):
        if entry.is_symlink() or entry.is_dir():
            problems.append(f"not a plain file (no folders or links in the wiki source): {entry.name}")
        elif entry.suffix != ".md":
            problems.append(f"not a page (the wiki takes Markdown only): {entry.name}")
    for name, path in sorted(pages.items()):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append(f"{name}.md is not UTF-8 text")
            continue
        if not text.startswith("# "):
            problems.append(f"{name}.md does not start with a '# Title' line")
        if EMAIL.search(text):
            problems.append(f"{name}.md contains something that looks like an e-mail address")
        for target in [*LINK.findall(text), *DEFINITION.findall(text)]:
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            page = target.split("#", 1)[0]
            if page not in pages:
                problems.append(f"{name}.md links to a page that does not exist: {page}")
    return problems


def main(argv: list[str]) -> int:
    """Check the wiki source directory given as argv[1] (default docs/wiki), print every problem to stderr, and return 1 if there is one."""
    wiki_dir = Path(argv[1]).resolve() if len(argv) > 1 else DEFAULT_DIR
    if not wiki_dir.is_dir():
        print(f"Not a directory: {wiki_dir}", file=sys.stderr)
        return 1
    problems = check(wiki_dir)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print(f"Wiki source is fine ({len(list(wiki_dir.glob('*.md')))} pages).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
