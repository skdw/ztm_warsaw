"""H-xx: the fake city and the routing seam are themselves tested.

If one of these fails, a red e2e scenario must not be trusted: the instrument is broken, not (only)
the integration. Plain aiohttp is used here on purpose, no Home Assistant code is involved.
"""

from __future__ import annotations

import json
import socket
from datetime import time, timedelta

import aiohttp
import pytest
import pytest_socket
from yarl import URL

from tests.contract_shapes import (
    RESPONSE_CAP_BYTES,
    SERVICE_UNAVAILABLE,
    assert_lines_rows,
    assert_stops_rows,
    assert_timetable_rows,
    classify_legacy,
    classify_new,
    czas_to_minutes,
    is_legacy_key,
)
from tests.live.capped import read_capped

from .conftest import at
from .fake_city import (
    DEFAULT_KEY,
    DEFAULT_TOKEN,
    FULL_CATALOGUE,
    FULL_NEW_CATALOGUE,
    LEGACY_LINES_ID,
    LEGACY_STOPS_ID,
    LEGACY_TIMETABLE_ID,
    OVER_CAP_CATALOGUE,
    BadKey,
    FakeCity,
    Hang,
    Html,
    Http,
    InvalidJson,
    HarnessError,
    NetworkBlocked,
    NullResult,
    Oversize,
    ParamError,
    Redirect,
    Reset,
    Truncated,
    czas_of,
    day_sets,
)
from .fake_city.data import NEW_ACTION_LINES, NEW_ACTION_STOPS, NEW_ACTION_TIMETABLE, SERVICE_UNAVAILABLE_PAYLOAD
from .helpers import rows_for

pytestmark = pytest.mark.e2e

LEGACY = "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
NEW = "https://dane.um.warszawa.pl/api/action/"


async def legacy_get(session, dataset, key=DEFAULT_KEY, **params):
    async with session.get(LEGACY, params={"id": dataset, "apikey": key, **params}) as resp:
        return resp.status, await resp.read()


# ---------------------------------------------------------------------- H-01 contract
async def test_h01_legacy_payloads_have_the_documented_shapes(fake_city, clock):
    clock.move_to(at("2026-10-16 12:00"))
    async with aiohttp.ClientSession() as s:
        status, body = await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="151")
        assert status == 200
        rows = assert_timetable_rows(json.loads(body))
        assert len(rows) == 81  # the captured Friday set

        _, body = await legacy_get(s, LEGACY_LINES_ID, busstopId="7009", busstopNr="01")
        assert "N25" in assert_lines_rows(json.loads(body))

        _, body = await legacy_get(s, LEGACY_STOPS_ID)
        assert assert_stops_rows(json.loads(body)) > 100


async def test_h01_error_payloads_follow_the_measured_semantics(fake_city, clock):
    clock.move_to(at("2026-10-17 12:00"))  # Saturday: line 411 does not run
    async with aiohttp.ClientSession() as s:
        _, b = await legacy_get(s, LEGACY_TIMETABLE_ID, key="nope", busstopId="7009", busstopNr="01", line="151")
        assert classify_legacy(json.loads(b)) == "bad_key"
        _, b = await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="ZZZ")
        assert classify_legacy(json.loads(b)) == "param_error"
        _, b = await legacy_get(s, LEGACY_TIMETABLE_ID)  # no parameters at all
        assert classify_legacy(json.loads(b)) == "param_error"
        _, b = await legacy_get(s, LEGACY_LINES_ID, busstopId="9999", busstopNr="99")
        assert classify_legacy(json.loads(b)) == "param_error"
        _, b = await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="411")
        assert classify_legacy(json.loads(b)) == "null"
        _, b = await legacy_get(s, "00000000-0000-0000-0000-000000000000", busstopId="7009")
        assert classify_legacy(json.loads(b)) == "param_error"


