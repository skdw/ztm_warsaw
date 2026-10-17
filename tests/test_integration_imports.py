"""The integration must import with only what Home Assistant itself provides.

`async_timeout` is a third-party package that Home Assistant 2026.10 no longer installs; the
integration imported it, so on a clean installation it failed to load. The CI test environment
cannot show that: `hass-nabucasa` still pulls `async-timeout` into it, and Home Assistant's own
modules import it there. These tests therefore refuse the import only when it comes from a
module of the integration, in a fresh interpreter.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.ztm_warsaw"
MANIFEST = ROOT / "custom_components" / "ztm_warsaw" / "manifest.json"

# Modules the integration must not need: Home Assistant no longer provides them.
NOT_PROVIDED = ("async_timeout",)

# `__import__` is what every `import x` / `from x import y` statement calls, and it is given the
# importing module's globals, so this catches the import whether or not the module is already
# cached in sys.modules (Home Assistant's own modules may have loaded it).
GUARD = f"""\
import builtins, importlib, pkgutil, sys

NOT_PROVIDED = {NOT_PROVIDED!r}
PACKAGE = {PACKAGE!r}
real_import = builtins.__import__


def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    importer = (globals or {{}}).get("__name__", "")
    if level == 0 and name.split(".")[0] in NOT_PROVIDED and importer.startswith(PACKAGE):
        raise ImportError(f"{{importer}} imports {{name}}, which Home Assistant does not provide")
    return real_import(name, globals, locals, fromlist, level)


builtins.__import__ = guarded
"""


def run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", GUARD + code], cwd=ROOT, capture_output=True, text=True, check=False)


def test_every_module_of_the_integration_imports_without_the_modules_home_assistant_dropped() -> None:
    done = run(
        "package = importlib.import_module(PACKAGE)\n"
        "for module in pkgutil.iter_modules(package.__path__):\n"
        "    importlib.import_module(PACKAGE + '.' + module.name)\n"
    )
    assert done.returncode == 0, done.stderr[-2000:]


def test_the_guard_refuses_the_import_from_a_module_of_the_integration() -> None:
    """Guard for the guard: without it the test above would pass for any environment."""
    done = run("exec('import async_timeout', {'__name__': PACKAGE + '.some_module'})\n")
    assert done.returncode != 0
    assert "which Home Assistant does not provide" in done.stderr


def test_the_guard_refuses_the_from_form_too() -> None:
    done = run("exec('from async_timeout import timeout', {'__name__': PACKAGE + '.client'})\n")
    assert done.returncode != 0
    assert "which Home Assistant does not provide" in done.stderr


def test_the_manifest_declares_no_runtime_requirements() -> None:
    """Home Assistant provides aiohttp (hassfest rejects it as a requirement); anything else must be discussed first."""
    assert json.loads(MANIFEST.read_text(encoding="utf-8"))["requirements"] == []
