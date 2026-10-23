"""E2E-48: the map. One pin for every stop pole and one for every vehicle of the lines that show theirs; nothing is drawn twice."""

from __future__ import annotations

import base64
from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util

from custom_components.ztm_warsaw.geo_location import LAYERS_KEY
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


async def test_e2e_48_the_state_of_a_pin_is_its_distance_from_home_in_the_unit_of_the_instance(env):
    """Home Assistant already converts to kilometres (or miles): the pin keeps that number and does not divide it again."""
    env.city.vehicles = [_row(number="1001", lat=52.2297, lon=21.0122)]
    await env.add_entry(api_key=DEFAULT_TOKEN, options={CONF_SHOW_VEHICLES: True})
    (pin,) = _vehicles(env)
    assert float(pin.state) == round(env.hass.config.distance(52.2297, 21.0122), 1)
    assert float(pin.state) > 10, "a place in Warsaw is far from the home of the test instance, not 0.0 from a division by 1000"


async def test_e2e_48_a_stop_whose_position_is_not_a_place_has_no_pin(env):
    entry = await env.add_entry(api_key=DEFAULT_TOKEN)
    assert len(_poles(env)) == 1
    coordinator = entry.runtime_data["coordinator"]
    coordinator.data.stop_info = {**coordinator.data.stop_info, "szer_geo": "nan"}
    coordinator.async_set_updated_data(coordinator.data)
    await env.settle()
    assert _poles(env) == []


async def test_e2e_48_stopping_the_vehicles_of_a_line_twice_does_no_harm(env):
    from custom_components.ztm_warsaw.geo_location import LineVehicles

    class _Feed:
        """A feed that holds no vehicle and remembers that it was left."""

        left = 0

        def subscribe(self, wanted, changed):
            """Follow, and say how to stop following."""
            return lambda: setattr(self, "left", self.left + 1)

        def vehicles_of(self, line):
            """No vehicle."""
            return []

    feed = _Feed()
    pins = LineVehicles(env.hass, "151", feed, lambda entities: None)  # type: ignore[arg-type]
    pins.start()
    pins.stop()
    pins.stop()
    assert feed.left == 1


async def test_e2e_48_a_vehicle_pin_says_where_it_heads_from_the_timetable_of_its_brigade(env):
    env.city.vehicles = []
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    departure = next(d for d in entry.runtime_data["coordinator"].data.departures if d.brygada)
    env.city.vehicles = [_row(line="151", brigade=departure.brygada, number="4711")]
    await env.advance(seconds=31)
    (pin,) = _vehicles(env)
    assert pin.attributes["Direction"] == departure.kierunek
    assert pin.attributes["friendly_name"] == f"Line 151 → {departure.kierunek}", "the place under the pin says where the vehicle goes"


async def test_e2e_48_a_vehicle_whose_brigade_has_no_departure_near_now_has_no_direction(env):
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="no-such-brigade", number="4712")]
    await env.advance(seconds=31)
    (pin,) = _vehicles(env)
    assert "Direction" not in pin.attributes
    assert pin.attributes["friendly_name"] == "Line 151 · 4712"
    assert entry is not None


async def test_e2e_48_the_pins_are_registered_entities_on_devices_so_they_show_on_the_integrations_page(env):
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="no-such-brigade", number="4711")]
    await env.advance(seconds=31)
    registry = env.entity_registry
    (pole_state,) = _poles(env)
    (vehicle_state,) = _vehicles(env)
    pole = registry.async_get(pole_state.entity_id)
    vehicle = registry.async_get(vehicle_state.entity_id)
    assert (pole.unique_id, vehicle.unique_id) == ("pole_7009_01", "vehicle_151_4711")
    assert (pole.config_entry_id, vehicle.config_entry_id) == (entry.entry_id, entry.entry_id)
    assert env.device_registry.async_get(pole.device_id).identifiers == {("ztm_warsaw", "pole_7009_01")}
    assert env.device_registry.async_get(vehicle.device_id).identifiers == {("ztm_warsaw", "vehicles_151")}


async def test_e2e_48_the_id_of_a_vehicle_does_not_carry_where_it_heads_because_the_timetable_changes(env):
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    departure = next(d for d in entry.runtime_data["coordinator"].data.departures if d.brygada)
    env.city.vehicles = [_row(line="151", brigade=departure.brygada, number="4711")]
    await env.advance(seconds=31)
    (pin,) = _vehicles(env)
    assert pin.entity_id == "geo_location.line_151_4711"
    assert pin.attributes["friendly_name"] == f"Line 151 → {departure.kierunek}"


async def test_e2e_48_a_vehicle_that_is_not_reported_any_more_leaves_the_registry_and_its_device_too(env):
    await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="no-such-brigade", number="4711")]
    await env.advance(seconds=31)
    assert env.entity_registry.async_get("geo_location.line_151_4711") is not None
    env.city.vehicles = []
    await env.advance(seconds=31)
    await env.settle()
    assert env.entity_registry.async_get("geo_location.line_151_4711") is None
    assert env.device_registry.async_get_device(identifiers={("ztm_warsaw", "vehicles_151")}) is None


async def test_e2e_48_registry_entries_of_vehicles_left_by_a_restart_are_taken_out_at_the_next_setup(env):
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True}, setup=False)
    env.entity_registry.async_get_or_create("geo_location", "ztm_warsaw", "vehicle_151_9999", config_entry=entry)
    await env.hass.config_entries.async_setup(entry.entry_id)
    await env.settle()
    assert [e for e in env.entity_registry.entities.values() if e.unique_id == "vehicle_151_9999"] == []


async def test_e2e_48_a_pole_that_changes_host_keeps_one_pin_and_its_unique_id(env):
    first = await env.add_entry(line="151", api_key=DEFAULT_TOKEN)
    second = await env.add_entry(line="523", api_key=DEFAULT_TOKEN)
    assert await env.hass.config_entries.async_unload(first.entry_id)
    await env.settle()
    (pole,) = _poles(env)
    assert pole.attributes["Lines"] == "523"
    entity = env.entity_registry.async_get(pole.entity_id)
    assert (entity.unique_id, entity.config_entry_id) == ("pole_7009_01", second.entry_id)


async def test_e2e_48_a_host_that_is_dropped_while_its_platform_is_still_loaded_leaves_no_second_pin_for_its_pole(env):
    first = await env.add_entry(line="151", api_key=DEFAULT_TOKEN)
    await env.add_entry(line="523", api_key=DEFAULT_TOKEN)
    env.hass.data[LAYERS_KEY].drop_entry(first.entry_id)  # what the unload does, with Home Assistant not taking the pin away itself
    await env.settle()
    (pole,) = _poles(env)
    assert pole.attributes["Lines"] == "523", "the pole is one pin again, hosted by the line that is left"
