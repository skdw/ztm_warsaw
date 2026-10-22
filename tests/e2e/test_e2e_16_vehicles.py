"""E2E-45: how far the vehicle of the next departure is from the stop (a sensor in metres, off by default)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.util import dt as dt_util

from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_TOKEN, WARSAW, Http, stop_name_for

pytestmark = pytest.mark.e2e

SENSOR = "sensor.line_151_from_7009_01_vehicle_distance"


def _row(*, line="151", brigade="1", number="1234", seconds_ago=10, lat=52.2297, lon=21.0122):
    """One position as the City sends it: the time in Warsaw wall-clock text, ``seconds_ago`` before now."""
    moment = dt_util.utcnow().astimezone(WARSAW) - timedelta(seconds=seconds_ago)
    return {"Lines": line, "Brigade": brigade, "Lat": lat, "Lon": lon, "Time": moment.strftime("%Y-%m-%d %H:%M:%S"), "VehicleNumber": number}


async def _entry(env, *, rows=(), enabled=True, api_key=DEFAULT_TOKEN, line="151"):
    """An entry with its distance sensor switched on in the registry before the setup (the same write as in the UI) and the City holding ``rows``."""
    env.city.vehicles = list(rows)
    entry = await env.add_entry(setup=False, api_key=api_key, line=line)
    env.entity_registry.async_get_or_create(
        "sensor", DOMAIN, f"line_{line}_from_7009_01_vehicle_distance", config_entry=entry,
        disabled_by=None if enabled else RegistryEntryDisabler.INTEGRATION, suggested_object_id=f"line_{line}_from_7009_01_vehicle_distance",
    )
    await env.hass.config_entries.async_setup(entry.entry_id)
    await env.settle()
    return entry


async def test_e2e_45_the_distance_of_the_vehicle_of_the_next_departure_is_in_metres_with_its_details(env):
    await _entry(env, rows=[_row(brigade="01"), _row(brigade="2", number="9999", lat=1.0, lon=1.0)])
    state = env.hass.states.get(SENSOR)
    assert state is not None
    assert float(state.state) > 0
    assert state.attributes["unit_of_measurement"] == "m"
    assert state.attributes["Vehicle number"] == "1234", "the vehicle of the next departure's brigade, '01' and '1' being the same"
    assert state.attributes["Status"] == "tracking"
    assert "latitude" not in state.attributes, "a position here would draw the vehicle on the map once more for every stop"
    assert env.city.count("vehicles") == 1, "the first positions are fetched at once, not after the first interval"


async def test_e2e_45_a_position_older_than_three_minutes_is_not_measured(env):
    await _entry(env, rows=[_row(seconds_ago=200)])
    state = env.hass.states.get(SENSOR)
    assert state.state == "unknown"
    assert state.attributes["Status"] == "old_position"


async def test_e2e_45_a_brigade_the_city_does_not_report_has_no_distance(env):
    await _entry(env, rows=[_row(brigade="7")])
    state = env.hass.states.get(SENSOR)
    assert state.state == "unknown"
    assert state.attributes["Status"] == "no_vehicle"


async def test_e2e_45_the_distance_follows_the_vehicle_every_half_minute(env):
    await _entry(env, rows=[_row(lat=52.20)])
    before = float(env.hass.states.get(SENSOR).state)
    env.city.vehicles = [_row(lat=52.21)]
    await env.advance(seconds=31)
    assert float(env.hass.states.get(SENSOR).state) != before


async def test_e2e_45_nothing_is_asked_while_the_next_departure_is_far(env):
    with patch("custom_components.ztm_warsaw.vehicle_sensor.WANTED_WITHIN", timedelta(minutes=1)):
        await _entry(env, rows=[_row()])
        await env.advance(seconds=65)
    assert env.city.count("vehicles") == 0
    assert env.hass.states.get(SENSOR).attributes["Status"] == "too_early"


async def test_e2e_45_the_sensor_is_off_by_default_and_costs_the_city_nothing(env):
    env.city.vehicles = [_row()]
    await env.add_entry(api_key=DEFAULT_TOKEN)
    entity = env.entity_registry.async_get(SENSOR)
    assert entity is not None
    assert entity.disabled_by is not None
    assert env.hass.states.get(SENSOR) is None
    await env.advance(seconds=65)
    assert env.city.count("vehicles") == 0


async def test_e2e_45_an_old_key_has_no_vehicle_sensor(env):
    env.city.vehicles = [_row()]
    await env.add_entry()  # the old key: only the new host knows the positions
    assert env.entity_registry.async_get(SENSOR) is None
    assert env.city.count("vehicles") == 0


async def test_e2e_45_a_failing_city_is_said_and_the_value_comes_back_when_it_heals(env, caplog):
    await _entry(env, rows=[_row(seconds_ago=160)])  # a position that will be too old a poll later
    assert env.hass.states.get(SENSOR).attributes["Status"] == "tracking"
    env.city.script("vehicles", Http(500), Http(500))  # one poll fails (the request is tried twice)
    await env.advance(seconds=31)
    state = env.hass.states.get(SENSOR)
    assert state.attributes["Status"] == "city_unavailable", "the old position is not used and the failure is the reason"
    assert state.state == "unknown"
    assert sum("did not send the positions" in r.getMessage() for r in caplog.records) == 1
    env.city.vehicles = [_row()]
    await env.advance(seconds=31)
    assert env.hass.states.get(SENSOR).attributes["Status"] == "tracking"


async def test_e2e_45_a_failing_city_is_asked_less_and_less_often(env):
    await _entry(env, rows=[_row()])
    env.city.always("vehicles", Http(500))
    env.city.reset_counts()
    await env.advance(seconds=300)
    assert 0 < env.city.count("vehicles") < 10, "ten polls in five minutes would be one every half minute"


async def test_e2e_45_unloading_the_entry_stops_the_polling(env):
    entry = await _entry(env, rows=[_row()])
    assert await env.hass.config_entries.async_unload(entry.entry_id)
    env.city.reset_counts()
    await env.advance(seconds=120)
    assert env.city.count("vehicles") == 0


async def test_e2e_45_the_distance_follows_the_departure_the_sensor_shows_when_there_is_a_walking_time(env):
    entry = await env.add_entry(setup=False, api_key=DEFAULT_TOKEN, data={
        "api_key": DEFAULT_TOKEN, "busstop_id": 7009, "busstop_nr": "01", "line": "151", "departures": 3,
    })
    env.entity_registry.async_get_or_create(
        "sensor", DOMAIN, "line_151_from_7009_01_vehicle_distance", config_entry=entry, disabled_by=None,
        suggested_object_id="line_151_from_7009_01_vehicle_distance",
    )
    env.city.vehicles = [_row(brigade="1", number="111"), _row(brigade="2", number="222")]
    await env.hass.config_entries.async_setup(entry.entry_id)
    await env.settle()
    assert env.hass.states.get(SENSOR).attributes["Vehicle number"] == "111", "the next departure is at 12:04, brigade 1"
    entry.runtime_data["coordinator"].walking_minutes = 10  # the sensor now skips 12:04 and shows 12:24, the departure of brigade 2
    await env.advance(seconds=31)
    state = env.hass.states.get(SENSOR)
    assert state.attributes["Vehicle number"] == "222"
    assert state.attributes["Status"] == "tracking", "12:24 is more than 15 minutes away, but the user has to leave 10 minutes earlier"


async def test_e2e_45_a_departure_without_a_brigade_says_so_and_is_not_a_missing_timetable(env):
    entry = await _entry(env, rows=[_row()])
    for departure in entry.runtime_data["coordinator"].data.departures:
        departure.brygada = None
    await env.advance(seconds=31)
    assert env.hass.states.get(SENSOR).attributes["Status"] == "no_brigade"


async def test_e2e_45_the_sensor_takes_the_stop_name_into_its_name(env):
    await _entry(env, rows=[_row()])
    assert env.hass.states.get(SENSOR).attributes["friendly_name"] == f"Line 151 {stop_name_for('7009')} 01 Vehicle distance"


async def test_e2e_45_without_the_position_of_the_stop_there_is_no_distance(env):
    entry = await _entry(env, rows=[_row()])
    entry.runtime_data["coordinator"].data.stop_info = {"nazwa_zespolu": "Somewhere"}  # a stop whose position the City did not give
    await env.advance(seconds=31)
    state = env.hass.states.get(SENSOR)
    assert state.attributes["Status"] == "tracking"
    assert state.state == "unknown"


async def test_e2e_45_without_a_timetable_that_may_be_shown_nothing_is_asked_and_the_sensor_is_unavailable(env):
    entry = await _entry(env, rows=[_row()])
    entry.runtime_data["coordinator"].last_update_success = False  # the sensors refuse the timetable too
    env.city.reset_counts()
    await env.advance(seconds=65)
    assert env.hass.states.get(SENSOR).state == "unavailable"
    assert env.city.count("vehicles") == 0


async def test_e2e_45_after_the_last_departure_there_is_no_timetable_to_follow(env):
    entry = await _entry(env, rows=[_row()])
    entry.runtime_data["coordinator"].data.departures = []  # nothing is left of the day
    await env.advance(seconds=31)
    state = env.hass.states.get(SENSOR)
    assert state.state == "unknown"
    assert state.attributes["Status"] == "no_timetable"


async def test_e2e_45_a_new_timetable_or_a_stop_name_that_arrives_late_is_shown(env):
    entry = await _entry(env, rows=[_row()])
    coordinator = entry.runtime_data["coordinator"]
    coordinator.data.stop_info = {}  # the City has not given the stop's name yet
    coordinator.async_set_updated_data(coordinator.data)
    await env.settle()
    assert env.hass.states.get(SENSOR).attributes["Status"] == "tracking"
    coordinator.data.stop_info = {"nazwa_zespolu": "Late Name"}
    coordinator.async_set_updated_data(coordinator.data)
    await env.settle()
    assert env.hass.states.get(SENSOR).attributes["friendly_name"] == "Line 151 Late Name 01 Vehicle distance"


async def test_e2e_45_the_trackers_of_b6_are_removed_from_the_registry(env):
    """1.2.0b6 had a device tracker per stop: the registry entry is cleaned up when the line loads."""
    entry = await env.add_entry(setup=False, api_key=DEFAULT_TOKEN)
    env.entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, "line_151_from_7009_01_vehicle", config_entry=entry, disabled_by=None,
    )
    assert [e for e in env.entity_registry.entities.values() if e.domain == "device_tracker"], "the old tracker is there before the setup"
    await env.hass.config_entries.async_setup(entry.entry_id)
    await env.settle()
    assert not [e for e in env.entity_registry.entities.values() if e.domain == "device_tracker" and e.platform == DOMAIN]
