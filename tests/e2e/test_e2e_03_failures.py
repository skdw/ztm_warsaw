"""E2E-14 .. E2E-21: what happens when the city misbehaves. Wrong keys, junk payloads, outages, slow servers,
connection resets, and what ends up in the logs.

Common setup: a restored 1.1.4 entry (line 151, stop 7009/01) on Friday noon, already loaded with a good
timetable ("warm cache"), unless a test says it starts cold.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ztm_warsaw.client import ZTMStopClient
from custom_components.ztm_warsaw.models import ZTMDepartureData

from .fake_city import (
    DEFAULT_KEY,
    DEFAULT_TOKEN,
    BadKey,
    EmptyList,
    Hang,
    Html,
    Http,
    InvalidJson,
    Mutate,
    NullResult,
    Oversize,
    ParamError,
    RedirectOnce,
    RedirectSelf,
    Reset,
    Respond,
    Truncated,
    drop_czas_from_first_row,
)
from .helpers import log_blob

pytestmark = pytest.mark.e2e

OK_STATES = ("unknown", "unavailable")


def departing(env, line="151") -> bool:
    """The sensor shows a concrete departure (not unknown, not unavailable)."""
    return env.state(line).state not in OK_STATES


def shows_a_future_departure(env, line="151") -> bool:
    """The sensor shows a departure that is not in the past."""
    shown = env.departure_local(line)
    return shown is not None and shown >= env.now.strftime("%Y-%m-%d %H:%M")


def coordinator_of(env):
    """The coordinator of the first config entry of the integration."""
    return env.coordinator(env.hass.config_entries.async_entries("ztm_warsaw")[0])


# ===================================================================== E2E-14
async def test_e2e_14_a_key_revoked_while_running_is_not_reported_as_no_service(env):
    await env.add_entry()
    assert departing(env)
    env.city.valid_keys.clear()  # the city stops accepting the key
    await env.hourly_tick()
    assert env.state().state == "unavailable"


async def test_e2e_14_a_rejected_key_is_visible_in_the_log(env, caplog):
    caplog.set_level(logging.DEBUG)
    await env.add_entry()
    env.city.valid_keys.clear()
    caplog.clear()
    await env.hourly_tick()
    loud = [r for r in caplog.records if r.levelno >= logging.WARNING and r.name.startswith("custom_components")]
    assert loud, "a rejected API key must leave a WARNING or ERROR the user can find"


async def test_e2e_14_the_rejected_key_never_reaches_the_log(env, caplog):
    caplog.set_level(logging.DEBUG)
    await env.add_entry()
    env.city.valid_keys.clear()
    await env.hourly_tick()
    assert DEFAULT_KEY not in log_blob(caplog)


async def test_e2e_14_a_network_error_after_an_api_error_does_not_bring_the_stale_timetable_back(env):
    await env.add_entry()
    assert departing(env)
    env.city.valid_keys.clear()
    await env.hourly_tick()
    assert env.state().state == "unavailable"
    env.city.always("timetable", Http(500))  # now the city is also failing, with the old timetable still cached
    await env.hourly_tick()
    assert env.state().state == "unavailable"
    env.city.heal()
    env.city.valid_keys.add(DEFAULT_KEY)
    await env.hourly_tick()
    assert departing(env)


async def test_e2e_14_a_stop_the_api_stops_knowing_is_unavailable_and_recovers(env):
    await env.add_entry()
    assert departing(env)
    env.city.always("timetable", ParamError())
    await env.hourly_tick()
    assert env.state().state == "unavailable"
    env.city.heal()
    await env.hourly_tick()
    assert departing(env)


async def test_e2e_14_a_key_the_city_never_accepted_is_unavailable_from_the_start(env):
    entry = await env.add_entry(api_key="never-valid")
    if entry.state is ConfigEntryState.LOADED:
        assert env.state().state == "unavailable"
    else:  # a fix may also refuse the entry (retry or auth failure); it must not load as an empty success
        assert entry.state in (ConfigEntryState.SETUP_RETRY, ConfigEntryState.SETUP_ERROR)


async def test_e2e_14_a_coordinator_failure_with_cached_data_is_visible_in_the_state_machine(env):
    """White-box fault injection: 1.1.4 never raises with a warm cache, but a fail-closed fix will, and
    without a matching entity change the entity would keep its old state while ``coordinator.last_update_success`` is False."""
    entry = await env.add_entry()
    assert entry.state is ConfigEntryState.LOADED, "precondition: a loaded entry with a warm cache"
    assert departing(env), "precondition: a loaded entry with a warm cache"
    coord = coordinator_of(env)
    with patch.object(ZTMStopClient, "get", AsyncMock(side_effect=UpdateFailed("forced by the test"))):
        await coord.async_refresh()
        await env.settle()
    assert coord.last_update_success is False
    assert coord.data is not None, "the cached timetable is still there"
    assert env.state().state == "unavailable"


async def test_e2e_14_a_rejected_key_does_not_crash_or_unload_the_entry(env):
    entry = await env.add_entry()
    env.city.valid_keys.clear()
    before = env.city.count("timetable")
    await env.hourly_tick()
    assert entry.state is ConfigEntryState.LOADED
    assert env.city.count("timetable") == before + 1, "it keeps polling at the normal pace"
    env.city.valid_keys.add(DEFAULT_KEY)
    await env.hourly_tick()
    assert departing(env), "and recovers by itself once the key works again"


# ===================================================================== E2E-15
# (behavior factory, what the entity must look like, finding if the 1.1.4 behavior differs)
COLD_START = [
    pytest.param(NullResult, "no_service", id="result_null__line_not_running_today"),
    pytest.param(EmptyList, "no_service", id="result_empty_list"),
    pytest.param(
        ParamError,
        "unavailable",
        id="result_text__bad_parameters",
    ),
    pytest.param(
        lambda: Respond(200, {"unexpected": "shape"}, name="unknown_shape"),
        "unavailable",
        id="unknown_shape",
    ),
    pytest.param(lambda: Respond(200, [], name="bare_list"), "unavailable", id="bare_list_is_not_the_legacy_shape"),
    pytest.param(lambda: Respond(200, {"result": 5}, name="odd_result"), "unavailable", id="result_of_an_odd_type"),
    pytest.param(
        lambda: Respond(200, {"result": "false", "error": "something else"}, name="false_other"),
        "unavailable",
        id="result_false_without_apikey",
    ),
    pytest.param(lambda: Respond(200, {"result": [[{"key": "czas", "value": "garbage"}]]}, name="junk"), "unavailable", id="rows_without_one_reading"),
    pytest.param(lambda: Http(500), "unavailable", id="http_500"),
    pytest.param(lambda: Http(403, {"message": "Forbidden"}), "unavailable", id="http_403"),
    pytest.param(lambda: Http(404, {"message": "Not found"}), "unavailable", id="http_404"),
    pytest.param(InvalidJson, "unavailable", id="invalid_json"),
    pytest.param(Html, "unavailable", id="html_page"),
    pytest.param(Oversize, "unavailable", id="over_2mb"),
    pytest.param(Truncated, "unavailable", id="truncated_body"),
    pytest.param(Reset, "unavailable", id="connection_reset"),
]


@pytest.mark.parametrize(("make", "expected"), COLD_START)
async def test_e2e_15_first_refresh_classifies_what_the_city_answered(env, make, expected):
    env.city.always("timetable", make())
    entry = await env.add_entry()
    if entry.state is ConfigEntryState.SETUP_RETRY:  # a fail-closed fix may refuse the first refresh
        assert expected == "unavailable", "a line without service must still load"
        return
    assert entry.state is ConfigEntryState.LOADED
    st = env.state()
    if expected == "no_service":
        assert st.state == "unknown", "the line simply has no departures: available, no timestamp"
        assert st.attributes["Upcoming, Headsign"] == "No service"
    else:
        assert st.state == "unavailable", "an error must not be shown as a normal 'No service'"


async def test_e2e_15_http_5xx_is_retried_once_after_the_documented_backoff(env):
    env.city.always("timetable", Http(503))
    await env.add_entry()
    assert env.city.count("timetable") == 2
    assert env.sleeps.requested == [1.5]


async def test_e2e_15_http_4xx_is_not_retried(env):
    env.city.always("timetable", Http(403, {"message": "Forbidden"}))
    await env.add_entry()
    assert env.city.count("timetable") == 1
    assert env.sleeps.requested == []


@pytest.mark.parametrize("make", [NullResult, EmptyList])
async def test_e2e_15_a_line_that_stops_running_today_becomes_no_service_and_stays_available(env, make):
    """Friday -> a line that the city answers with null/[] on a given day: must NOT be an error state."""
    await env.add_entry()
    env.city.always("timetable", make())
    await env.hourly_tick()
    st = env.state()
    assert st.state == "unknown"
    assert st.attributes["Upcoming, Headsign"] == "No service"


@pytest.mark.start("2026-10-16 23:40")
async def test_e2e_15_line_411_stops_running_when_the_service_day_flips_to_saturday(env):
    """Captured: 411 runs on Friday (34 departures, 06:52..18:40) and answers {"result": null} on Saturday."""
    await env.add_entry(line="411")
    await env.run_to("2026-10-17 02:50")
    assert env.departure_local("411") is None, "Friday's 06:52 is Friday's: nothing is announced before the flip"
    await env.run_to("2026-10-17 03:45")  # the 03:02 refresh gets null
    st = env.state("411")
    assert st.state == "unknown", "an available entity without a departure, not an error"
    assert st.attributes["Upcoming, Headsign"] == "No service"
    assert [c.behavior for c in env.city.matching("timetable")][-1] == "ok"  # the fake answered null by day logic
    assert coordinator_of(env).last_update_success is True


# ===================================================================== E2E-16
async def test_e2e_16_one_connection_reset_is_invisible_to_the_user(env):
    await env.add_entry()
    coord = coordinator_of(env)
    first_success = coord.last_update_success_time
    env.city.script("timetable", Reset())  # only the next request is reset, the retry succeeds
    await env.hourly_tick()
    assert coord.last_update_success is True
    assert coord.last_update_success_time > first_success, "the retry got through: a fresh timetable was stored"
    assert shows_a_future_departure(env)


async def test_e2e_16_a_five_minute_outage_spanning_a_refresh_keeps_the_cached_schedule(env, caplog):
    """The real incident: ConnectionResetError for ~5 minutes at 04:35, fine again at 04:40."""
    caplog.set_level(logging.INFO)
    await env.add_entry()
    coord = coordinator_of(env)
    cached = coord.data
    stamp = coord.last_update_success_time
    env.city.always(None, Reset())
    await env.hourly_tick()
    assert coord.data is cached, "the last good timetable is what is served during the outage"
    assert coord.last_update_success_time == stamp
    assert shows_a_future_departure(env), "stale-but-available is the intended short-outage behavior"
    assert any(r.levelno >= logging.WARNING and "old API" in r.getMessage() for r in caplog.records), "and it says so (an old key: the City's old API)"

    env.city.heal()  # five minutes later the city is back; the next refresh is the next hourly tick
    await env.hourly_tick()
    assert coord.data is not cached
    assert coord.last_update_success_time > stamp
    assert shows_a_future_departure(env)


# ===================================================================== E2E-17
async def test_e2e_17_a_short_outage_serves_the_cached_schedule_and_stays_available(env):
    await env.add_entry()
    env.city.always("timetable", Http(500))
    await env.run_to("2026-10-16 15:05")  # three failed hourly refreshes
    assert env.state().state != "unavailable"
    assert shows_a_future_departure(env)
    assert env.departure_local()[:10] == "2026-10-16"


async def test_e2e_17_after_days_of_outage_an_old_schedule_is_not_presented_as_live(env):
    await env.add_entry()
    env.city.always("timetable", Http(500))
    await env.run_to("2026-10-19 12:05")  # Monday noon, 72 failed hourly refreshes later
    st = env.state()
    no_longer_trusted = st.state == "unavailable" or (
        st.state == "unknown" and st.attributes["Upcoming, Headsign"] == "No service"
    )
    assert no_longer_trusted, f"still announcing {st.state} from a 3-day-old timetable"


# ===================================================================== E2E-18
async def test_e2e_18_a_hanging_server_costs_two_timeouts_then_the_cache_is_kept(env):
    await env.add_entry()
    env.city.always("timetable", Hang())
    before = env.city.count("timetable")
    await env.hourly_tick(hanging=True)
    assert env.city.count("timetable") - before == 2, "one attempt + one retry"
    assert env.sleeps.requested == [1.5]
    assert env.state().state != "unavailable"
    assert shows_a_future_departure(env)


async def test_e2e_18_setup_against_a_hanging_server_does_not_block_for_over_a_minute(env):
    env.city.always(None, Hang())
    task = asyncio.ensure_future(env.add_entry())
    entry = await env.drive_timeouts(task)
    blocked = 20 * env.city.hung_total() + sum(env.sleeps.requested)
    assert entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY)
    assert blocked <= 60, f"setup was blocked for about {blocked:.0f} s"


# ===================================================================== E2E-19
GARBAGE = [
    pytest.param(InvalidJson, id="invalid_json"),
    pytest.param(Html, id="html_page"),
    pytest.param(Oversize, id="over_2mb"),
    pytest.param(Truncated, id="truncated_body"),
]


@pytest.mark.parametrize("make", GARBAGE)
async def test_e2e_19_garbage_does_not_poison_the_cache(env, make):
    await env.add_entry()
    coord = coordinator_of(env)
    cached = coord.data
    env.city.always("timetable", make())
    await env.hourly_tick()
    assert coord.data is cached, "the last good timetable survives one bad answer"
    assert shows_a_future_departure(env)
    env.city.heal()
    await env.hourly_tick()
    assert coord.data is not cached, "and the next good answer replaces it"
    assert shows_a_future_departure(env)


async def test_e2e_19_a_row_without_a_departure_time_is_ignored(env):
    env.move_to("2026-10-16 23:40")
    env.city.always("timetable", Mutate(drop_czas_from_first_row, "row_without_czas"))
    await env.add_entry()
    # 151's last real departure is 23:11, so at 23:50 there must be NOTHING; the phantom 00:00 shows up instead
    await env.run_to("2026-10-16 23:50")
    assert env.departure_local() is None, f"phantom departure announced: {env.departure_local()}"


async def test_e2e_19_a_row_with_an_unparseable_time_is_skipped_not_fatal(env):
    def garble(payload):
        """Make the 'czas' value of the first row unparseable."""
        row = payload["result"][0]
        for item in row:
            if item["key"] == "czas":
                item["value"] = "soon"
        return payload

    env.city.always("timetable", Mutate(garble, "unparseable_czas"))
    entry = await env.add_entry()
    assert entry.state is ConfigEntryState.LOADED
    assert departing(env), "the other 80 rows still work"


async def test_e2e_19_a_redirect_on_a_credentialed_request_is_not_followed(env):
    env.city.script("timetable", RedirectOnce())
    entry = await env.add_entry()
    assert env.city.count("timetable") == 1, "the integration must not chase the redirect"
    assert entry.state is ConfigEntryState.SETUP_RETRY, "visible as a setup that is retried, with no sensor"


# ===================================================================== E2E-20
KEY = "deadbeef-0000-4000-8000-feedfacecafe"  # gitleaks:allow  (synthetic; distinctive so any leak is unmistakable)

LOG_MODES = [
    pytest.param(lambda c: c.always(None, Reset()), id="connection_reset"),
    pytest.param(lambda c: c.always(None, Http(500)), id="http_500"),
    pytest.param(lambda c: c.always(None, Http(403, {"message": "Forbidden"})), id="http_403"),
    pytest.param(lambda c: c.always(None, InvalidJson()), id="invalid_json"),
    pytest.param(lambda c: c.always(None, Html()), id="html_page"),
    pytest.param(lambda c: c.always(None, Oversize()), id="over_2mb"),
    pytest.param(lambda c: c.always(None, Truncated()), id="truncated_body"),
    pytest.param(lambda c: c.always(None, BadKey()), id="bad_key"),
    pytest.param(lambda c: c.always(None, ParamError()), id="param_error"),
    pytest.param(
        lambda c: c.always(None, RedirectSelf()),
        id="redirect_loop",
    ),
]


def _guard_is_live(env, caplog) -> None:
    """Positive control: the scenario really ran (a request reached the fake city) and the integration's own
    records reach caplog; otherwise 'nothing leaked' would be true of an empty log."""
    assert env.city.calls, "no request reached the fake city: the scenario did not run"
    assert any(r.name.startswith("custom_components") for r in caplog.records), (
        "the integration logged nothing that caplog can see: the leak scan would pass vacuously"
    )


def _scan(caplog) -> str:
    """The lines of the log that contain a piece of the API key, as text for the assertion message; an empty string when nothing leaked."""
    blob = log_blob(caplog)
    leaked = [frag for frag in (KEY, KEY[:8], KEY[-12:]) if frag in blob]
    return (
        f"leaked {leaked} in:\n" + "\n".join(line for line in blob.splitlines() if any(f in line for f in leaked))
        if leaked
        else ""
    )


@pytest.mark.parametrize("arrange", LOG_MODES)
async def test_e2e_20_runtime_logs_never_contain_the_api_key(env, caplog, arrange):
    caplog.set_level(logging.DEBUG)
    env.city.valid_keys.add(KEY)
    await env.add_entry(api_key=KEY)  # healthy start
    arrange(env.city)
    await env.hourly_tick()  # failing refresh (warm cache)
    entry = env.hass.config_entries.async_entries("ztm_warsaw")[0]
    await env.hass.config_entries.async_reload(entry.entry_id)  # cold start against the failing city: stops + timetable
    await env.settle()
    _guard_is_live(env, caplog)
    assert not _scan(caplog), _scan(caplog)


@pytest.mark.parametrize("arrange", LOG_MODES)
async def test_e2e_20_config_flow_logs_never_contain_the_api_key(env, caplog, arrange):
    caplog.set_level(logging.DEBUG)
    env.city.valid_keys.add(KEY)
    arrange(env.city)
    await env.submit_flow(api_key=KEY)
    _guard_is_live(env, caplog)
    assert not _scan(caplog), _scan(caplog)


async def test_e2e_20_server_down_does_not_leak_either(env, caplog):
    caplog.set_level(logging.DEBUG)
    env.city.valid_keys.add(KEY)
    await env.add_entry(api_key=KEY)
    await env.city.take_offline()
    await env.hourly_tick()
    await env.submit_flow(api_key=KEY)
    _guard_is_live(env, caplog)
    assert not _scan(caplog), _scan(caplog)


def test_e2e_20_the_scanner_would_notice_a_leak(caplog):
    """Guard for the guard: a log line containing the key (or its first 8 chars) is detected, on a logger
    under the integration's own name (the records the real scans depend on)."""
    log = logging.getLogger("custom_components.ztm_warsaw.client")
    log.error("GET https://x/?apikey=%s failed", KEY)
    assert KEY in _scan(caplog)
    assert any(r.name.startswith("custom_components") for r in caplog.records)
    caplog.clear()
    log.error("key starts with %s...", KEY[:8])
    assert KEY[:8] in _scan(caplog)