# ---------------------------------------------------------------------- H-02 service day
@pytest.mark.parametrize(
    ("instant", "service_date", "day_set", "first_523"),
    [
        ("2026-10-16 23:50", "2026-10-16", "friday", "04:50:00"),
        ("2026-10-17 00:10", "2026-10-16", "friday", "04:50:00"),  # midnight does NOT flip the day
        ("2026-10-17 02:59:59", "2026-10-16", "friday", "04:50:00"),
        ("2026-10-17 03:00:00", "2026-10-17", "saturday", "05:15:00"),
        ("2026-10-17 04:30", "2026-10-17", "saturday", "05:15:00"),
    ],
)
async def test_h02_service_day_flips_at_three_not_at_midnight(
    fake_city, clock, instant, service_date, day_set, first_523
):
    clock.move_to(at(instant))
    async with aiohttp.ClientSession() as s:
        _, body = await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="523")
    assert min(r["czas"] for r in assert_timetable_rows(json.loads(body))) == first_523
    call = fake_city.calls[-1]
    assert (str(call.service_date), call.day_set) == (service_date, day_set)


def test_h02_flip_time_is_a_knob(clock):
    city = FakeCity(flip_at=time(2, 55))
    clock.move_to(at("2026-10-17 02:56"))
    assert str(city.service_date()) == "2026-10-17"
    clock.move_to(at("2026-10-17 02:54"))
    assert str(city.service_date()) == "2026-10-16"


@pytest.mark.parametrize(
    ("instant", "service_date"),
    [
        ("2026-03-29 01:59", "2026-03-28"),  # spring forward night: before 03:00 wall clock
        ("2026-03-29 03:01", "2026-03-29"),
        ("2026-10-25 02:30", "2026-10-24"),  # fall back night (first pass of the repeated hour)
        ("2026-10-25 03:30", "2026-10-25"),
    ],
)
def test_h02_service_day_is_defined_on_dst_days(clock, instant, service_date):
    city = FakeCity()
    clock.move_to(at(instant))
    assert str(city.service_date()) == service_date


# ---------------------------------------------------------------------- H-03 failure modes
@pytest.mark.parametrize(
    ("behavior", "expect"),
    [
        (Reset(), aiohttp.ClientError),
        (Truncated(), aiohttp.ClientError),
    ],
    ids=["reset", "truncated"],
)
async def test_h03_connection_level_failures_surface_as_client_errors(fake_city, behavior, expect):
    fake_city.always("timetable", behavior)
    async with aiohttp.ClientSession() as s:
        with pytest.raises(expect) as caught:
            await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="151")
    assert isinstance(caught.value, aiohttp.ClientError)  # what the integration's `except ClientError` catches


@pytest.mark.parametrize(
    ("behavior", "status", "check"),
    [
        (BadKey(), 200, lambda b: classify_legacy(json.loads(b)) == "bad_key"),
        (ParamError(), 200, lambda b: classify_legacy(json.loads(b)) == "param_error"),
        (NullResult(), 200, lambda b: classify_legacy(json.loads(b)) == "null"),
        (Http(500), 500, lambda b: json.loads(b) == {"message": "Service unavailable"}),
        (Http(403, {"message": "Forbidden"}), 403, lambda b: json.loads(b) == {"message": "Forbidden"}),
        (InvalidJson(), 200, lambda b: not _is_json(b)),
        (Html(), 200, lambda b: b.startswith(b"<html>")),
        (Oversize(), 200, lambda b: len(b) > 2_000_000),
    ],
    ids=["bad_key", "param_error", "null", "500", "403", "invalid_json", "html", "oversize"],
)
async def test_h03_scripted_answers(fake_city, behavior, status, check):
    fake_city.always("timetable", behavior)
    async with aiohttp.ClientSession() as s:
        got_status, body = await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="151")
    assert got_status == status
    assert check(body)
    assert fake_city.calls[-1].behavior == behavior.name


def _is_json(body: bytes) -> bool:
    try:
        json.loads(body)
    except ValueError:
        return False
    return True


async def test_h03_script_is_consumed_in_order_and_heals(fake_city):
    fake_city.script("timetable", Http(500), Http(503))  # then normal
    async with aiohttp.ClientSession() as s:
        got = [
            (await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="151"))[0]
            for _ in range(3)
        ]
    assert got == [500, 503, 200]
    assert fake_city.count("timetable") == 3
    fake_city.always("timetable", Http(500))
    fake_city.heal()
    async with aiohttp.ClientSession() as s:
        assert (await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="151"))[0] == 200


