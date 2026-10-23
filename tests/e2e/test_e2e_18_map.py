"""E2E-48: the map. One pin for every stop pole and one for every vehicle of the lines that show theirs; nothing is drawn twice."""

from __future__ import annotations

import base64
from unittest.mock import patch
from datetime import timedelta

import pytest
from homeassistant.helpers import device_registry as dr
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

        def details_of(self, line, number):
            """Nothing is known about a vehicle."""
            return {}

        def has_polled(self, line):
            """No poll has worked."""
            return False

        async def ensure_fleet(self):
            """The fleet is not read."""
            return False

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


async def test_e2e_48_a_vehicle_pin_is_a_registered_entity_on_a_device_of_its_line_and_a_pole_pin_is_not(env):
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="no-such-brigade", number="4711")]
    await env.advance(seconds=31)
    (pole_state,) = _poles(env)
    (vehicle_state,) = _vehicles(env)
    assert env.entity_registry.async_get(pole_state.entity_id) is None, "a pole is shared by lines: it has no registry entry"
    vehicle = env.entity_registry.async_get(vehicle_state.entity_id)
    assert (vehicle.unique_id, vehicle.config_entry_id) == ("vehicle_151_4711", entry.entry_id)
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
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="no-such-brigade", number="4711")]
    await env.advance(seconds=31)
    assert env.entity_registry.async_get("geo_location.line_151_4711") is not None
    env.city.vehicles = []
    await env.advance(seconds=31)
    await env.settle()
    assert env.entity_registry.async_get("geo_location.line_151_4711") is None
    assert not [d for d in dr.async_entries_for_config_entry(env.device_registry, entry.entry_id) if ("ztm_warsaw", "vehicles_151") in d.identifiers]


async def test_e2e_48_after_a_restart_the_entries_of_vehicles_the_city_no_longer_reports_go_and_those_still_reported_keep_their_settings(env):
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True}, setup=False)
    registry = env.entity_registry
    gone = registry.async_get_or_create("geo_location", "ztm_warsaw", "vehicle_151_9999", config_entry=entry, suggested_object_id="line_151_9999")
    kept = registry.async_get_or_create("geo_location", "ztm_warsaw", "vehicle_151_4711", config_entry=entry, suggested_object_id="line_151_4711")
    registry.async_update_entity(kept.entity_id, name="My bus")
    env.city.vehicles = [_row(line="151", brigade="x", number="4711")]
    await env.hass.config_entries.async_setup(entry.entry_id)
    await env.settle()
    await env.advance(seconds=31)
    assert registry.async_get(gone.entity_id) is None
    assert registry.async_get(kept.entity_id).name == "My bus", "the vehicle is still there: its settings are as they were"
    (pin,) = _vehicles(env)
    assert pin.entity_id == kept.entity_id


async def test_e2e_48_switching_the_vehicles_off_takes_their_entries_and_their_device_out_of_the_registry(env):
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="x", number="4711")]
    await env.advance(seconds=31)
    assert dr.async_entries_for_config_entry(env.device_registry, entry.entry_id)
    env.hass.config_entries.async_update_entry(entry, options={"show_vehicles": False})
    await env.settle()
    assert env.entity_registry.async_get("geo_location.line_151_4711") is None
    assert not [d for d in dr.async_entries_for_config_entry(env.device_registry, entry.entry_id) if ("ztm_warsaw", "vehicles_151") in d.identifiers]


async def test_e2e_48_a_vehicle_still_running_yesterdays_late_departure_has_its_destination_from_the_previous_answer(env):
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    coordinator = entry.runtime_data["coordinator"]
    reading = next(d for d in coordinator.data.departures if d.brygada)
    late = type(reading)(kierunek="Nocna Pętla", czas=reading.czas, trasa="TX-N", brygada="77", dt=dt_util.utcnow())
    with patch.object(type(coordinator), "known", lambda self: [late, *[d for d in self.data.departures if d.dt]]):
        env.city.vehicles = [_row(line="151", brigade="77", number="4712")]
        await env.advance(seconds=31)
        (pin,) = _vehicles(env)
    assert pin.attributes["Direction"] == "Nocna Pętla"