# ===================================================================== E2E-21
async def test_e2e_21_a_failed_first_refresh_leaves_unavailable_entities_not_a_crash(env):
    env.city.always(None, Http(500))
    entry = await env.add_entry()
    assert entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY)
    if entry.state is ConfigEntryState.LOADED:
        assert env.state().state == "unavailable"


async def test_e2e_21_it_recovers_on_its_own_at_the_latest_at_the_next_hourly_refresh(env):
    env.city.always(None, Http(500))
    await env.add_entry()
    env.city.heal()
    await env.hourly_tick()
    assert departing(env)


async def test_e2e_21_it_recovers_within_ten_minutes_of_the_city_coming_back(env):
    env.city.always(None, Http(500))
    await env.add_entry()  # HA boots, the network is not up yet
    env.city.heal()  # two minutes later it is
    await env.advance(minutes=10)
    assert departing(env), "setup should have been retried (SETUP_RETRY) instead of waiting for the hourly tick"


async def test_e2e_21_a_retried_setup_says_why(env):
    """HA raises ConfigEntryNotReady without a reason; the entry shows the City's one, and never the key."""
    env.city.always("timetable", Http(500))
    entry = await env.add_entry()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.reason
    assert DEFAULT_KEY not in entry.reason


@pytest.mark.start("2026-10-17 12:00")
async def test_e2e_21_a_slow_city_does_not_throw_away_the_stored_timetable(env, hass_storage):
    """The deadline ends a first refresh that hangs; with a stored timetable of today the sensor starts from it."""
    entry = await env.add_entry(line="151", setup=False)
    key = f"ztm_warsaw.{entry.entry_id}"
    rows = [{"czas": "13:30:00"}, {"czas": "14:30:00"}]
    hass_storage[key] = {"version": 1, "key": key, "data": {"answers": [{"service_date": "2026-10-17", "rows": rows}]}}
    env.city.always(None, Hang())
    task = asyncio.ensure_future(env.hass.config_entries.async_setup(entry.entry_id))
    await env.drive_timeouts(task)
    await env.settle()
    assert entry.state is ConfigEntryState.LOADED
    assert env.departure_local("151") == "2026-10-17 13:30"


