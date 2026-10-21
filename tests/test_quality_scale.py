"""quality_scale.yaml says, rule by rule, where the integration stands: every rule of Home Assistant's list is in it, once, with a valid status."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

FILE = Path(__file__).resolve().parent.parent / "custom_components" / "ztm_warsaw" / "quality_scale.yaml"

# The 54 rules of the Integration Quality Scale (https://contributors.home-assistant.io/core/quality-scale/rules/).
RULES = {
    "bronze": [
        "action-setup", "appropriate-polling", "brands", "common-modules", "config-flow", "config-flow-test-coverage",
        "dependency-transparency", "docs-actions", "docs-conditions", "docs-high-level-description",
        "docs-installation-instructions", "docs-removal-instructions", "docs-triggers", "entity-event-setup",
        "entity-unique-id", "has-entity-name", "runtime-data", "test-before-configure", "test-before-setup",
        "unique-config-entry",
    ],
    "silver": [
        "action-exceptions", "config-entry-unloading", "docs-configuration-parameters", "docs-installation-parameters",
        "entity-unavailable", "integration-owner", "log-when-unavailable", "parallel-updates", "reauthentication-flow",
        "test-coverage",
    ],
    "gold": [
        "devices", "diagnostics", "discovery", "discovery-update-info", "docs-data-update", "docs-examples",
        "docs-known-limitations", "docs-supported-devices", "docs-supported-functions", "docs-troubleshooting",
        "docs-use-cases", "dynamic-devices", "entity-category", "entity-device-class", "entity-disabled-by-default",
        "entity-translations", "exception-translations", "icon-translations", "reconfiguration-flow", "repair-issues",
        "stale-devices",
    ],
    "platinum": ["async-dependency", "inject-websession", "strict-typing"],
}


class _UniqueKeys(yaml.SafeLoader):
    """A YAML loader that refuses a mapping with the same key twice (PyYAML keeps the last one without a word)."""

    def construct_mapping(self, node, deep=False):
        """Build the mapping, after checking that no key repeats."""
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        repeated = {key for key in keys if keys.count(key) > 1}
        if repeated:
            raise ValueError(f"repeated YAML keys: {sorted(repeated)}")
        return super().construct_mapping(node, deep=deep)


def _load(text: str) -> dict:
    """Parse YAML text, refusing repeated keys."""
    return yaml.load(text, Loader=_UniqueKeys)  # noqa: S506 - the loader is a SafeLoader


def _rules() -> dict:
    """The rules of the file."""
    return _load(FILE.read_text())["rules"]


def test_a_rule_written_twice_is_refused_instead_of_silently_keeping_the_last():
    text = "rules:\n  config-flow:\n    status: done\n  config-flow:\n    status: todo\n"
    with pytest.raises(ValueError):
        _load(text)


def test_every_rule_of_the_scale_is_in_the_file_and_nothing_else():
    wanted = {rule for rules in RULES.values() for rule in rules}
    assert len(wanted) == 54
    assert set(_rules()) == wanted


def test_every_status_is_valid_and_every_exemption_or_todo_says_why():
    for rule, entry in _rules().items():
        status = entry if isinstance(entry, str) else entry["status"]
        assert status in {"done", "exempt", "todo"}, rule
        if status in {"exempt", "todo"}:
            assert isinstance(entry, dict), f"{rule} is {status}: say why"
            assert entry.get("comment"), f"{rule} is {status}: say why"
