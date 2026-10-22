"""E2E-48: the map. One pin for every stop pole and one for every vehicle of the lines that show theirs; nothing is drawn twice."""

from __future__ import annotations

import base64
from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util

from custom_components.ztm_warsaw.const import CONF_SHOW_VEHICLES
from custom_components.ztm_warsaw.utils import get_line_badge, get_stop_badge

from .fake_city import DEFAULT_TOKEN, WARSAW, stop_name_for

pytestmark = pytest.mark.e2e


def _pins(env):
    """The states of every geo_location pin of the integration."""
    return [s for s in env.hass.states.async_all("geo_location") if s.attributes.get("source") == "ztm_warsaw"]


def _poles(env):
    """The pins that are stop poles."""
    return [s for s in _pins(env) if "Stop, ID" in s.attributes]


def _vehicles(env):
    """The pins that are vehicles."""
    return [s for s in _pins(env) if "Vehicle number" in s.attributes]


def _row(*, line="151", brigade="1", number="1234", seconds_ago=10, lat=52.2297, lon=21.0122):
    """One position as the City sends it, ``seconds_ago`` before now."""
    moment = dt_util.utcnow().astimezone(WARSAW) - timedelta(seconds=seconds_ago)
    return {"Lines": line, "Brigade": brigade, "Lat": lat, "Lon": lon, "Time": moment.strftime("%Y-%m-%d %H:%M:%S"), "VehicleNumber": number}


def _decoded(picture: str) -> str:
    """The SVG text of a picture given as a data URI."""
    return base64.b64decode(picture.split(",", 1)[1]).decode()


async def test_e2e_48_a_pole_served_by_two_lines_is_one_pin_with_both_lines(env):
    await env.add_entry(line="523", api_key=DEFAULT_TOKEN)
    await env.add_entry(line="151", api_key=DEFAULT_TOKEN)
    (pole,) = _poles(env)
    assert pole.attributes["Lines"] == "151, 523", "the lines are in order, numbers first"
    assert pole.attributes["friendly_name"] == f"{stop_name_for('7009')} 01 · 151, 523", "the map card writes the name under the pin"
    assert (pole.attributes["Stop, ID"], pole.attributes["Stop, Number"]) == ("7009", "01")
    assert pole.attributes["entity_picture"] == get_stop_badge("01")


async def test_e2e_48_a_line_with_two_poles_gives_two_pins(env):
    entry = await env.add_entry_via_flow(line="151")
    await env.submit_flow(line="151", stop_nr="02")
    await env.settle()
    assert len(entry.subentries) == 2
    assert sorted(p.attributes["Stop, Number"] for p in _poles(env)) == ["01", "02"]


async def test_e2e_48_the_pin_stays_while_another_line_serves_the_pole_and_goes_with_the_last(env):
    first = await env.add_entry(line="151", api_key=DEFAULT_TOKEN)
    second = await env.add_entry(line="523", api_key=DEFAULT_TOKEN)
    assert len(_poles(env)) == 1
    assert await env.hass.config_entries.async_unload(first.entry_id)
    await env.settle()
    (pole,) = _poles(env)
    assert pole.attributes["Lines"] == "523", "the pin moved to the line that is left and lost the line that is gone"
    assert await env.hass.config_entries.async_unload(second.entry_id)
    await env.settle()
    assert _poles(env) == []


async def test_e2e_48_reloading_the_line_that_hosts_the_pin_does_not_double_it(env):
    first = await env.add_entry(line="151", api_key=DEFAULT_TOKEN)
    await env.add_entry(line="523", api_key=DEFAULT_TOKEN)
    assert await env.hass.config_entries.async_reload(first.entry_id)
    await env.settle()
    (pole,) = _poles(env)
    assert pole.attributes["Lines"] == "151, 523"


async def test_e2e_48_a_line_sensor_has_no_position_of_its_own(env):
    await env.add_entry(api_key=DEFAULT_TOKEN)
    assert "latitude" not in env.state().attributes


async def test_e2e_48_vehicles_are_off_by_default_and_cost_the_city_nothing(env):
    env.city.vehicles = [_row()]
    await env.add_entry(api_key=DEFAULT_TOKEN)
    await env.advance(seconds=65)
    assert _vehicles(env) == []
    assert env.city.count("vehicles") == 0