async def test_e2e_21_a_hanging_stops_catalogue_does_not_keep_the_sensor_away(env):
    """The stop's name is optional: with the timetable healthy and the catalogue hanging, setup still succeeds (a review finding)."""
    env.city.always("stops", Hang())
    task = asyncio.ensure_future(env.add_entry())
    entry = await env.drive_timeouts(task)
    assert entry.state is ConfigEntryState.LOADED
    assert departing(env)


async def test_e2e_16_a_failed_refresh_covered_by_the_cache_is_retried_in_minutes_not_an_hour(env):
    """Right after a restart the City may be unreachable for a moment: the sensors must not wait for the next hourly tick."""
    await env.add_entry()
    coord = coordinator_of(env)
    cached = coord.data
    env.city.always(None, Reset())
    await env.hourly_tick()
    assert coord.data is cached, "the cached timetable covers the failure"
    env.city.heal()  # the City is back; nothing but the short retry asks for it
    await env.advance(seconds=360)
    assert coord.data is not cached, "the retry fetched a fresh timetable long before the next hourly refresh"
    assert coord._retry_unsub is None, "a retry that worked does not schedule another"


async def test_e2e_16_an_answer_without_the_stop_name_keeps_the_name_the_stop_has(env):
    """A refresh whose catalogue read failed brings a timetable without the stop's name: the name (and the pin) must stay."""
    await env.add_entry()
    coord = coordinator_of(env)
    known = coord.data.stop_info
    assert known
    coord._accept(ZTMDepartureData(departures=list(coord.data.departures), stop_info=None, service_date=coord.data.service_date))
    assert coord.data.stop_info == known


