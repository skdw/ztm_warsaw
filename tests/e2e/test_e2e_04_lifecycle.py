"""E2E-22, E2E-23, E2E-25, E2E-26, E2E-27: entry lifecycle, API load with several entries, shared devices,
the diagnostic sensor and the stop-metadata download."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util.async_ import get_scheduled_timer_handles

from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import FULL_CATALOGUE, OVER_CAP_CATALOGUE, Http, ParamError, Respond, stop_name_for
from .helpers import find_devices, known_bug, owners_of

pytestmark = pytest.mark.e2e


def integration_timers(env) -> list[str]:
    """The timers this integration owns: the coordinator's hourly refresh and a sensor's departure wake-up."""
    out = []
    for handle in get_scheduled_timer_handles(env.hass.loop):
        text = repr(handle)
        if not handle.cancelled() and ("DataUpdateCoordinator" in text or "track point in time" in text):
            out.append(text[:80])
    return out


# ===================================================================== E2E-22
async def test_e2e_22_setup_owns_exactly_two_timers_and_unload_releases_both(env):
    assert integration_timers(env) == []
    entry = await env.add_entry()
    assert len(integration_timers(env)) == 2, integration_timers(env)  # hourly refresh + next-departure wake-up
    assert DOMAIN in env.hass.data

    assert await env.hass.config_entries.async_unload(entry.entry_id)
    await env.settle()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert integration_timers(env) == []
    assert DOMAIN not in env.hass.data, "no per-entry data left behind"
    st = env.hass.states.get("sensor.line_151_from_7009_01")
    assert st is not None
    assert st.state == "unavailable"
    assert st.attributes.get("restored") is True

    calls = env.city.count()
    await env.advance(hours=3)
    assert env.city.count() == calls, "an unloaded entry must not keep polling"


async def test_e2e_22_reloading_three_times_never_accumulates_timers_or_entities(env):
    entry = await env.add_entry()
    registry_before = {e.entity_id for e in er.async_entries_for_config_entry(env.entity_registry, entry.entry_id)}
    for round_no in range(1, 4):
        tt = env.city.count("timetable")
        assert await env.hass.config_entries.async_reload(entry.entry_id)
        await env.settle()
        assert entry.state is ConfigEntryState.LOADED
        assert env.city.count("timetable") == tt + 1, f"reload {round_no}: exactly one timetable fetch"
        assert len(integration_timers(env)) == 2, integration_timers(env)
        assert list(env.hass.data[DOMAIN]) == [entry.entry_id]
    registry_after = {e.entity_id for e in er.async_entries_for_config_entry(env.entity_registry, entry.entry_id)}
    assert registry_after == registry_before


async def test_e2e_22_removing_the_last_entry_cleans_registries(env):
    entry = await env.add_entry()
    assert find_devices(env.device_registry, {(DOMAIN, "line_151")})
    await env.hass.config_entries.async_remove(entry.entry_id)
    await env.settle()
    assert er.async_entries_for_config_entry(env.entity_registry, entry.entry_id) == []
    assert not find_devices(env.device_registry, {(DOMAIN, "line_151")})
    assert env.hass.states.get("sensor.line_151_from_7009_01") is None
    assert integration_timers(env) == []
    assert DOMAIN not in env.hass.data


async def test_e2e_22_two_loaded_entries_hold_two_timers_each_and_unloading_releases_them(env):
    first = await env.add_entry(line="151")
    second = await env.add_entry(line="N25")
    assert len(integration_timers(env)) == 4
    await env.hass.config_entries.async_unload(first.entry_id)
    await env.hass.config_entries.async_unload(second.entry_id)
    await env.settle()
    assert integration_timers(env) == []


# ===================================================================== E2E-23
FIVE_LINES = ["151", "143", "182", "525", "520"]  # five real lines at stop 7009/01


async def _five_entries(env):
    entries = [await env.add_entry(line=line, setup=False) for line in FIVE_LINES]
    await env.hass.config_entries.async_setup(entries[0].entry_id)
    await env.settle()
    return entries


@pytest.mark.city(catalogue_bytes=FULL_CATALOGUE)
async def test_e2e_23_five_entries_on_one_stop_all_load(env):
    entries = await _five_entries(env)
    assert [e.state for e in entries] == [ConfigEntryState.LOADED] * 5
    for line in FIVE_LINES:
        assert env.departure_local(line) is not None, line
        assert env.state(line).attributes["Stop, Name"] == stop_name_for("7009")
    assert env.city.count("timetable") == 5, "one timetable request per entry at startup"
    assert len(env.hass.states.async_all("sensor")) == 5  # the five diagnostic sensors are disabled by default


@pytest.mark.city(catalogue_bytes=FULL_CATALOGUE)
async def test_e2e_23_hourly_load_is_one_request_per_entry_and_never_the_catalogue(env):
    await _five_entries(env)
    stops_after_setup = env.city.count("stops")
    tt = env.city.count("timetable")
    await env.advance(hours=24, minutes=1)
    assert env.city.count("timetable") - tt == 5 * 24
    assert env.city.count("stops") == stops_after_setup


@pytest.mark.city(catalogue_bytes=FULL_CATALOGUE)
@known_bug("stops-catalogue-redownloaded", "the 1.6 MB stops catalogue is downloaded once PER ENTRY (and again on every reload)")
async def test_e2e_23_the_stop_catalogue_is_downloaded_once_for_five_entries_on_one_stop(env):
    entries = await _five_entries(env)
    assert [e.state for e in entries] == [ConfigEntryState.LOADED] * 5, "precondition: all five entries loaded"
    assert env.city.count("timetable") == 5
    assert env.city.count("stops") <= 1, (
        f"{env.city.count('stops')} downloads, {env.city.bytes_sent('stops') / 1e6:.1f} MB for one stop"
    )


# ===================================================================== E2E-25
async def test_e2e_25_removing_one_of_two_entries_that_share_a_device_keeps_the_other_working(env):
    a = await env.add_entry(line="151", stop_nr="01")
    b = await env.add_entry(line="151", stop_nr="02")  # same line, other pole: same device (ztm_warsaw, line_151)
    devices = find_devices(env.device_registry, {(DOMAIN, "line_151")})
    assert owners_of(devices) == {a.entry_id, b.entry_id}  # the layout is pinned by the next test

    await env.hass.config_entries.async_remove(a.entry_id)
    await env.settle()

    devices = find_devices(env.device_registry, {(DOMAIN, "line_151")})
    assert owners_of(devices) == {b.entry_id}, "the survivor keeps its device, the removed entry's is gone"
    assert env.hass.states.get("sensor.line_151_from_7009_01") is None
    assert env.departure_local("151", 7009, "02") is not None
    calls_b = len(env.city.matching("timetable", busstopNr="02"))
    calls_a = len(env.city.matching("timetable", busstopNr="01"))
    await env.advance(hours=2)
    assert len(env.city.matching("timetable", busstopNr="02")) > calls_b, "the survivor keeps refreshing"
    assert len(env.city.matching("timetable", busstopNr="01")) == calls_a, "the removed one stopped"

    await env.hass.config_entries.async_remove(b.entry_id)
    await env.settle()
    assert not find_devices(env.device_registry, {(DOMAIN, "line_151")})


@pytest.mark.xfail(
    strict=True,
    condition=hasattr(dr.DeviceRegistry, "async_get_devices"),  # Home Assistant 2026.10 and newer
    raises=AssertionError,
    reason="device-per-entry-on-ha-2026-10: a device belongs to one config entry there, so two entries of one "
    "line get two devices with the same identifiers instead of sharing the one device per line",
)
async def test_e2e_25_two_entries_of_one_line_share_one_device(env):
    """The frozen contract: one device per line. Broken by Home Assistant 2026.10, not yet by a fix of ours."""
    await env.add_entry(line="151", stop_nr="01")
    await env.add_entry(line="151", stop_nr="02")
    assert len(find_devices(env.device_registry, {(DOMAIN, "line_151")})) == 1


# ===================================================================== E2E-26
async def _entry_with_diagnostic_enabled(env, **kwargs):
    entry = await env.add_entry(setup=False, **kwargs)
    line = kwargs.get("line", "151")
    # Enabling it in the UI is the same registry write; doing it up front avoids the 30 s reload-after-enable delay.
    env.entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"line_{line}_from_7009_01_last_update",
        config_entry=entry,
        disabled_by=None,
        suggested_object_id=f"line_{line}_from_7009_01_last_update",
    )
    await env.hass.config_entries.async_setup(entry.entry_id)
    await env.settle()
    return entry


async def test_e2e_26_diagnostic_sensor_reports_the_last_successful_refresh(env):
    await _entry_with_diagnostic_enabled(env)
    st = env.state(diag=True)
    assert st.state == "2026-10-16T10:00:00+00:00"  # Fri 12:00 Warsaw
    assert dict(st.attributes) | {"friendly_name": None} == {
        "Last update successful": True,
        "Number of fetched departures": 81,
        "attribution": "Data provided by the City of Warsaw (api.um.warszawa.pl)",
        "device_class": "timestamp",
        "friendly_name": None,
    }
    await env.advance(hours=1, minutes=1)
    refreshed = datetime.fromisoformat(env.state(diag=True).state)
    assert (
        timedelta(0) <= refreshed - datetime(2026, 10, 16, 11, 0, tzinfo=UTC) < timedelta(seconds=3)
    )  # the 11:00 tick


async def test_e2e_26_diagnostic_sensor_does_not_advance_while_the_city_is_failing(env):
    await _entry_with_diagnostic_enabled(env)
    env.city.always("timetable", Http(500))
    await env.advance(hours=2, minutes=1)
    st = env.state(diag=True)
    assert st.state == "2026-10-16T10:00:00+00:00", "'Last update' is the last SUCCESS, not the last attempt"


async def test_e2e_26_diagnostic_sensor_counts_the_departures_of_the_current_service_day(env):
    env.move_to("2026-10-17 01:30")
    await _entry_with_diagnostic_enabled(env)
    assert env.state(diag=True).attributes["Number of fetched departures"] == 81  # Friday set, before 03:00
    await env.run_to("2026-10-17 03:45")
    assert env.state(diag=True).attributes["Number of fetched departures"] == 53  # Saturday set


async def test_e2e_26_diagnostic_sensor_is_unavailable_when_the_first_fetch_failed(env):
    env.city.always(None, Http(500))
    entry = await _entry_with_diagnostic_enabled(env)
    if entry.state is ConfigEntryState.LOADED:  # a fail-closed fix may refuse the entry instead (no entity at all)
        assert env.state(diag=True).state == "unavailable"
    else:
        assert entry.state is ConfigEntryState.SETUP_RETRY


# ===================================================================== E2E-27
@pytest.mark.city(catalogue_bytes=FULL_CATALOGUE)
async def test_e2e_27_stop_metadata_comes_from_the_full_size_catalogue(env):
    await env.add_entry()
    attrs = env.state().attributes
    assert attrs["Stop, Name"] == stop_name_for("7009")
    assert all(k in attrs for k in ("Stop, Street ID", "Stop, Latitude", "Stop, Longitude"))
    assert attrs["friendly_name"].startswith(f"Line 151 {stop_name_for('7009')}")
    assert env.state().entity_id == "sensor.line_151_from_7009_01", "the entity_id never picks up the stop name"
    assert 1.6e6 < env.city.bytes_sent("stops") < 2.0e6, "82% of the integration's 2 MB response cap"


@pytest.mark.city(catalogue_bytes=OVER_CAP_CATALOGUE)
@known_bug(
    "catalogue-over-two-megabyte-cap",
    "the 2 MB cap also applies to the whole stops catalogue: once it grows, every stop name vanishes",
)
async def test_e2e_27_stop_names_survive_a_catalogue_larger_than_two_megabytes(env):
    await env.add_entry()
    assert env.state().attributes["Stop, Name"] == stop_name_for("7009")


async def test_e2e_27_a_failing_catalogue_does_not_stop_departures(env):
    env.city.always("stops", Http(500))
    await env.add_entry()
    st = env.state()
    assert st.state not in ("unknown", "unavailable")
    assert st.attributes["Stop, Name"] == "Not available"
    # Home Assistant 2026.10 capitalises words of a name it builds ("From"); the older ones keep "from".
    assert st.attributes["friendly_name"].lower() == "line 151 from 7009/01"


@pytest.mark.start("2026-10-17 12:00")  # Saturday: line 411 does not run
async def test_e2e_27_no_service_without_a_stop_record_says_not_available_for_every_stop_attribute(env):
    env.city.always("stops", Http(500))
    await env.add_entry(line="411")
    attrs = env.state("411").attributes
    for name in ("Name", "Street ID", "Latitude", "Longitude", "Direction", "Effective From"):
        assert attrs[f"Stop, {name}"] == "Not available", name


async def test_e2e_27_malformed_catalogue_rows_are_skipped_not_fatal(env):
    good = {"values": [{"key": "zespol", "value": "7009"}, {"key": "slupek", "value": "01"}, {"key": "nazwa_zespolu", "value": "Dobry"}]}
    env.city.always("stops", Respond(200, {"result": [{"values": 5}, "junk", {"values": None}, {"values": ["x"]}, good]}))
    await env.add_entry()
    st = env.state()
    assert st.state not in ("unknown", "unavailable")
    assert st.attributes["Stop, Name"] == "Dobry"


async def test_e2e_27_a_text_answer_for_the_catalogue_is_retried_once_shortly_after(env):
    env.city.script("stops", ParamError())  # transient backend state, then normal
    await env.add_entry()
    assert env.sleeps.requested == [0.8]
    assert env.state().attributes["Stop, Name"] == stop_name_for("7009")
    assert env.city.count("stops") == 2