async def test_h03_hang_blocks_until_released(fake_city):
    import asyncio

    fake_city.always("timetable", Hang())
    async with aiohttp.ClientSession() as s:
        task = asyncio.ensure_future(legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="151"))
        await fake_city.wait_hung(1)
        assert not task.done()
        fake_city.heal()  # releases
        status, _ = await task
    assert status == 200


async def test_h03_waiting_for_a_hang_does_not_depend_on_how_fast_the_request_arrives(fake_city):
    """A bounded spin of ``sleep(0)`` ran out on a slow CI runner with coverage tracing; the wait is event-driven."""
    import asyncio

    fake_city.always("timetable", Hang())
    waiter = asyncio.ensure_future(fake_city.wait_hung(1))
    for _ in range(10_000):  # far more loop turns than the old spin budget (3000), with no request in flight
        await asyncio.sleep(0)
    assert not waiter.done()
    async with aiohttp.ClientSession() as s:
        task = asyncio.ensure_future(legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="151"))
        await asyncio.wait_for(waiter, timeout=30)
        fake_city.heal()
        status, _ = await task
    assert status == 200
    assert fake_city._hang_waiters == []


# ---------------------------------------------------------------------- H-04 sandbox
async def test_h04_only_the_fake_city_is_reachable(fake_city):
    async with aiohttp.ClientSession() as s:
        with pytest.raises(NetworkBlocked):
            await s.get("https://example.com/")
        with pytest.raises(NetworkBlocked):
            await s.get("https://dane.um.warszawa.pl.evil.example/")
    assert len(fake_city.blocked) == 2
    fake_city.blocked.clear()  # these were intentional


@pytest.mark.parametrize("target", ["https://example.com/", "http://93.184.216.34/"], ids=["hostname", "ip_literal"])
async def test_h04_a_redirect_to_another_host_is_blocked_before_any_lookup(fake_city, target):
    """aiohttp follows redirects inside the original ``_request``, so the connector is the checkpoint."""
    fake_city.always("timetable", Redirect(target))
    async with aiohttp.ClientSession() as s:
        with pytest.raises(NetworkBlocked):
            await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="151")
    assert len(fake_city.blocked) == 1
    fake_city.blocked.clear()  # intentional


def test_h04_pytest_socket_still_guards_every_non_loopback_address(socket_enabled):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(pytest_socket.SocketConnectBlockedError):
            sock.connect(("93.184.216.34", 80))
    finally:
        sock.close()


# ---------------------------------------------------------------------- H-05 new contract
async def test_h05_new_contract_post_with_raw_authorization_returns_a_bare_list(fake_city, clock):
    clock.move_to(at("2026-10-16 12:00"))
    body = {"busstopId": "7009", "busstopNr": "01", "line": "151"}
    async with aiohttp.ClientSession() as s:
        async with s.post(
            NEW + "get_ztm_odjazdy_linii_z_przystanku", json=body, headers={"Authorization": DEFAULT_TOKEN}
        ) as r:
            payload = await r.json()
        assert isinstance(payload, list)
        assert len(assert_timetable_rows(payload)) == 81
        assert payload[0][0].keys() == {"value", "key"}

        async with s.post(
            NEW + "get_ztm_lista_linii_na_przystanku",
            json={"busstopId": "7009", "busstopNr": "01"},
            headers={"Authorization": DEFAULT_TOKEN},
        ) as r:
            assert "151" in assert_lines_rows(await r.json())

        async with s.post(
            NEW + "get_ztm_odjazdy_linii_z_przystanku", json=body, headers={"Authorization": "bogus"}
        ) as r:
            assert r.status == 500  # OBSERVED on the real service for a bogus token
            assert await r.json() == {"message": "Service unavailable"}
        async with s.post(NEW + "get_ztm_odjazdy_linii_z_przystanku", json=body) as r:
            assert r.status == 500
    new_calls = fake_city.matching(contract="new")
    assert [c.key for c in new_calls] == [DEFAULT_TOKEN, DEFAULT_TOKEN, "bogus", None]
    assert new_calls[0].params == body
    assert fake_city.count(contract="legacy") == 0


