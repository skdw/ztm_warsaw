"""Optional LIVE contract check: do the REAL City of Warsaw responses still have the shape the fake city serves?

Why it exists: the whole e2e suite trusts a fake. The fake is only as good as our belief about the real API, and
beliefs go stale (the legacy host is being phased out; the new one is only partly documented). This file runs
the SAME shape assertions (``tests/contract_shapes.py``) that ``test_harness.py`` runs against the fake, but
against api.um.warszawa.pl / dane.um.warszawa.pl.

Rules
* never in PR CI; never without a key. ``-m live`` AND ``ZTM_LIVE_API_KEY`` are both required.
* at most 6 requests per run, one per test, at human pace. The stops catalogue (1.6 MB) is opt-in.
* the key is never printed: errors are re-raised as the exception class name only, no URL, no headers.

    ZTM_LIVE_API_KEY=<uuid or jwt> python -m pytest -m live tests/live -p no:cacheprovider
    ZTM_LIVE_STOP_ID=7009 ZTM_LIVE_STOP_NR=01  # optional, these are the defaults
    ZTM_LIVE_CATALOGUE=1                        # also download the stops catalogue (legacy host only)
"""

from __future__ import annotations

import asyncio
import json
import os

import aiohttp
import pytest

from tests.contract_shapes import (
    RESPONSE_CAP_BYTES,
    assert_lines_rows,
    assert_stops_rows,
    assert_timetable_rows,
    classify_legacy,
    is_legacy_key,
)

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_network")]

STOP_ID = os.environ.get("ZTM_LIVE_STOP_ID", "7009")
STOP_NR = os.environ.get("ZTM_LIVE_STOP_NR", "01")
LEGACY = "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
NEW = "https://dane.um.warszawa.pl/api/action/"
IDS = {
    "timetable": "e923fa0e-d96c-43f9-ae6e-60518c9f3238",
    "lines": "88cd555f-6f31-43ca-9de4-66c479ad5942",
    "stops": "ab75c33d-3a26-4342-b36a-6e5fef0a3ac3",
}
ACTIONS = {
    "timetable": "get_ztm_odjazdy_linii_z_przystanku",
    "lines": "get_ztm_lista_linii_na_przystanku",
    "stops": "get_ztm_przystanki_komunikacji_miejskiej",
}


async def _call(key: str, what: str, **params: str) -> tuple[int, bytes]:
    """One request on whichever contract ``key`` belongs to. Returns (status, body); never leaks the key."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            if is_legacy_key(key):
                request = session.get(LEGACY, params={"id": IDS[what], "apikey": key, **params})
            else:
                request = session.post(NEW + ACTIONS[what], json=params or None, headers={"Authorization": key})
            async with request as resp:
                body = await resp.content.read(RESPONSE_CAP_BYTES + 1)
                return resp.status, body
    except (TimeoutError, aiohttp.ClientError) as err:
        raise AssertionError(f"live API unreachable ({type(err).__name__})") from None
    finally:
        await asyncio.sleep(1)  # be polite


def _json(body: bytes):
    try:
        return json.loads(body)
    except ValueError:
        raise AssertionError(f"response is not JSON ({len(body)} bytes)") from None


async def test_live_lines_at_the_stop_have_the_documented_shape(live_key):
    status, body = await _call(live_key, "lines", busstopId=STOP_ID, busstopNr=STOP_NR)
    assert status == 200, f"HTTP {status}"
    payload = _json(body)
    if is_legacy_key(live_key):
        assert classify_legacy(payload) == "rows"
    lines = assert_lines_rows(payload)
    assert lines, "a real stop pole has at least one line today"


async def test_live_timetable_has_the_documented_shape_including_service_hours_past_24(live_key):
    status, body = await _call(live_key, "lines", busstopId=STOP_ID, busstopNr=STOP_NR)
    assert status == 200
    lines = assert_lines_rows(_json(body))
    line = os.environ.get("ZTM_LIVE_LINE") or lines[0]
    status, body = await _call(live_key, "timetable", busstopId=STOP_ID, busstopNr=STOP_NR, line=line)
    assert status == 200, f"HTTP {status}"
    payload = _json(body)
    if is_legacy_key(live_key):
        assert classify_legacy(payload) == "rows"
    rows = assert_timetable_rows(payload)  # keys, HH:MM:SS, hour < 29
    assert rows, "a line listed at the stop runs today"
    # The envelope is the whole difference between the two hosts and the thing the fake mimics:
    assert isinstance(payload, dict) == is_legacy_key(live_key), "legacy -> {'result': [...]}, new -> bare list"


async def test_live_error_semantics_the_fake_relies_on():
    """Legacy host only (it is the only contract whose error bodies are documented by measurement)."""
    unknown = "00000000-0000-0000-0000-000000000000"  # shaped like a legacy key, certainly not issued
    status, body = await _call(unknown, "timetable", busstopId=STOP_ID, busstopNr=STOP_NR, line="151")
    assert status == 200 and classify_legacy(_json(body)) == "bad_key"


async def test_live_unknown_parameters_answer_with_the_text_error(live_key):
    if not is_legacy_key(live_key):
        pytest.skip("the new host's error semantics are unverified (a bogus token gave HTTP 500)")
    status, body = await _call(live_key, "timetable", busstopId="9999", busstopNr="99", line="ZZZ")
    assert status == 200 and classify_legacy(_json(body)) == "param_error"


@pytest.mark.skipif(not os.environ.get("ZTM_LIVE_CATALOGUE"), reason="opt-in: downloads ~1.6 MB")
async def test_live_stops_catalogue_shape_and_size_stay_under_the_integrations_cap(live_key):
    status, body = await _call(live_key, "stops")
    assert status == 200
    assert len(body) <= RESPONSE_CAP_BYTES, (
        f"catalogue is {len(body)} bytes: past the integration's {RESPONSE_CAP_BYTES} byte cap"
    )
    assert assert_stops_rows(_json(body)) > 1000