async def test_e2e_16_a_stop_that_starts_without_a_timetable_is_asked_again_in_minutes(env):
    """One stop of a line failing at startup must not wait for the next hourly tick."""
    await env.add_entry()
    coord = coordinator_of(env)
    assert coord._retry_unsub is None
    with patch.object(coord, "_schedule_flip_refresh"):  # the one made at the setup is the one that stays
        coord.start_without_timetable()
    assert coord._retry_unsub is not None


async def test_e2e_16_a_pending_retry_is_not_doubled_and_an_unload_cancels_it(env):
    """Two failures before the retry fire one retry, and a stop that is unloaded leaves no timer behind."""
    entry = await env.add_entry()
    coord = coordinator_of(env)
    env.city.always(None, Reset())
    await env.hourly_tick()
    pending = coord._retry_unsub
    assert pending is not None
    await coord.async_refresh()  # a second failure while the first retry is still waiting
    assert coord._retry_unsub is pending, "the wait already under way is kept, not replaced"
    await env.hass.config_entries.async_unload(entry.entry_id)
    assert coord._retry_unsub is None, "unloading cancels the wait"


async def test_e2e_16_a_long_outage_is_said_once_and_asked_less_and_less_often(env, caplog):
    """The City's old host can be down for hours: the log says so once, and the retries do not stay at five minutes."""
    caplog.set_level(logging.DEBUG)
    await env.add_entry()
    env.city.always(None, Reset())
    env.city.reset_counts()
    caplog.clear()
    await env.advance(seconds=3600 * 3)
    loud = [r for r in caplog.records if r.levelno >= logging.WARNING and r.name.startswith("custom_components.ztm_warsaw")]
    assert 0 < len(loud) <= 8, f"said at the start of the outage, not at every try: {[r.getMessage()[:60] for r in loud]}"
    asked = env.city.count("timetable")
    assert 0 < asked <= 24, f"{asked} requests in three hours (two per try); five-minute retries without a back-off would be about 72"
    env.city.heal()
    caplog.clear()
    await env.advance(seconds=3700)
    assert any("answers again" in r.getMessage() for r in caplog.records)