async def test_h05_legacy_host_does_not_know_the_new_paths_and_vice_versa(fake_city):
    async with aiohttp.ClientSession() as s:
        async with s.get(NEW + "get_ztm_odjazdy_linii_z_przystanku") as r:
            assert r.status == 405
        async with s.get(LEGACY.replace("dbtimetable_get/", "get_ztm_odjazdy_linii_z_przystanku")) as r:
            assert r.status == 404


NEW_STOP = {"busstopId": "7009", "busstopNr": "01"}
NEW_PAIR = {**NEW_STOP, "line": "151"}


async def new_post(session, action, body=None, token=DEFAULT_TOKEN):
    headers = {} if token is None else {"Authorization": token}
    async with session.post(NEW + action, json=body, headers=headers) as resp:
        return resp.status, await resp.read(), resp.headers


@pytest.mark.parametrize(
    ("what", "action", "body", "token"),
    [
        ("no token", NEW_ACTION_TIMETABLE, NEW_PAIR, None),
        ("a token that is not a JWT", NEW_ACTION_TIMETABLE, NEW_PAIR, "x.y.z"),
        ("the right token with a Bearer prefix", NEW_ACTION_TIMETABLE, NEW_PAIR, f"Bearer {DEFAULT_TOKEN}"),
        ("an unknown stop", NEW_ACTION_TIMETABLE, {"busstopId": "9999", "busstopNr": "99", "line": "20"}, DEFAULT_TOKEN),
        ("an unknown line", NEW_ACTION_TIMETABLE, {**NEW_STOP, "line": "ZZZ"}, DEFAULT_TOKEN),
        ("a missing line", NEW_ACTION_TIMETABLE, NEW_STOP, DEFAULT_TOKEN),
        ("an empty object", NEW_ACTION_TIMETABLE, {}, DEFAULT_TOKEN),
        (
            "numbers instead of strings",
            NEW_ACTION_TIMETABLE,
            {"busstopId": 7009, "busstopNr": 1, "line": 151},
            DEFAULT_TOKEN,
        ),
        ("lines at an unknown stop", NEW_ACTION_LINES, {"busstopId": "9999", "busstopNr": "99"}, DEFAULT_TOKEN),
    ],
)
async def test_h05_every_rejected_request_on_the_new_host_is_the_same_500(fake_city, clock, what, action, body, token):
    """Measured 2026-10-18: nothing tells a bad token from a bad stop from a malformed request."""
    clock.move_to(at("2026-10-17 12:00"))
    async with aiohttp.ClientSession() as s:
        status, raw, _ = await new_post(s, action, body, token)
    assert (status, raw) == (500, b'{"message":"Service unavailable"}'), what


async def test_h05_a_line_that_does_not_run_today_is_the_bare_value_null(fake_city, clock):
    clock.move_to(at("2026-10-17 12:00"))  # Saturday: line 411 does not run
    async with aiohttp.ClientSession() as s:
        status, raw, _ = await new_post(s, NEW_ACTION_TIMETABLE, {**NEW_STOP, "line": "411"})
    assert (status, raw) == (200, b"null")
    assert classify_new(status, json.loads(raw)) == "null"


async def test_h05_the_new_host_answers_a_wrong_method_and_an_unknown_action_with_the_measured_bodies(fake_city):
    async with aiohttp.ClientSession() as s:
        async with s.get(NEW + NEW_ACTION_LINES, headers={"Authorization": DEFAULT_TOKEN}) as resp:
            assert (resp.status, await resp.read()) == (405, b'{"detail":"Method Not Allowed"}')
        status, raw, _ = await new_post(s, "does_not_exist", {})
    assert (status, raw) == (404, b'{"message":"Resource not found"}')


async def test_h05_the_new_host_sends_compact_json_without_a_charset(fake_city, clock):
    clock.move_to(at("2026-10-17 12:00"))
    async with aiohttp.ClientSession() as s:
        status, raw, headers = await new_post(s, NEW_ACTION_LINES, NEW_STOP)
    assert status == 200
    assert headers["Content-Type"] == "application/json"  # measured: no "; charset=utf-8"
    assert raw.startswith(b'[{"values":[{"value":"')
    assert b", " not in raw
    assert b": " not in raw


