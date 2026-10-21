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


async def test_e2e_39_the_sensor_says_when_the_first_and_the_last_departure_of_the_day_is(env):
    from homeassistant.util.dt import as_local

    entry = await env.add_entry_via_flow(line=LINE)
    (runtime,) = entry.runtime_data["units"].values()
    known = runtime["coordinator"].known()
    attrs = env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_01").attributes
    assert attrs["Timetable, First Departure"] == as_local(known[0].dt).strftime("%H:%M")
    assert attrs["Timetable, Last Departure"] == as_local(known[-1].dt).strftime("%H:%M")


async def test_e2e_39_after_the_last_departure_the_state_is_unknown_but_the_times_of_the_day_are_still_there(env):
    """What a person needs to understand "unknown" at midnight: there is no next departure, but the last one is on the sensor."""
    from datetime import timedelta

    from homeassistant.util.dt import as_local

    entry = await env.add_entry_via_flow(line=LINE)
    (runtime,) = entry.runtime_data["units"].values()
    last = runtime["coordinator"].known()[-1].dt
    await env.run_to(last + timedelta(minutes=1))
    state = env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_01")
    assert state.state == "unknown"
    assert state.attributes["Upcoming, Headsign"] == "No service"
    assert state.attributes["Timetable, Last Departure"] == as_local(last).strftime("%H:%M")
    assert "Timetable, First Departure" in state.attributes


async def test_e2e_39_the_times_are_warsaw_times_whatever_time_zone_home_assistant_has(env):
    """The attribute says Europe/Warsaw as its zone, so the times must be Warsaw ones for a Home Assistant set to another zone."""
    from zoneinfo import ZoneInfo

    entry = await env.add_entry_via_flow(line=LINE)
    (runtime,) = entry.runtime_data["units"].values()
    known = runtime["coordinator"].known()
    await env.hass.config.async_set_time_zone("America/New_York")
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.settle()
    attrs = env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_01").attributes
    warsaw = ZoneInfo("Europe/Warsaw")
    assert attrs["Timetable, First Departure"] == known[0].dt.astimezone(warsaw).strftime("%H:%M")
    assert attrs["Timetable, Last Departure"] == known[-1].dt.astimezone(warsaw).strftime("%H:%M")


def _reconfigure(env, entry):
    """Start Home Assistant's own *Reconfigure* flow of an entry."""
    from homeassistant.config_entries import SOURCE_RECONFIGURE

    return env.hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id})


async def test_e2e_40_reconfigure_replaces_an_old_key_by_a_token_and_reloads_the_line_once(env):
    from unittest.mock import patch

    from homeassistant.config_entries import ConfigEntryState

    from .fake_city import DEFAULT_TOKEN

    entry = await env.add_entry_via_flow(line=LINE)
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    form = await _reconfigure(env, entry)
    assert (form["type"], form["step_id"]) == ("form", "reconfigure"), "an old key is nudged to a token"
    assert form["description_placeholders"]["portal"] == "https://dane.um.warszawa.pl/pl/key-api"
    with patch.object(env.hass.config_entries, "async_reload", wraps=env.hass.config_entries.async_reload) as reload:
        done = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": f" {DEFAULT_TOKEN} "})
        await env.settle()
    assert (done["type"], done["reason"]) == ("abort", "reconfigure_successful")
    assert entry.data["api_key"] == DEFAULT_TOKEN
    assert reload.call_count == 1
    assert entry.state is ConfigEntryState.LOADED


async def test_e2e_40_reconfigure_of_an_entry_with_a_token_asks_for_the_new_token_and_refuses_a_bad_one(env):
    from .fake_city import DEFAULT_TOKEN

    env.city.valid_tokens.add(DEFAULT_TOKEN)
    entry = await env.add_entry_via_flow(line=LINE, api_key=DEFAULT_TOKEN)
    form = await _reconfigure(env, entry)
    assert (form["type"], form["step_id"]) == ("form", "reconfigure_token")
    bad = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": "not a key"})
    assert (bad["type"], bad["errors"]) == ("form", {"base": "invalid_api_key"})
    assert entry.data["api_key"] == DEFAULT_TOKEN


async def test_e2e_40_reconfigure_of_an_entry_whose_data_cannot_be_read_aborts_and_changes_nothing(env):
    from .fake_city import DEFAULT_KEY

    entry = await env.add_entry(data={"api_key": DEFAULT_KEY}, setup=False)  # no stop: a 1.1.x entry that cannot be run
    result = await _reconfigure(env, entry)
    assert (result["type"], result["reason"]) == ("abort", "unknown")
    assert entry.data["api_key"] == DEFAULT_KEY


async def test_e2e_40_reconfigure_accepts_a_key_that_works_for_a_line_that_does_not_run_today(env):
    """A weekday-only line on a Saturday: the key is judged by the key, as in Configure."""
    from .fake_city import DEFAULT_TOKEN

    env.move_to("2026-10-17 12:00")
    entry = await env.add_entry(line="411")
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    form = await _reconfigure(env, entry)
    done = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert (done["type"], done["reason"]) == ("abort", "reconfigure_successful")
    assert entry.data["api_key"] == DEFAULT_TOKEN
