"""E2E-28 .. E2E-30: behaviour the roadmap promises but 1.1.4 does not have. Written first, xfail(strict) until
the feature lands; the strict flag turns the day it works into a red build that says "remove the mark"."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import UnknownStep

from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN, Http, stop_name_for
from .helpers import known_bug

pytestmark = pytest.mark.e2e


# ===================================================================== E2E-28 new contract (JWT)
async def test_e2e_28_setup_with_a_jwt_talks_the_new_contract_end_to_end(env):
    result = await env.submit_flow(api_key=DEFAULT_TOKEN)
    assert result["type"] == "create_entry", result.get("errors")
    assert result["result"].state is ConfigEntryState.LOADED
    assert env.state().state not in ("unknown", "unavailable")

    new_calls = env.city.matching(contract="new")
    assert {c.endpoint for c in new_calls} >= {"lines", "timetable"}
    timetable = next(c for c in new_calls if c.endpoint == "timetable")
    assert timetable.method == "POST"
    assert timetable.key == DEFAULT_TOKEN, "the raw token, no 'Bearer'"
    assert timetable.body == {"busstopId": "7009", "busstopNr": "01", "line": "151"}, "all values are strings"


async def test_e2e_28_a_key_is_only_ever_sent_to_the_host_that_can_accept_it(env):
    env.city.valid_keys.add(DEFAULT_KEY)
    await env.add_entry(api_key=DEFAULT_TOKEN, line="151")
    await env.add_entry(api_key=DEFAULT_KEY, line="N25")
    legacy_keys = {c.key for c in env.city.matching(contract="legacy")}
    new_keys = {c.key for c in env.city.matching(contract="new")}
    assert DEFAULT_TOKEN not in legacy_keys, "a JWT must never be sent to api.um.warszawa.pl"
    assert DEFAULT_KEY not in new_keys, "a legacy UUID must never be sent to dane.um.warszawa.pl"
    assert DEFAULT_KEY in legacy_keys


async def test_e2e_28_an_entry_with_a_token_talks_only_to_the_new_host_and_shows_departures(env):
    await env.add_entry(api_key=DEFAULT_TOKEN)
    assert env.state().state not in ("unknown", "unavailable")
    assert env.city.count(contract="legacy") == 0, "a token never goes to api.um.warszawa.pl"
    new_calls = env.city.matching(contract="new")
    assert {c.endpoint for c in new_calls} == {"timetable", "stops"}
    timetable = next(c for c in new_calls if c.endpoint == "timetable")
    assert (timetable.method, timetable.key) == ("POST", DEFAULT_TOKEN), "the raw token, no 'Bearer'"
    assert timetable.body == {"busstopId": "7009", "busstopNr": "01", "line": "151"}, "all values are strings"
    assert env.state().attributes["Stop, Name"] == stop_name_for("7009"), "the name comes from the new catalogue"


@pytest.mark.start("2026-10-17 12:00")  # Saturday: line 411 does not run
async def test_e2e_28_a_line_that_does_not_run_today_is_no_service_with_a_token_too(env):
    await env.add_entry(api_key=DEFAULT_TOKEN, line="411")
    st = env.state("411")
    assert st.state == "unknown", "an empty timetable: available, no departure"
    assert st.attributes["Upcoming, Headsign"] == "No service"


async def test_e2e_28_every_request_says_which_software_asks_and_nothing_about_who(env):
    manifest = json.loads((Path(__file__).parents[2] / "custom_components/ztm_warsaw/manifest.json").read_text())
    expected = f"ztm_warsaw/{manifest['version']} (Home Assistant custom integration; +https://github.com/solarssk/ztm_warsaw)"
    await env.add_entry()
    await env.add_entry(api_key=DEFAULT_TOKEN, line="N25")
    assert {c.contract for c in env.city.calls} == {"legacy", "new"}, "the scenario must reach both hosts"
    assert {c.user_agent for c in env.city.calls} == {expected}
    assert DEFAULT_KEY not in expected
    assert DEFAULT_TOKEN not in expected


async def test_e2e_28_a_legacy_key_keeps_using_only_the_legacy_host(env):
    """The no-regression half of the routing rule, true today and must stay true after JWT support lands."""
    await env.add_entry_via_flow()
    assert env.city.count(contract="new") == 0
    assert env.city.count(contract="legacy") > 0


async def test_e2e_28_new_host_500_is_a_failed_setup_not_a_silent_no_service(env):
    env.city.always(None, Http(500), contract="new")
    entry = await env.add_entry(api_key=DEFAULT_TOKEN)
    # Today this fails at the next line for the JWT reason (1.1.4 never talks to the new host); it can only
    # XPASS once a JWT is supported AND the 500 is treated as a failure.
    assert env.city.count(contract="new") > 0, "it must at least have tried the new host"
    if entry.state is ConfigEntryState.LOADED:
        assert env.state().state == "unavailable"
    else:
        assert entry.state is ConfigEntryState.SETUP_RETRY


# ===================================================================== E2E-29 reauth
@known_bug(
    "no-reauth-step", "no reauth step: starting one raises UnknownStep", raises=(AssertionError, UnknownStep)
)
async def test_e2e_29_reauth_flow_offers_a_form_to_enter_a_new_key(env):
    entry = await env.add_entry()
    result = await env.hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id}, data=entry.data
    )
    assert result["type"] == "form"


@known_bug("rejected-key-starts-no-reauth", "a key the city rejects never starts a reauth flow; the entry just shows 'No service'")
async def test_e2e_29_a_rejected_key_starts_reauth_after_repeated_failures(env):
    entry = await env.add_entry()
    env.city.valid_keys.clear()
    for _ in range(3):
        await env.hourly_tick()
    flows = env.hass.config_entries.flow.async_progress_by_handler(DOMAIN, match_context={"source": "reauth"})
    assert [f["context"]["entry_id"] for f in flows] == [entry.entry_id]


# ===================================================================== E2E-30 diagnostics
@known_bug("no-diagnostics-platform", "no diagnostics platform", raises=(AssertionError, ImportError))
async def test_e2e_30_diagnostics_download_redacts_the_api_key(env):
    entry = await env.add_entry()
    diagnostics = importlib.import_module("custom_components.ztm_warsaw.diagnostics")
    result = await diagnostics.async_get_config_entry_diagnostics(env.hass, entry)
    assert DEFAULT_KEY not in json.dumps(result, default=str)
    assert "api_key" in json.dumps(result, default=str), "the field is shown, its value is redacted"
