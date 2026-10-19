"""E2E-35: the walking time to a stop: the sensor skips the departures that cannot be caught."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import InvalidData
from homeassistant.util import dt as dt_util


pytestmark = pytest.mark.e2e

LINE = "151"
WALK = 10


async def _set_walking_time(env, entry, minutes):
    """Run *Reconfigure* on the one stop of the line with this walking time and let the entry reload."""
    (subentry_id,) = entry.subentries
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "reconfigure", "subentry_id": subentry_id})
    assert (form["type"], form["step_id"]) == ("form", "reconfigure")
    done = await manager.async_configure(form["flow_id"], {"walking_time": minutes})
    await env.settle()
    return form, done


def _coordinator(env, entry):
    """The coordinator of the one stop of a line entry."""
    (runtime,) = entry.runtime_data["units"].values()
    return runtime["coordinator"]


def _state_time(env):
    """The moment the sensor of the line shows as its state."""
    return datetime.fromisoformat(env.state(LINE).state)


async def test_e2e_35_without_a_walking_time_nothing_changes(env):
    entry = await env.add_entry_via_flow(line=LINE)
    coordinator = _coordinator(env, entry)
    assert _state_time(env) == coordinator.upcoming(dt_util.utcnow())[0].dt
    assert "Walking time, Minutes" not in env.state(LINE).attributes


async def test_e2e_35_the_sensor_skips_the_departures_sooner_than_the_walking_time(env):
    entry = await env.add_entry_via_flow(line=LINE)
    first = _state_time(env)
    assert first - dt_util.utcnow() < timedelta(minutes=WALK), "the next departure is sooner than the walking time"
    form, done = await _set_walking_time(env, entry, WALK)
    assert (done["type"], done["reason"]) == ("abort", "reconfigure_successful")
    coordinator = _coordinator(env, entry)  # the entry was reloaded: this is the new coordinator
    shown = _state_time(env)
    assert shown > first
    assert shown >= dt_util.utcnow() + timedelta(minutes=WALK)
    assert shown == coordinator.upcoming(dt_util.utcnow() + timedelta(minutes=WALK))[0].dt
    assert env.state(LINE).attributes["Walking time, Minutes"] == WALK


async def test_e2e_35_the_sensor_moves_on_when_a_departure_can_no_longer_be_caught(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await _set_walking_time(env, entry, WALK)
    coordinator = _coordinator(env, entry)  # after the reload
    catchable = _state_time(env)
    moment = catchable - timedelta(minutes=WALK) + timedelta(seconds=1)  # one second too late to walk to it
    await env.run_to(moment)
    assert _state_time(env) == coordinator.upcoming(moment + timedelta(minutes=WALK))[0].dt
    assert _state_time(env) > catchable


async def test_e2e_35_the_form_offers_the_walking_time_the_stop_has_and_refuses_what_is_out_of_range(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await _set_walking_time(env, entry, 7)
    (subentry_id,) = entry.subentries
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "reconfigure", "subentry_id": subentry_id})
    field = next(k for k in form["data_schema"].schema if str(k) == "walking_time")
    assert field.default() == 7
    assert form["description_placeholders"] == {"stop": entry.subentries[subentry_id].title}
    for bad in (-1, 121):
        with pytest.raises(InvalidData):
            await manager.async_configure(form["flow_id"], {"walking_time": bad})
    assert entry.subentries[subentry_id].data["walking_time"] == 7


async def test_e2e_35_a_new_walking_time_reloads_the_entry_once_and_keeps_the_rest_of_the_stop(env):
    entry = await env.add_entry_via_flow(line=LINE)
    (subentry_id,) = entry.subentries
    before = dict(entry.subentries[subentry_id].data)
    with patch.object(env.hass.config_entries, "async_reload", wraps=env.hass.config_entries.async_reload) as reload:
        await _set_walking_time(env, entry, WALK)
    assert reload.call_count == 1
    assert entry.state is ConfigEntryState.LOADED
    assert dict(entry.subentries[subentry_id].data) == {**before, "walking_time": WALK}
    await _set_walking_time(env, entry, 0)
    assert "Walking time, Minutes" not in env.state(LINE).attributes, "0 is no walking time"


async def test_e2e_35_the_walking_time_stays_in_the_attributes_when_no_departure_can_be_caught(env):
    entry = await env.add_entry_via_flow(line=LINE)
    last = _coordinator(env, entry).known()[-1].dt
    await env.run_to(last - timedelta(minutes=30))
    await _set_walking_time(env, entry, 60)  # every departure left is sooner than that
    state = env.state(LINE)
    assert state.state == "unknown"
    assert state.attributes["Upcoming, Headsign"] == "No service"
    assert state.attributes["Walking time, Minutes"] == 60