def _record(number="4711", **more):
    """A record of the City's fleet as the City sends it."""
    return {"numerTaborowy": number, "nazwaOperatora": "Miejskie Zakłady Autobusowe", "nazwaZajezdni": "Woronicza", "numerRejestracyjny": "WZ 1234A",
            "rokProdukcji": 2019, "trakcja": "Bus", "kolorPojazdu": "RAL 1003", **more}


async def test_e2e_48_a_vehicle_pin_has_what_the_fleet_and_the_timetable_say_about_the_vehicle(env):
    env.city.fleet = [_record("4711", idMarki=7)]
    env.city.fleet_models = [{"idMarki": 7, "marka": "Solaris", "typ": "Urbino 12", "katWielkosci": "MAXI (12m)", "rodzajZasilania": "Spalinowy", "klimatyzacja": True,
                              "podloga": "LF", "liczMiejscSiedzacychTab": 30, "liczMiejscStojacychTab": 74, "liczMiejscTab": 104, "zasilanie": "ON"}]
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    brigade = next(d.brygada for d in entry.runtime_data["coordinator"].data.departures if d.brygada)
    departure = min((d for d in entry.runtime_data["coordinator"].data.departures if d.brygada == brigade), key=lambda d: abs(d.dt - dt_util.utcnow()))
    env.city.vehicles = [_row(line="151", brigade=brigade, number="4711")]
    await env.advance(seconds=31)
    (pin,) = _vehicles(env)
    attrs = pin.attributes
    assert (attrs["Operator"], attrs["Depot"], attrs["Registration"], attrs["Year of production"], attrs["Vehicle type"]) == (
        "Miejskie Zakłady Autobusowe", "Woronicza", "WZ 1234A", 2019, "Bus")
    assert (attrs["Make"], attrs["Model"], attrs["Size class"], attrs["Powertrain"], attrs["Air conditioning"]) == ("Solaris", "Urbino 12", "MAXI (12m)", "Spalinowy", True)
    assert (attrs["Floor"], attrs["Seats"], attrs["Standing places"], attrs["Capacity"]) == ("Low floor", 30, 74, 104)
    assert "kolorPojazdu" not in attrs, "only the facts that are shown"
    assert "zasilanie" not in attrs, "only the facts that are shown"
    assert attrs["Route"] == departure.trasa
    assert attrs["Scheduled at"] == f"{stop_name_for('7009')} 01"
    assert attrs["Scheduled departure"].startswith(str(dt_util.as_local(departure.dt).date()))


async def test_e2e_48_the_fleet_is_read_once_and_a_failing_fleet_does_not_touch_the_pins(env):
    env.city.fleet = []  # the City answers with no vehicles: nothing to show
    await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="x", number="4711")]
    await env.advance(seconds=31)
    await env.advance(seconds=31)
    (pin,) = _vehicles(env)
    assert "Operator" not in pin.attributes
    assert env.city.count("fleet") == 1, "asked once, then not again for an hour"


async def test_e2e_48_the_speed_and_the_course_are_worked_out_from_the_last_two_positions_and_not_from_noise(env):
    await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="x", number="4711", lat=52.2000, lon=21.0000, seconds_ago=40)]
    await env.advance(seconds=31)
    (pin,) = _vehicles(env)
    assert "Speed, km/h" not in pin.attributes, "one position says nothing about speed"
    env.city.vehicles = [_row(line="151", brigade="x", number="4711", lat=52.2030, lon=21.0000, seconds_ago=10)]  # about 330 m north in the 61 s between the two reports
    await env.advance(seconds=31)
    (pin,) = _vehicles(env)
    assert pin.attributes["Course, degrees"] == 0
    assert 18 <= pin.attributes["Speed, km/h"] <= 22
    env.city.vehicles = [_row(line="151", brigade="x", number="4711", lat=52.2030, lon=21.00001, seconds_ago=5)]  # a metre: noise
    await env.advance(seconds=31)
    (pin,) = _vehicles(env)
    assert pin.attributes["Course, degrees"] == 0, "a vehicle that has hardly moved keeps its course"