@pytest.mark.city(catalogue_bytes=FULL_NEW_CATALOGUE)
async def test_h05_the_new_host_catalogue_is_a_bare_list_of_six_key_records_under_the_cap(fake_city):
    async with aiohttp.ClientSession() as s:
        status, raw, _ = await new_post(s, NEW_ACTION_STOPS)
    assert status == 200
    assert 0.99 * FULL_NEW_CATALOGUE <= len(raw) <= 1.01 * FULL_NEW_CATALOGUE
    assert len(raw) < RESPONSE_CAP_BYTES
    records = json.loads(raw)
    assert isinstance(records, list)  # no {"result": ...} envelope
    assert assert_stops_rows(records) > 1000
    six = ("zespol", "slupek", "nazwa_zespolu", "id_ulicy", "szer_geo", "dlug_geo")
    assert {tuple(item["key"] for item in record["values"]) for record in records} == {six}


def test_h05_classify_new_follows_the_measurements():
    assert classify_new(200, None) == "null"
    assert classify_new(200, []) == "empty"
    assert classify_new(200, [[{"key": "czas", "value": "05:00:00"}]]) == "rows"
    assert classify_new(200, {"result": []}) == "unknown_shape"  # the legacy envelope is not the new host's
    assert classify_new(500, {"message": "Service unavailable"}) == "failure"
    assert classify_new(500, {"message": "something else"}) == "unknown_shape"
    assert classify_new(404, {"message": "Resource not found"}) == "not_found"
    assert classify_new(405, {"detail": "Method Not Allowed"}) == "method_not_allowed"


def test_h05_the_fake_and_the_shape_module_agree_on_the_one_error_body():
    assert SERVICE_UNAVAILABLE_PAYLOAD == SERVICE_UNAVAILABLE


# ---------------------------------------------------------------------- H-06 data
def test_h06_catalogue_sizes_match_what_they_claim():
    from .fake_city import data

    full = data.stops_catalogue_bytes(FULL_CATALOGUE)
    assert 0.99 * FULL_CATALOGUE <= len(full) <= 1.01 * FULL_CATALOGUE
    assert len(full) < 2_000_000  # under the integration's cap, as in production
    assert len(data.stops_catalogue_bytes(OVER_CAP_CATALOGUE)) > 2_000_000
    assert is_legacy_key(DEFAULT_KEY)
    assert not is_legacy_key(DEFAULT_TOKEN)


def test_h06_fixtures_carry_the_measured_facts():
    n25 = rows_for("friday", "N25")
    assert rows_for("saturday", "N25") == n25  # identical on both days
    assert (min(n25), max(n25)) == ("23:24:00", "28:54:00")
    assert max(rows_for("friday", "520"), key=czas_to_minutes) == "24:38:00"  # day line with a 24:xx tail
    assert (min(rows_for("friday", "523")), min(rows_for("saturday", "523"))) == ("04:50:00", "05:15:00")
    assert (len(rows_for("friday", "151")), len(rows_for("saturday", "151"))) == (81, 53)
    assert ("7009", "01") in {k[0] for k in day_sets()["friday"].timetables}
    assert ((("7009", "01"), "411")) not in day_sets()["saturday"].timetables  # not running on Saturday
    captured = {p for p, v in day_sets()["friday"].provenance.items() if v == "captured"}
    assert captured == {(("7009", "01"), line) for line in ("151", "523", "N25", "411")}
    assert all(czas_of(row) for row in day_sets()["friday"].timetables[(("7009", "01"), "151")])


async def test_h07_request_counting_and_param_capture(fake_city):
    async with aiohttp.ClientSession() as s:
        await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="151")
        await legacy_get(s, LEGACY_TIMETABLE_ID, busstopId="7009", busstopNr="01", line="523")
        await legacy_get(s, LEGACY_STOPS_ID)
    assert fake_city.count() == 3
    assert fake_city.count("timetable") == 2
    assert fake_city.count("timetable", line="523") == 1
    assert fake_city.count("stops", "legacy") == 1
    assert fake_city.bytes_sent("stops") == fake_city.matching("stops")[0].bytes_sent > 0
    assert URL("?" + fake_city.calls[0].query_string).query["apikey"] == DEFAULT_KEY