async def test_e2e_16_an_outage_with_http_errors_is_said_once_like_one_with_resets(env, caplog):
    """The City answering 500 for hours is an outage too: the log says so once."""
    caplog.set_level(logging.DEBUG)
    await env.add_entry()
    env.city.always(None, Http(500))
    caplog.clear()
    await env.advance(seconds=3600 * 3)
    loud = [r for r in caplog.records if r.levelno >= logging.WARNING and r.name.startswith("custom_components.ztm_warsaw")]
    assert 0 < len(loud) <= 8, f"said at the start of the outage, not at every try: {[r.getMessage()[:70] for r in loud]}"
    assert any("HTTP 500" in r.getMessage() for r in caplog.records), "and the status is in the message"


async def test_e2e_16_an_old_api_that_does_not_answer_is_said_once_for_all_the_stops(env, caplog):
    """The old API can be switched off for good: one clear line tells the user to get a token, however many stops there are."""
    caplog.set_level(logging.DEBUG)
    await env.add_entry()
    await env.add_entry(line="523")
    env.city.always(None, Reset())
    caplog.clear()
    await env.advance(seconds=3600 * 3)
    loud = [r for r in caplog.records if r.levelno >= logging.WARNING and r.name.startswith("custom_components.ztm_warsaw")]
    assert len(loud) == 1, [r.getMessage()[:80] for r in loud]
    assert "old API" in loud[0].getMessage()
    assert "token" in loud[0].getMessage()


async def test_e2e_16_the_end_of_an_outage_of_the_old_api_and_of_a_token_is_said_once(env, caplog):
    """The old API's outage is said once for all the stops, so is its end; a token's end is said by its stop."""
    caplog.set_level(logging.INFO)
    await env.add_entry()  # an old key
    await env.add_entry(line="525")  # a second line with an old key: the end is still said once
    await env.add_entry(line="523", api_key=DEFAULT_TOKEN)
    env.city.always(None, Reset())
    await env.advance(seconds=3600 * 2)
    caplog.clear()
    env.city.heal()
    await env.advance(seconds=3700)
    ends = [r.getMessage() for r in caplog.records if "answers again" in r.getMessage()]
    assert sorted(ends) == ["The City of Warsaw answers again", "The City of Warsaw's old API answers again"]
