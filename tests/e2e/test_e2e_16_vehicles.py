"""E2E-45: the vehicle of the next departure as a pin on the map (a device tracker, off by default)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_TOKEN, WARSAW, Http, stop_name_for

pytestmark = pytest.mark.e2e

TRACKER = "device_tracker.line_151_from_7009_01_vehicle"


def _row(*, line="151", brigade="1", number="1234", seconds_ago=10, lat=52.2297, lon=21.0122):
    """One position as the City sends it: the time in Warsaw wall-clock text, ``seconds_ago`` before now."""
    moment = dt_util.utcnow().astimezone(WARSAW) - timedelta(seconds=seconds_ago)
    return {"Lines": line, "Brigade": brigade, "Lat": lat, "Lon": lon, "Time": moment.strftime("%Y-%m-%d %H:%M:%S"), "VehicleNumber": number}


async def _entry(env, *, rows=(), enabled=True, api_key=DEFAULT_TOKEN, line="151"):
    """An entry with its tracker switched on in the registry before the setup (the same write as in the UI) and the City holding ``rows``."""
    env.city.vehicles = list(rows)
    entry = await env.add_entry(setup=False, api_key=api_key, line=line)
    env.entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, f"line_{line}_from_7009_01_vehicle", config_entry=entry,
        disabled_by=None if enabled else er_disabled(), suggested_object_id=f"line_{line}_from_7009_01_vehicle",
    )
    await env.hass.config_entries.async_setup(entry.entry_id)
    await env.settle()
    return entry


def er_disabled():
    """The registry's mark for an entity the integration switched off."""
    from homeassistant.helpers.entity_registry import RegistryEntryDisabler

    return RegistryEntryDisabler.INTEGRATION


async def test_e2e_45_the_vehicle_of_the_next_departure_is_a_pin_with_its_details(env):
    await _entry(env, rows=[_row(brigade="01"), _row(brigade="2", number="9999", lat=1.0, lon=1.0)])
    state = env.hass.states.get(TRACKER)
    assert state is not None
    assert state.attributes["latitude"] == 52.2297
    assert state.attributes["longitude"] == 21.0122
    assert state.attributes["Vehicle number"] == "1234", "the vehicle of the next departure's brigade, '01' and '1' being the same"
    assert state.attributes["Status"] == "tracking"
    assert state.attributes["Distance to stop"] > 0
    assert env.city.count("vehicles") == 1, "the first positions are fetched at once, not after the first interval"


async def test_e2e_45_a_position_older_than_three_minutes_is_not_shown(env):
    await _entry(env, rows=[_row(seconds_ago=200)])
    state = env.hass.states.get(TRACKER)
    assert state.state == "unknown"
    assert "latitude" not in state.attributes
    assert state.attributes["Status"] == "old_position"


async def test_e2e_45_a_brigade_the_city_does_not_report_has_no_pin(env):
    await _entry(env, rows=[_row(brigade="7")])
    state = env.hass.states.get(TRACKER)
    assert state.state == "unknown"
    assert state.attributes["Status"] == "no_vehicle"


async def test_e2e_45_the_pin_follows_the_vehicle_every_half_minute(env):
    await _entry(env, rows=[_row(lat=52.20)])
    assert env.hass.states.get(TRACKER).attributes["latitude"] == 52.20
    env.city.vehicles = [_row(lat=52.21)]
    await env.advance(seconds=31)
    assert env.hass.states.get(TRACKER).attributes["latitude"] == 52.21


async def test_e2e_45_nothing_is_asked_while_the_next_departure_is_far(env):
    with patch("custom_components.ztm_warsaw.device_tracker.WANTED_WITHIN", timedelta(minutes=1)):
        await _entry(env, rows=[_row()])
        await env.advance(seconds=65)
    assert env.city.count("vehicles") == 0
    assert env.hass.states.get(TRACKER).attributes["Status"] == "too_early"


async def test_e2e_45_the_tracker_is_off_by_default_and_costs_the_city_nothing(env):
    env.city.vehicles = [_row()]
    await env.add_entry(api_key=DEFAULT_TOKEN)
    entity = env.entity_registry.async_get(TRACKER)
    assert entity is not None
    assert entity.disabled_by is not None
    assert env.hass.states.get(TRACKER) is None
    await env.advance(seconds=65)
    assert env.city.count("vehicles") == 0


async def test_e2e_45_an_old_key_has_no_tracker(env):
    env.city.vehicles = [_row()]
    await env.add_entry()  # the old key: only the new host knows the positions
    assert env.entity_registry.async_get(TRACKER) is None
    assert env.city.count("vehicles") == 0


