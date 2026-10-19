"""E2E-31: the timetable as a calendar entity (every departure an event of one minute)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import WARSAW, stop_name_for

pytestmark = pytest.mark.e2e

CAL = "calendar.line_151_from_7009_01_timetable"


async def _add_entry(env, **kwargs):
    """An entry with its calendar enabled (it is off by default): the same registry write as enabling it in the UI,
    done up front to avoid the reload that follows the switch."""
    entry = await env.add_entry(setup=False, **kwargs)
    line = kwargs.get("line", "151")
    env.entity_registry.async_get_or_create(
        "calendar",
        DOMAIN,
        f"line_{line}_from_7009_01_calendar",
        config_entry=entry,
        disabled_by=None,
        suggested_object_id=f"line_{line.lower()}_from_7009_01_timetable",
    )
    await env.hass.config_entries.async_setup(entry.entry_id)
    await env.settle()
    return entry


async def _events(env, entity_id, start: str, end: str):
    """The events the calendar entity returns for the given Warsaw wall-clock range, through the real ``calendar.get_events`` service."""
    def moment(text: str) -> datetime:
        """A Warsaw wall-clock time from ISO text."""
        return datetime.fromisoformat(text).replace(tzinfo=WARSAW)

    answer = await env.hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": entity_id, "start_date_time": moment(start).isoformat(), "end_date_time": moment(end).isoformat()},
        blocking=True,
        return_response=True,
    )
    return answer[entity_id]["events"]


async def test_e2e_31_the_calendar_is_registered_next_to_the_sensor_on_the_same_device(env):
    entry = await _add_entry(env)
    registry = er.async_get(env.hass)
    entity = registry.async_get(CAL)
    assert entity is not None
    assert (entity.unique_id, entity.platform, entity.domain) == ("line_151_from_7009_01_calendar", DOMAIN, "calendar")
    assert entity.disabled_by is None
    sensor = registry.async_get("sensor.line_151_from_7009_01")
    assert entity.device_id == sensor.device_id, "one device per line: the calendar joins the sensor's device"
    assert len(dr.async_entries_for_config_entry(dr.async_get(env.hass), entry.entry_id)) == 1


async def test_e2e_31_the_next_departure_is_the_calendars_event(env):
    await _add_entry(env)  # Friday 12:00: the next departure of 151 is 12:04
    st = env.hass.states.get(CAL)
    assert st.state == "off", "no departure is happening this minute"
    assert st.attributes["message"].startswith("151")
    assert datetime.fromisoformat(st.attributes["start_time"]).astimezone(WARSAW).strftime("%H:%M") == "12:04"
    assert st.attributes["location"] == stop_name_for("7009")
    assert "friendly_name" in st.attributes


async def test_e2e_31_the_calendar_is_on_during_the_minute_of_a_departure(env):
    await _add_entry(env)
    await env.run_to("2026-10-16 12:04:20")
    assert env.hass.states.get(CAL).state == "on"
    await env.run_to("2026-10-16 12:05:10")
    st = env.hass.states.get(CAL)
    assert st.state == "off"
    assert datetime.fromisoformat(st.attributes["start_time"]).astimezone(WARSAW).strftime("%H:%M") == "12:24"


async def test_e2e_31_the_whole_day_is_in_the_calendar_past_departures_too(env):
    await _add_entry(env)
    events = await _events(env, CAL, "2026-10-16 00:00", "2026-10-17 00:00")
    starts = [datetime.fromisoformat(e["start"]).astimezone(WARSAW).strftime("%H:%M") for e in events]
    assert len(starts) == 81, "line 151 on that Friday has 81 departures"
    assert starts == sorted(starts)
    assert starts[0] == "04:41"
    assert starts[-1] == "23:11"
    first = events[0]
    assert (first["summary"].startswith("151"), first["location"]) == (True, stop_name_for("7009"))
    window = await _events(env, CAL, "2026-10-16 12:00", "2026-10-16 13:00")
    assert [datetime.fromisoformat(e["start"]).astimezone(WARSAW).strftime("%H:%M") for e in window] == ["12:04", "12:24", "12:44"]


@pytest.mark.start("2026-10-17 02:00")
async def test_e2e_31_the_night_tail_of_the_previous_day_stays_in_the_calendar_after_the_swap(env):
    """N25 of Friday runs to 04:54 on Saturday; at 03:30 the City serves Saturday, the tail is held from the answer before."""
    await _add_entry(env, line="N25")
    await env.run_to("2026-10-17 03:30")
    cal = "calendar.line_n25_from_7009_01_timetable"
    events = await _events(env, cal, "2026-10-17 03:30", "2026-10-17 05:30")
    starts = [datetime.fromisoformat(e["start"]).astimezone(WARSAW).strftime("%H:%M") for e in events]
    assert starts[:1] == ["03:54"]
    assert "04:54" in starts
    assert datetime.fromisoformat(env.hass.states.get(cal).attributes["start_time"]).astimezone(WARSAW).strftime("%H:%M") == "03:54"


async def test_e2e_31_after_the_last_departure_there_is_no_event_and_the_calendar_is_off(env):
    await _add_entry(env)
    await env.run_to("2026-10-16 23:30")  # the last departure of 151 was 23:11
    st = env.hass.states.get(CAL)
    assert st.state == "off"
    assert "message" not in st.attributes


async def test_e2e_31_the_calendar_is_unavailable_when_the_sensor_is(env):
    await _add_entry(env)
    env.city.valid_keys.clear()
    for _ in range(2):
        await env.hourly_tick()
    assert env.state().state == "unavailable"
    assert env.hass.states.get(CAL).state == "unavailable"
    # the held timetable must not start automations while the sensor refuses to vouch for it (a review finding)
    # (the service refuses an unavailable entity, so ask the entity as the calendar trigger does)
    entity = env.hass.data["entity_components"]["calendar"].get_entity(CAL)
    start = datetime.fromisoformat("2026-10-16 12:00").replace(tzinfo=WARSAW)
    assert await entity.async_get_events(env.hass, start, start + timedelta(hours=2)) == []
    assert entity.event is None


async def test_e2e_31_removing_the_entry_removes_the_calendar(env):
    entry = await _add_entry(env)
    await env.hass.config_entries.async_remove(entry.entry_id)
    await env.settle()
    assert env.hass.states.get(CAL) is None
    assert er.async_get(env.hass).async_get(CAL) is None


async def test_e2e_31_a_departure_that_the_api_repeats_is_one_event_and_another_direction_is_another(env):
    from custom_components.ztm_warsaw.models import ZTMDepartureDataReading

    entry = await _add_entry(env)
    coordinator = env.coordinator(entry)
    moment = coordinator.data.departures[0]
    twin = ZTMDepartureDataReading(kierunek=moment.kierunek, czas=moment.czas, brygada=moment.brygada, dt=moment.dt)
    other = ZTMDepartureDataReading(kierunek="ELSEWHERE", czas=moment.czas, brygada="9", dt=moment.dt)
    coordinator.data.departures.extend([twin, other])
    start = moment.dt.astimezone(WARSAW)
    events = await env.hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": CAL, "start_date_time": (start - timedelta(minutes=1)).isoformat(), "end_date_time": (start + timedelta(minutes=2)).isoformat()},
        blocking=True,
        return_response=True,
    )
    summaries = sorted(e["summary"] for e in events[CAL]["events"])
    assert len(summaries) == 2
    assert summaries[0] != summaries[1]


async def test_e2e_31_the_calendar_is_off_by_default_and_has_no_state_until_it_is_enabled(env):
    entry = await env.add_entry()
    entity = er.async_get(env.hass).async_get(CAL)
    assert entity is not None
    assert entity.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert env.hass.states.get(CAL) is None
    assert env.state().state not in ("unknown", "unavailable"), "the sensor is not affected"
    assert entry.state.value == "loaded"