# ---------------------------------------------------------------------- H-08/09 clock and sleeps
def test_h08_frozen_clock_keeps_the_fixed_offset_astimezone_that_production_sees(clock, process_tz):
    """Plain freezegun answers ``astimezone()`` with dateutil's DST-aware tzlocal(); the real datetime gives a
    FIXED offset. The ``clock`` fixture restores the real one, otherwise the process-timezone and fixed-offset bugs would be invisible."""
    from datetime import UTC, datetime, timedelta, timezone

    process_tz("Europe/Warsaw")
    clock.move_to(at("2026-10-24 23:50"))
    local = datetime.now(UTC).astimezone()
    assert type(local.tzinfo) is timezone, type(local.tzinfo)
    assert local.utcoffset() == timedelta(hours=2)
    clock.move_to(at("2026-10-25 12:00"))
    assert datetime.now(UTC).astimezone().utcoffset() == timedelta(hours=1)
    process_tz("UTC")
    assert datetime.now(UTC).astimezone().utcoffset() == timedelta(0)


async def test_h09_backoff_patch_is_scoped_to_the_integration_modules(sleeps):
    import asyncio

    from custom_components.ztm_warsaw import client

    assert asyncio.sleep.__module__ == "asyncio.tasks", "the global asyncio.sleep must stay the real one"
    await client.asyncio.sleep(1.5)
    assert sleeps.requested == [1.5]
    assert client.asyncio.TimeoutError is asyncio.TimeoutError, "everything else is delegated to the real module"


# ---------------------------------------------------------------------- H-10 clock arithmetic
async def test_h10_advance_counts_real_time_across_the_repeated_dst_hour(env):
    """Aware datetimes sharing one tzinfo add as wall-clock time: from 02:59 CEST a naive ``+1 min`` lands on
    03:00 CET and jumps over the whole repeated hour. The helpers must go through UTC."""
    env.move_to("2026-10-25 02:59")  # first pass of the repeated hour, still CEST
    assert env.now.utcoffset() == timedelta(hours=2)
    await env.advance(minutes=1)
    assert (env.now.hour, env.now.utcoffset()) == (2, timedelta(hours=1)), "02:00 CET: the second pass is sampled"
    await env.advance(minutes=59)
    assert (env.now.hour, env.now.minute, env.now.utcoffset()) == (2, 59, timedelta(hours=1))
    await env.advance(minutes=1)
    assert (env.now.hour, env.now.utcoffset()) == (3, timedelta(hours=1))


async def test_h04_a_loopback_port_that_is_not_the_fake_city_is_blocked(fake_city):
    async with aiohttp.ClientSession() as s:
        with pytest.raises(NetworkBlocked):
            await s.get("http://127.0.0.1:1/")
    assert fake_city.blocked == ["http://127.0.0.1:1/"]
    fake_city.blocked.clear()  # intentional


# ---------------------------------------------------------------------- H-11 harness failures stay red
async def test_h11_a_harness_failure_is_not_an_assertion_error(env):
    """``known_bug`` is xfail(raises=AssertionError): a missing entity must not pass as 'the bug is still there'."""
    assert not issubclass(HarnessError, AssertionError)
    with pytest.raises(HarnessError):
        env.state("151")  # no entry has been added


# ---------------------------------------------------------------------- H-12 reading a large body
@pytest.mark.city(catalogue_bytes=FULL_CATALOGUE)
async def test_h12_read_capped_returns_the_whole_catalogue_not_the_first_chunk(fake_city):
    async with aiohttp.ClientSession() as s:
        async with s.get(LEGACY, params={"id": LEGACY_STOPS_ID, "apikey": DEFAULT_KEY}) as resp:
            body = await read_capped(resp)
    assert len(body) == fake_city.bytes_sent("stops"), "the whole body, however many chunks it arrived in"
    assert len(json.loads(body)["result"]) > 1000


@pytest.mark.city(catalogue_bytes=OVER_CAP_CATALOGUE)
async def test_h12_read_capped_stops_just_past_the_cap_for_an_oversized_body(fake_city):
    async with aiohttp.ClientSession() as s:
        async with s.get(LEGACY, params={"id": LEGACY_STOPS_ID, "apikey": DEFAULT_KEY}) as resp:
            body = await read_capped(resp)
    assert RESPONSE_CAP_BYTES < len(body) <= RESPONSE_CAP_BYTES + 64 * 1024