async def test_e2e_45_a_failing_city_is_said_and_the_pin_comes_back_when_it_heals(env, caplog):
    await _entry(env, rows=[_row(seconds_ago=160)])  # a position that will be too old a poll later
    assert env.hass.states.get(TRACKER).attributes["Status"] == "tracking"
    env.city.script("vehicles", Http(500), Http(500))  # one poll fails (the request is tried twice)
    await env.advance(seconds=31)
    state = env.hass.states.get(TRACKER)
    assert state.attributes["Status"] == "city_unavailable", "the old position is not shown and the failure is the reason"
    assert state.state == "unknown"
    assert sum("did not send the positions" in r.getMessage() for r in caplog.records) == 1
    env.city.vehicles = [_row()]
    await env.advance(seconds=31)
    assert env.hass.states.get(TRACKER).attributes["Status"] == "tracking"


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


async def test_e2e_45_two_lines_with_one_token_share_one_request(env):
    env.city.vehicles = [_row(), *[_row(line="523", brigade=str(n), number="55") for n in range(1, 10)]]
    first = await env.add_entry(setup=False, api_key=DEFAULT_TOKEN)
    second = await env.add_entry(setup=False, api_key=DEFAULT_TOKEN, line="523")
    for entry, line in ((first, "151"), (second, "523")):
        env.entity_registry.async_get_or_create(
            "device_tracker", DOMAIN, f"line_{line}_from_7009_01_vehicle", config_entry=entry, disabled_by=None,
            suggested_object_id=f"line_{line}_from_7009_01_vehicle",
        )
    await env.hass.config_entries.async_setup(first.entry_id)  # sets up every entry of the integration
    await env.settle()
    env.city.reset_counts()
    await env.advance(seconds=31)
    assert env.city.count("vehicles") == 1, "one request for both followers (both are buses)"
    assert env.hass.states.get(TRACKER).attributes["Status"] == "tracking"
    assert env.hass.states.get("device_tracker.line_523_from_7009_01_vehicle").attributes["Vehicle number"] == "55"


async def test_e2e_45_the_tracker_follows_the_departure_the_sensor_shows_when_there_is_a_walking_time(env):
    entry = await env.add_entry(setup=False, api_key=DEFAULT_TOKEN, data={
        "api_key": DEFAULT_TOKEN, "busstop_id": 7009, "busstop_nr": "01", "line": "151", "departures": 3,
    })
    env.entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, "line_151_from_7009_01_vehicle", config_entry=entry, disabled_by=None,
        suggested_object_id="line_151_from_7009_01_vehicle",
    )
    env.city.vehicles = [_row(brigade="1", number="111"), _row(brigade="2", number="222")]
    await env.hass.config_entries.async_setup(entry.entry_id)
    await env.settle()
    assert env.hass.states.get(TRACKER).attributes["Vehicle number"] == "111", "the next departure is at 12:04, brigade 1"
    coordinator = entry.runtime_data["coordinator"]
    coordinator.walking_minutes = 10  # the sensor now skips 12:04 and shows 12:24, the departure of brigade 2
    await env.advance(seconds=31)
    state = env.hass.states.get(TRACKER)
    assert state.attributes["Vehicle number"] == "222"
    assert state.attributes["Status"] == "tracking", "12:24 is more than 15 minutes away, but the user has to leave 10 minutes earlier"


async def test_e2e_45_a_departure_without_a_brigade_says_so_and_is_not_a_missing_timetable(env):
    entry = await _entry(env, rows=[_row()])
    coordinator = entry.runtime_data["coordinator"]
    for departure in coordinator.data.departures:
        departure.brygada = None
    await env.advance(seconds=31)
    assert env.hass.states.get(TRACKER).attributes["Status"] == "no_brigade"


async def test_e2e_45_the_tracker_takes_the_stop_name_into_its_name(env):
    await _entry(env, rows=[_row()])
    assert env.hass.states.get(TRACKER).attributes["friendly_name"] == f"Line 151 {stop_name_for('7009')} 01 Vehicle"


async def test_e2e_45_without_the_position_of_the_stop_there_is_no_distance(env):
    entry = await _entry(env, rows=[_row()])
    coordinator = entry.runtime_data["coordinator"]
    coordinator.data.stop_info = {"nazwa_zespolu": "Somewhere"}  # a stop whose position the City did not give
    await env.advance(seconds=31)
    attrs = env.hass.states.get(TRACKER).attributes
    assert attrs["Status"] == "tracking"
    assert "Distance to stop" not in attrs