async def test_e2e_48_a_jump_of_the_position_is_not_a_speed(env):
    await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="x", number="4711", lat=52.2000, lon=21.0000, seconds_ago=40)]
    await env.advance(seconds=31)
    env.city.vehicles = [_row(line="151", brigade="x", number="4711", lat=52.3000, lon=21.0000, seconds_ago=10)]  # 11 km in 30 s
    await env.advance(seconds=31)
    (pin,) = _vehicles(env)
    assert "Speed, km/h" not in pin.attributes


async def test_e2e_48_the_fleet_is_asked_again_every_hour_and_read_again_after_a_day_or_after_a_failure(env):
    env.city.fleet = []  # the first read finds nothing
    await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="x", number="4711")]
    await env.advance(seconds=31)
    assert env.city.count("fleet") == 1
    env.city.fleet = [_record("4711")]
    await env.advance(seconds=3500)
    env.city.vehicles = [_row(line="151", brigade="x", number="4711")]  # the vehicle is still reported (a position is only good for a few minutes)
    await env.advance(seconds=130)  # an hour after the failed read it is asked again
    (pin,) = _vehicles(env)
    assert env.city.count("fleet") == 2
    assert pin.attributes["Operator"] == "Miejskie Zakłady Autobusowe"


async def test_e2e_48_a_line_that_reloads_while_another_keeps_the_feed_is_not_reconciled_against_the_other_lines_poll(env):
    from custom_components.ztm_warsaw.geo_location import LAYERS_KEY  # noqa: F401 - the module is imported for its side effects only

    a = await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    await env.add_entry(line="523", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="x", number="4711"), _row(line="523", brigade="y", number="5000")]
    await env.advance(seconds=31)
    pin = env.entity_registry.async_get("geo_location.line_151_4711")
    env.entity_registry.async_update_entity(pin.entity_id, name="My bus")
    assert await env.hass.config_entries.async_unload(a.entry_id)
    await env.advance(seconds=31)  # a poll with only the other line wanted
    assert await env.hass.config_entries.async_setup(a.entry_id)
    await env.settle()
    assert env.entity_registry.async_get("geo_location.line_151_4711").name == "My bus", "nothing is deleted before the line has been polled again"


async def test_e2e_48_a_failed_daily_refresh_of_the_fleet_is_retried_after_an_hour_and_keeps_what_was_read(env):
    env.city.fleet = [_record("4711")]
    await env.add_entry(line="151", api_key=DEFAULT_TOKEN, options={"show_vehicles": True})
    env.city.vehicles = [_row(line="151", brigade="x", number="4711")]
    await env.advance(seconds=31)
    assert env.city.count("fleet") == 1
    env.city.fleet = []  # the City stops answering with vehicles
    for _ in range(7):  # a day and a bit, the positions kept fresh
        await env.advance(seconds=3600 * 4)
        env.city.vehicles = [_row(line="151", brigade="x", number="4711")]
        await env.advance(seconds=31)
    failed_at = env.city.count("fleet")
    assert failed_at >= 2, "the daily refresh was tried"
    env.city.fleet = [_record("4711", nazwaZajezdni="Redutowa")]
    await env.advance(seconds=3500)
    env.city.vehicles = [_row(line="151", brigade="x", number="4711")]
    await env.advance(seconds=130)
    (pin,) = _vehicles(env)
    assert pin.attributes["Depot"] == "Redutowa", "an hour after the failed refresh it was asked again, not a day after"


async def test_e2e_48_a_bus_and_a_tram_with_the_same_number_get_the_facts_of_their_own_kind(env):
    from custom_components.ztm_warsaw.client import ZTMStopClient
    from custom_components.ztm_warsaw.vehicles import VehicleFeed

    env.city.fleet = [_record("1001", idMarki=1, trakcja="Bus")]
    entry = await env.add_entry(line="151", api_key=DEFAULT_TOKEN)
    client: ZTMStopClient = entry.runtime_data["client"]

    async def tram_too(self):
        """The City's fleet, with a tram that has the number of a bus."""
        return {"1/1001": {"Vehicle type": "Bus"}, "2/1001": {"Vehicle type": "Tram"}}

    with patch.object(ZTMStopClient, "get_fleet", tram_too):
        feed = VehicleFeed(env.hass, client)
        await feed.ensure_fleet()
    assert feed.details_of("161", "1001") == {"Vehicle type": "Bus"}
    assert feed.details_of("28", "1001") == {"Vehicle type": "Tram"}
