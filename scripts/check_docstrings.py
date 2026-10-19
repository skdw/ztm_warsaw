#!/usr/bin/env python3
"""Check that every module, class and function of the project has a docstring (also in every pytest run).

The project is picked up again after months, by its one maintainer or by someone new, and the code is the only
thing that remembers *why* it is as it is: so a docstring says what a piece is for and what it promises, not what
its name already says. This checks that one is there; whether it is any good is for the review.

Required: every module, class, function and method of ``custom_components/``, ``scripts/`` and ``tests/``, the
private ones too (``_name``), nested functions too. Not required: ``test_*`` functions of ``tests/`` (their names
are sentences about the behaviour), the dunder methods other than ``__init__`` (``__repr__`` and the like), the
``__init__.py`` files that are empty, and ``@overload`` stubs. Messages are a constant text plus ``file:line name``;
no source text is printed.

Usage: python3 scripts/check_docstrings.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNED = ("custom_components", "scripts", "tests")  # relative to the root
TEST_FUNCTION_PREFIX = "test_"


def _is_overload(node: ast.AST) -> bool:
    """Whether a function is a ``@typing.overload`` stub, which has no body to describe."""
    decorators = getattr(node, "decorator_list", [])
    return any(
        (isinstance(d, ast.Name) and d.id == "overload") or (isinstance(d, ast.Attribute) and d.attr == "overload")
        for d in decorators
    )


def _needs_docstring(node: ast.AST, in_tests: bool) -> bool:
    """Whether the rule asks for a docstring on this function or class (see the module text for the exceptions)."""
    name = node.name  # type: ignore[attr-defined]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if in_tests and name.startswith(TEST_FUNCTION_PREFIX):
            return False
        if name.startswith("__") and name.endswith("__") and name != "__init__":
            return False
        if _is_overload(node):
            return False
    return True


def check_file(path: Path, root: Path = ROOT) -> list[str]:
    """The missing docstrings of one file as ``file:line name`` texts; an empty list means it is fine."""
    relative = path.relative_to(root)
    in_tests = relative.parts[0] == "tests"
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(relative))
    except (SyntaxError, UnicodeDecodeError):  # fails closed, with the file named, instead of a traceback
        return [f"{relative}:1 file that cannot be read as Python"]
    found: list[tuple[int, str]] = []
    if source.strip() and not ast.get_docstring(tree):
        found.append((1, "module"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if _needs_docstring(node, in_tests) and not ast.get_docstring(node):
                found.append((node.lineno, node.name))
    return [f"{relative}:{line} {name}" for line, name in sorted(found, key=lambda item: item[0])]


def check(root: Path = ROOT) -> list[str]:
    """The missing docstrings of the whole project, in file order."""
    problems: list[str] = []
    for folder in SCANNED:
        for path in sorted((root / folder).rglob("*.py")):
            problems.extend(check_file(path, root))
    return problems


def main() -> int:
    """Print what is missing and exit 1, or exit 0 when everything has a docstring."""
    problems = check()
    for problem in problems:
        print(f"missing docstring: {problem}")
    if problems:
        print(f"{len(problems)} missing: add a docstring that says what it is for and what it promises.")
        return 1
    print("every module, class and function has a docstring")
    return 0


if __name__ == "__main__":
    sys.exit(main())