async def test_e2e_48_a_line_with_its_option_on_shows_each_of_its_vehicles_once(env):
    env.city.vehicles = [
        _row(brigade="1", number="1001"), _row(brigade="2", number="1002"),
        _row(line="523", brigade="1", number="9000"),  # another line's vehicle: not this line's pin
        _row(brigade="3", number="1003", seconds_ago=400),  # a position that old is not on the map
    ]
    await env.add_entry(api_key=DEFAULT_TOKEN, options={CONF_SHOW_VEHICLES: True})
    pins = _vehicles(env)
    assert sorted(p.attributes["Vehicle number"] for p in pins) == ["1001", "1002"]
    assert all(p.attributes["Line"] == "151" for p in pins)
    assert pins[0].attributes["entity_picture"] == get_line_badge("151")
    assert "151" in _decoded(pins[0].attributes["entity_picture"])
    assert env.city.count("vehicles") == 1


async def test_e2e_48_a_vehicle_pin_moves_and_goes_when_the_city_stops_reporting_the_vehicle(env):
    env.city.vehicles = [_row(number="1001", lat=52.20), _row(brigade="2", number="1002")]
    await env.add_entry(api_key=DEFAULT_TOKEN, options={CONF_SHOW_VEHICLES: True})
    before = {p.attributes["Vehicle number"]: p.attributes["latitude"] for p in _vehicles(env)}
    assert before["1001"] == 52.20
    env.city.vehicles = [_row(number="1001", lat=52.25)]  # 1002 is not reported any more
    await env.advance(seconds=31)
    after = {p.attributes["Vehicle number"]: p.attributes["latitude"] for p in _vehicles(env)}
    assert after == {"1001": 52.25}


async def test_e2e_48_two_lines_with_vehicles_share_one_request_and_draw_each_vehicle_once(env):
    env.city.vehicles = [_row(number="1001"), _row(line="523", number="5001")]
    await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={CONF_SHOW_VEHICLES: True})
    await env.add_entry(line="523", api_key=DEFAULT_TOKEN, options={CONF_SHOW_VEHICLES: True})
    env.city.reset_counts()
    await env.advance(seconds=31)
    assert env.city.count("vehicles") == 1, "one request for both lines (both are buses)"
    assert sorted((p.attributes["Line"], p.attributes["Vehicle number"]) for p in _vehicles(env)) == [("151", "1001"), ("523", "5001")]


async def test_e2e_48_vehicles_need_a_token(env):
    env.city.vehicles = [_row()]
    await env.add_entry(options={CONF_SHOW_VEHICLES: True})  # an old key
    assert _vehicles(env) == []
    assert env.city.count("vehicles") == 0


async def test_e2e_48_unloading_the_line_takes_its_vehicles_away_and_stops_the_polling(env):
    env.city.vehicles = [_row()]
    entry = await env.add_entry(api_key=DEFAULT_TOKEN, options={CONF_SHOW_VEHICLES: True})
    assert len(_vehicles(env)) == 1
    assert await env.hass.config_entries.async_unload(entry.entry_id)
    await env.settle()
    assert _vehicles(env) == []
    env.city.reset_counts()
    await env.advance(seconds=120)
    assert env.city.count("vehicles") == 0


async def test_e2e_48_configure_chooses_the_vehicles_without_asking_for_the_token_again(env):
    entry = await env.add_entry_via_flow(line="151", api_key=DEFAULT_TOKEN)
    form = await env.hass.config_entries.options.async_init(entry.entry_id)
    assert form["type"] == "form"
    fields = [str(k) for k in form["data_schema"].schema]
    assert fields == ["api_key", "show_vehicles"]
    env.city.reset_counts()
    done = await env.hass.config_entries.options.async_configure(form["flow_id"], {"show_vehicles": True})
    await env.settle()
    assert done["type"] == "create_entry"
    assert entry.options[CONF_SHOW_VEHICLES] is True
    assert entry.data["api_key"] == DEFAULT_TOKEN, "an empty token field keeps the token"
    assert env.city.count("lines") == 0, "no check of a token that was not changed"


async def test_e2e_48_configure_for_an_old_key_is_the_form_of_the_key_only(env):
    entry = await env.add_entry_via_flow(line="151")
    form = await env.hass.config_entries.options.async_init(entry.entry_id)
    assert [str(k) for k in form["data_schema"].schema] == ["api_key"]
