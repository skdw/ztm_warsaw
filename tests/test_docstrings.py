"""Every module, class and function of the project has a docstring (checked in every run), and the checker is tested."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_docstrings.py"
spec = importlib.util.spec_from_file_location("check_docstrings", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def project(tmp_path: Path, folder: str, name: str, source: str) -> Path:
    """A one-file project: ``source`` written to ``<folder>/<name>`` under ``tmp_path`` (the root the checker is given)."""
    target = tmp_path / folder
    target.mkdir(parents=True, exist_ok=True)
    (target / name).write_text(source, encoding="utf-8")
    return tmp_path


def test_the_project_has_a_docstring_everywhere():
    """The rule of AGENTS.md: whoever comes back to the code after months finds out what each piece is for."""
    assert checker.check() == []


def test_a_module_a_class_a_function_and_a_method_without_one_are_all_reported(tmp_path):
    root = project(
        tmp_path,
        "custom_components",
        "mod.py",
        "class A:\n    def method(self):\n        pass\n\ndef function():\n    pass\n",
    )
    assert checker.check(root) == [
        "custom_components/mod.py:1 module",
        "custom_components/mod.py:1 A",
        "custom_components/mod.py:2 method",
        "custom_components/mod.py:5 function",
    ]


def test_private_and_nested_functions_need_one_too(tmp_path):
    root = project(
        tmp_path,
        "scripts",
        "tool.py",
        '"""Tool."""\n\ndef _private():\n    """Private."""\n    def inner():\n        pass\n    return inner\n',
    )
    assert checker.check(root) == ["scripts/tool.py:5 inner"]


def test_a_documented_file_is_clean(tmp_path):
    root = project(
        tmp_path,
        "custom_components",
        "ok.py",
        '"""Module."""\n\nclass A:\n    """Class."""\n\n    def __init__(self):\n        """Init."""\n\ndef f():\n    """Function."""\n',
    )
    assert checker.check(root) == []


def test_test_functions_and_dunders_are_exempt_but_test_helpers_are_not(tmp_path):
    root = project(
        tmp_path,
        "tests",
        "test_x.py",
        '"""Module."""\n\ndef test_it_does_something():\n    pass\n\n'
        'class Stub:\n    """Stub."""\n\n    def __repr__(self):\n        return "stub"\n\n    def helper(self):\n        pass\n',
    )
    assert checker.check(root) == ["tests/test_x.py:12 helper"]


def test_test_functions_are_exempt_only_in_tests(tmp_path):
    root = project(tmp_path, "scripts", "x.py", '"""Module."""\n\ndef test_like_name():\n    pass\n')
    assert checker.check(root) == ["scripts/x.py:3 test_like_name"]


def test_an_empty_file_needs_no_docstring(tmp_path):
    root = project(tmp_path, "custom_components", "__init__.py", "")
    assert checker.check(root) == []


def test_a_file_that_is_not_python_is_reported_not_a_traceback(tmp_path):
    root = project(tmp_path, "scripts", "broken.py", "def (:\n")
    assert checker.check(root) == ["scripts/broken.py:1 file that cannot be read as Python"]


def test_async_functions_and_property_setters_need_one_too(tmp_path):
    root = project(
        tmp_path,
        "custom_components",
        "p.py",
        '"""Module."""\n\nasync def a():\n    pass\n\nclass C:\n    """C."""\n\n    @property\n    def x(self):\n        """X."""\n\n    @x.setter\n    def x(self, value):\n        pass\n',
    )
    assert checker.check(root) == ["custom_components/p.py:3 a", "custom_components/p.py:14 x"]


def test_an_overload_stub_needs_none(tmp_path):
    root = project(
        tmp_path,
        "scripts",
        "o.py",
        '"""Module."""\nfrom typing import overload\n\n@overload\ndef f(x: int) -> int: ...\n\ndef f(x):\n    """Real."""\n    return x\n',
    )
    assert checker.check(root) == []


def test_main_prints_what_is_missing_and_fails(capsys, monkeypatch):
    monkeypatch.setattr(checker, "check", lambda: ["scripts/bad.py:1 module", "scripts/bad.py:1 f"])
    assert checker.main() == 1
    out = capsys.readouterr().out
    assert "missing docstring: scripts/bad.py:1 module" in out
    assert "2 missing" in out


def test_main_succeeds_when_nothing_is_missing(capsys, monkeypatch):
    monkeypatch.setattr(checker, "check", lambda: [])
    assert checker.main() == 0
    assert "every module, class and function has a docstring" in capsys.readouterr().out
