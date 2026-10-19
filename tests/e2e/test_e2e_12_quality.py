"""E2E-37: the integration follows the quality-scale rules it can: stale devices are deletable, a device in use is not, no update limit."""

from __future__ import annotations

import importlib

import pytest
from homeassistant.helpers import device_registry as dr

from custom_components.ztm_warsaw import async_remove_config_entry_device
from custom_components.ztm_warsaw.const import DOMAIN

pytestmark = pytest.mark.e2e

LINE = "525"


def _device(env, entry, identifier):
    """A device of the integration for this entry, created the way a stop's entities create it."""
    return env.device_registry.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, identifier)})


async def test_e2e_37_the_device_of_a_stop_in_use_cannot_be_deleted(env):
    entry = await env.add_entry_via_flow(line=LINE)
    device = next(d for d in dr.async_entries_for_config_entry(env.device_registry, entry.entry_id) if (DOMAIN, f"line_{LINE}_7009_01") in d.identifiers)
    assert await async_remove_config_entry_device(env.hass, entry, device) is False


async def test_e2e_37_the_device_of_a_stop_the_line_no_longer_has_can_be_deleted(env):
    entry = await env.add_entry_via_flow(line=LINE)
    stray = _device(env, entry, f"line_{LINE}_9999_99")
    assert await async_remove_config_entry_device(env.hass, entry, stray) is True


async def test_e2e_37_the_device_of_a_1_1_x_entry_is_in_use_but_another_line_is_not(env):
    entry = await env.add_entry(line="151")  # one stop, the shape of 1.1.x: the line is the device
    live = next(d for d in dr.async_entries_for_config_entry(env.device_registry, entry.entry_id) if (DOMAIN, "line_151") in d.identifiers)
    assert await async_remove_config_entry_device(env.hass, entry, live) is False
    stray = _device(env, entry, "line_999")
    assert await async_remove_config_entry_device(env.hass, entry, stray) is True


@pytest.mark.parametrize("platform", ["sensor", "calendar"])
def test_e2e_37_the_platforms_do_not_limit_parallel_updates_because_they_only_read_the_coordinator(platform):
    module = importlib.import_module(f"custom_components.ztm_warsaw.{platform}")
    assert module.PARALLEL_UPDATES == 0


async def test_e2e_37_the_entities_without_a_dynamic_icon_get_theirs_from_icons_json(env):
    """Next 1-3, Last update and the calendar have no icon in code: each has a translation key that icons.json knows, so Home Assistant
    does not fall back to the default eye."""
    import json
    from pathlib import Path

    from homeassistant.helpers import entity_registry as er

    entry = await env.add_entry_via_flow(line=LINE)
    icons = json.loads((Path(__file__).resolve().parents[2] / "custom_components" / "ztm_warsaw" / "icons.json").read_text())["entity"]
    by_suffix = {"_last_update": "last_update", "_next_1": "next_1", "_next_2": "next_2", "_next_3": "next_3", "_calendar": "timetable"}
    seen = set()
    for reg in er.async_entries_for_config_entry(env.entity_registry, entry.entry_id):
        for suffix, key in by_suffix.items():
            if reg.unique_id.endswith(suffix):
                assert reg.translation_key == key, reg.unique_id
                assert icons[reg.domain][key]["default"].startswith("mdi:"), key
                seen.add(key)
    assert seen == set(by_suffix.values())
