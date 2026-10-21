"""E2E-41: the Status sensor says in words what is going on with a stop."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.ztm_warsaw import sensor as sensor_module

pytestmark = pytest.mark.e2e

LINE = "525"
STATUS = f"sensor.line_{LINE.lower()}_from_7009_01_status"
MAIN = f"sensor.line_{LINE.lower()}_from_7009_01"


def _coordinator(entry):
    """The coordinator of the one stop of the line."""
    (runtime,) = entry.runtime_data["units"].values()
    return runtime["coordinator"]


def _entity(env):
    """The Status entity itself, to ask it what it would say at another moment."""
    return env.hass.data["entity_components"]["sensor"].get_entity(STATUS)


async def test_e2e_41_a_stop_with_departures_to_catch_is_running_and_the_status_is_translatable(env):
    await env.add_entry_via_flow(line=LINE)
    state = env.hass.states.get(STATUS)
    assert state.state == "running"
    assert state.attributes["device_class"] == "enum"
    assert "after_last_departure" in state.attributes["options"]


async def test_e2e_41_after_the_last_departure_it_says_so_while_the_main_sensor_is_unknown(env):
    entry = await env.add_entry_via_flow(line=LINE)
    last = _coordinator(entry).known()[-1].dt
    await env.run_to(last + timedelta(minutes=1))
    assert env.hass.states.get(MAIN).state == "unknown"
    assert env.hass.states.get(STATUS).state == "after_last_departure"


async def test_e2e_41_a_line_that_does_not_run_today_says_so(env):
    env.move_to("2026-10-17 12:00")  # a Saturday: line 411 does not run
    await env.add_entry(line="411")  # the setup dialog refuses it, a 1.1.x entry or a later day has it
    assert env.hass.states.get("sensor.line_411_from_7009_01_status").state == "no_service_today"


async def test_e2e_41_when_every_departure_left_is_sooner_than_the_walking_time_it_says_it_cannot_be_caught(env):
    entry = await env.add_entry_via_flow(line=LINE)
    (subentry_id,) = entry.subentries
    subentry = entry.subentries[subentry_id]
    env.hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, "walking_time": 30})
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.settle()
    last = _coordinator(entry).known()[-1].dt
    await env.run_to(last - timedelta(minutes=10))
    assert env.hass.states.get(STATUS).state == "cannot_catch"


async def test_e2e_41_when_the_city_does_not_answer_with_a_timetable_the_status_says_so_while_the_main_sensor_is_unavailable(env):
    entry = await env.add_entry_via_flow(line=LINE)
    env.city.valid_keys.clear()
    await env.hourly_tick()
    assert env.hass.states.get(MAIN).state == "unavailable"
    assert env.hass.states.get(STATUS).state == "city_error", "the status is available exactly when the others are not"
    assert entry.state is not None


async def test_e2e_41_the_swap_of_the_city_and_a_missing_timetable_have_words_of_their_own(env):
    entry = await env.add_entry_via_flow(line=LINE)
    coordinator = _coordinator(entry)
    entity = _entity(env)
    now = dt_util.utcnow() + timedelta(days=1)  # nothing is left to catch a day later
    with patch.object(sensor_module, "in_swap_window", return_value=True):
        assert entity._compute(now) == "city_updating"
    with patch.object(coordinator, "is_fresh", return_value=False):
        assert entity._compute(now) == "waiting"
