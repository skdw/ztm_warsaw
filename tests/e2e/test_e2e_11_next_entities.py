"""E2E-36: the departures after the next one (Next 1 to Next 3) as sensors of their own, disabled by default."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util


from .fake_city import stop_name_for

pytestmark = pytest.mark.e2e

LINE = "151"


def _entity_id(position):
    """The entity ID of Next ``position`` of the line at its stop: made of the numbers, as the other sensors are."""
    return f"sensor.line_{LINE}_from_7009_01_next_{position}"


async def _line_with_next_enabled(env, walking_time=0):
    """A line whose Next 1 to Next 3 sensors are switched on in the registry before the setup (the same write as in the UI)."""
    entry = await env.add_entry_via_flow(line=LINE)
    for position in (1, 2, 3):
        env.entity_registry.async_update_entity(_entity_id(position), disabled_by=None)
    if walking_time:
        (subentry_id,) = entry.subentries
        subentry = entry.subentries[subentry_id]
        env.hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, "walking_time": walking_time})
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.settle()
    return entry


def _coordinator(env, entry):
    """The coordinator of the one stop of the line."""
    (runtime,) = entry.runtime_data["units"].values()
    return runtime["coordinator"]


def _state_time(env, position):
    """The moment Next ``position`` shows as its state."""
    return datetime.fromisoformat(env.hass.states.get(_entity_id(position)).state)


async def test_e2e_36_they_are_off_by_default_and_have_no_state_until_switched_on(env):
    await env.add_entry_via_flow(line=LINE)
    for position in (1, 2, 3):
        entry = env.entity_registry.async_get(_entity_id(position))
        assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        state = env.hass.states.get(_entity_id(position))
        assert state is None or state.state == "unavailable"


async def test_e2e_36_each_shows_the_departure_the_main_sensor_lists_as_its_attribute(env):
    entry = await _line_with_next_enabled(env)
    coordinator = _coordinator(env, entry)
    upcoming = coordinator.upcoming(dt_util.utcnow())
    main = env.state(LINE)
    for position in (1, 2, 3):
        assert _state_time(env, position) == upcoming[position].dt
        attrs = env.hass.states.get(_entity_id(position)).attributes
        assert attrs["Headsign"] == main.attributes[f"Next {position}, Headsign"]
        assert attrs["Brigade"] == main.attributes[f"Next {position}, Brigade"]
        assert attrs["Departure Day"] == main.attributes[f"Next {position}, Departure Day"]
        assert attrs["Route ID"] == main.attributes[f"Next {position}, Route ID"]
    assert env.hass.states.get(_entity_id(1)).attributes["friendly_name"] == f"Line {LINE} {stop_name_for('7009')} 01 Next 1"


async def test_e2e_36_they_move_up_when_the_next_departure_leaves(env):
    entry = await _line_with_next_enabled(env)
    coordinator = _coordinator(env, entry)
    first = coordinator.upcoming(dt_util.utcnow())[0].dt
    moment = first + timedelta(seconds=1)  # the next departure has left
    await env.run_to(moment)
    upcoming = _coordinator(env, entry).upcoming(moment)  # the entry reloads after the switch-on: the coordinator is a new one
    for position in (1, 2, 3):
        assert _state_time(env, position) == upcoming[position].dt


async def test_e2e_36_they_count_only_the_departures_that_can_be_caught(env):
    entry = await _line_with_next_enabled(env, walking_time=30)
    coordinator = _coordinator(env, entry)
    catchable = coordinator.upcoming(dt_util.utcnow() + timedelta(minutes=30))
    for position in (1, 2, 3):
        assert _state_time(env, position) == catchable[position].dt
    moment = catchable[0].dt - timedelta(minutes=30) + timedelta(seconds=1)  # one second too late to walk to the first one
    await env.run_to(moment)
    moved = _coordinator(env, entry).upcoming(moment + timedelta(minutes=30))
    assert _state_time(env, 1) == moved[1].dt


async def test_e2e_36_one_with_too_few_departures_left_has_no_state_and_keeps_its_attribution(env):
    entry = await _line_with_next_enabled(env)
    last = _coordinator(env, entry).known()[-1].dt
    await env.run_to(last - timedelta(minutes=1))  # the last departure of the day is the next one: nothing after it
    for position in (1, 2, 3):
        state = env.hass.states.get(_entity_id(position))
        assert state.state == "unknown"
        assert set(state.attributes) >= {"attribution"}
        assert "Headsign" not in state.attributes
