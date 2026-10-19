"""E2E-28 .. E2E-30: behaviour the roadmap promises but 1.1.4 does not have. Written first, xfail(strict) until
the feature lands; the strict flag turns the day it works into a red build that says "remove the mark"."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState

from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN, Http, stop_name_for

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
async def test_e2e_29_reauth_flow_offers_a_form_to_enter_a_new_key(env):
    entry = await env.add_entry()
    result = await env.hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id}, data=entry.data
    )
    assert result["type"] == "form"


async def test_e2e_29_a_rejected_key_starts_reauth_after_repeated_failures(env):
    entry = await env.add_entry()
    env.city.valid_keys.clear()
    for _ in range(3):
        await env.hourly_tick()
    flows = env.hass.config_entries.flow.async_progress_by_handler(DOMAIN, match_context={"source": "reauth"})
    assert [f["context"]["entry_id"] for f in flows] == [entry.entry_id]


NEW_KEY = "22222222-3333-4444-8555-666666666666"  # gitleaks:allow  (synthetic)


def _reauth_flows(env):
    return env.hass.config_entries.flow.async_progress_by_handler(DOMAIN, match_context={"source": "reauth"})


async def _entry_with_a_rejected_key(env, **kwargs):
    """Set up with a key the City rejects; Home Assistant retries the setup (5 s, 10 s, ...) and the third answer asks the user."""
    env.city.valid_keys.clear()
    entry = await env.add_entry(**kwargs)
    assert entry.state is ConfigEntryState.SETUP_RETRY, "one rejection is not enough"
    assert not _reauth_flows(env)
    await env.advance(minutes=2)
    return entry


async def test_e2e_29_a_key_rejected_three_times_at_setup_starts_reauth(env):
    entry = await _entry_with_a_rejected_key(env)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert [f["context"]["entry_id"] for f in _reauth_flows(env)] == [entry.entry_id]


async def test_e2e_29_one_rejection_at_runtime_does_not_ask_the_user(env):
    await env.add_entry()
    env.city.valid_keys.clear()
    await env.hourly_tick()
    assert not _reauth_flows(env), "a single answer is not enough to bother the user"


async def test_e2e_29_an_outage_never_starts_reauth(env):
    await env.add_entry()
    env.city.always(None, Http(500))
    for _ in range(4):
        await env.hourly_tick()
    assert not _reauth_flows(env)


async def test_e2e_29_reauth_with_a_good_key_updates_the_entry_and_reloads_it(env):
    entry = await _entry_with_a_rejected_key(env)
    env.city.valid_keys.add(NEW_KEY)
    flow = _reauth_flows(env)[0]
    assert flow["step_id"] == "reauth_confirm"
    result = await env.hass.config_entries.flow.async_configure(flow["flow_id"], {"api_key": f"  {NEW_KEY}\n"})
    await env.settle()
    assert (result["type"], result["reason"]) == ("abort", "reauth_successful")
    assert entry.data["api_key"] == NEW_KEY
    assert (entry.data["busstop_id"], entry.data["busstop_nr"], entry.data["line"]) == (7009, "01", "151")
    assert entry.state is ConfigEntryState.LOADED
    assert env.departure_local() is not None


@pytest.mark.parametrize(("typed", "error"), [("not a key", "invalid_api_key"), ("33333333-4444-4555-8666-777777777777", "invalid_api_key")])
async def test_e2e_29_reauth_with_a_bad_key_shows_the_error_and_keeps_the_entry(env, typed, error):
    entry = await _entry_with_a_rejected_key(env)
    flow = _reauth_flows(env)[0]
    result = await env.hass.config_entries.flow.async_configure(flow["flow_id"], {"api_key": typed})
    assert (result["type"], result["errors"]) == ("form", {"base": error})
    assert entry.data["api_key"] == DEFAULT_KEY


async def test_e2e_29_reauth_of_a_loaded_entry_reloads_it_once(env):
    entry = await env.add_entry()
    env.city.valid_keys.clear()
    for _ in range(3):
        await env.hourly_tick()
    env.city.valid_keys.add(NEW_KEY)
    flow = _reauth_flows(env)[0]
    with patch.object(env.hass.config_entries, "async_reload", wraps=env.hass.config_entries.async_reload) as reload:
        await env.hass.config_entries.flow.async_configure(flow["flow_id"], {"api_key": NEW_KEY})
        await env.settle()
    assert reload.call_count == 1, "the update listener and the reauth must not both reload the entry"
    assert entry.state is ConfigEntryState.LOADED
    assert env.departure_local() is not None


async def test_e2e_29_the_same_key_again_after_the_city_recovered_restarts_the_entry(env):
    """Three rejections stop the hourly refresh; the user types the key they have, which now works (a review finding)."""
    entry = await env.add_entry()
    env.city.valid_keys.clear()
    for _ in range(3):
        await env.hourly_tick()
    assert env.state().state == "unavailable"
    env.city.valid_keys.add(DEFAULT_KEY)
    flow = _reauth_flows(env)[0]
    result = await env.hass.config_entries.flow.async_configure(flow["flow_id"], {"api_key": DEFAULT_KEY})
    await env.settle()
    assert (result["type"], result["reason"]) == ("abort", "reauth_successful")
    assert entry.state is ConfigEntryState.LOADED
    assert env.departure_local() is not None, "the entry was reloaded although nothing in it changed"


@pytest.mark.start("2026-10-17 12:00")
async def test_e2e_29_a_good_key_is_accepted_although_the_line_does_not_run_today(env):
    """411 runs on weekdays only; the key of a Saturday reauth is still judged by the key (a review finding)."""
    entry = await env.add_entry(line="411")
    env.city.valid_keys.clear()
    for _ in range(3):
        await env.hourly_tick()
    env.city.valid_keys.add(NEW_KEY)
    flow = _reauth_flows(env)[0]
    result = await env.hass.config_entries.flow.async_configure(flow["flow_id"], {"api_key": NEW_KEY})
    assert (result["type"], result["reason"]) == ("abort", "reauth_successful")
    assert entry.data["api_key"] == NEW_KEY


async def test_e2e_29_rejections_must_be_consecutive(env):
    await env.add_entry()
    env.city.valid_keys.clear()
    await env.hourly_tick()
    await env.hourly_tick()
    env.city.always(None, Http(500))  # an outage in between breaks the run
    await env.hourly_tick()
    env.city.heal()
    await env.hourly_tick()
    assert not _reauth_flows(env)


async def test_e2e_29_an_outage_that_breaks_the_run_of_rejections_is_stored_too(env, hass_storage):
    """A crash after the outage must not revive the old count (a review finding)."""
    entry = await env.add_entry()
    key = f"ztm_warsaw.{entry.entry_id}"
    env.city.valid_keys.clear()
    await env.hourly_tick()
    await env.hourly_tick()
    await env.advance(minutes=1)
    assert hass_storage[key]["data"]["rejections"] == 2
    env.city.valid_keys.add(DEFAULT_KEY)
    env.city.always(None, Http(500))
    await env.hourly_tick()
    await env.advance(minutes=1)
    assert hass_storage[key]["data"]["rejections"] == 0


async def test_e2e_29_reauth_of_an_entry_that_cannot_be_read_aborts(env):
    entry = await env.add_entry(data={"api_key": DEFAULT_KEY}, setup=False)
    result = await env.hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id}, data=entry.data
    )
    assert (result["type"], result["reason"]) == ("abort", "unknown")


# ===================================================================== E2E-30 diagnostics
async def test_e2e_30_diagnostics_download_redacts_the_api_key(env):
    entry = await env.add_entry()
    diagnostics = importlib.import_module("custom_components.ztm_warsaw.diagnostics")
    result = await diagnostics.async_get_config_entry_diagnostics(env.hass, entry)
    assert DEFAULT_KEY not in json.dumps(result, default=str)
    assert "api_key" in json.dumps(result, default=str), "the field is shown, its value is redacted"


async def _diagnostics(env, entry):
    module = importlib.import_module("custom_components.ztm_warsaw.diagnostics")
    return await module.async_get_config_entry_diagnostics(env.hass, entry)


async def test_e2e_30_diagnostics_describe_the_entry_and_its_timetable(env):
    entry = await env.add_entry(departures=2)
    result = await _diagnostics(env, entry)
    assert result["entry"]["data"]["api_key"] == "**REDACTED**"
    assert (result["entry"]["data"]["line"], result["entry"]["state"]) == ("151", "loaded")
    assert result["key_kind"] == "legacy"
    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["current"]["departures"] > 0
    assert result["coordinator"]["current"]["first_labels"]


async def test_e2e_30_diagnostics_of_an_entry_that_is_not_loaded_still_work_and_hide_the_key(env):
    entry = await env.add_entry(setup=False)
    result = await _diagnostics(env, entry)
    assert result["coordinator"] is None
    assert DEFAULT_KEY not in json.dumps(result, default=str)


async def test_e2e_30_a_token_never_appears_anywhere_in_the_diagnostics(env):
    entry = await env.add_entry(api_key=DEFAULT_TOKEN)
    text = json.dumps(await _diagnostics(env, entry), default=str)
    assert DEFAULT_TOKEN not in text
    assert not any(part in text for part in DEFAULT_TOKEN.split(".") if len(part) > 8)
    assert '"key_kind": "token"' in text


async def test_e2e_30_diagnostics_after_a_rejected_key_name_the_error_class_only(env):
    entry = await env.add_entry()
    env.city.valid_keys.clear()
    await env.hourly_tick()
    result = await _diagnostics(env, entry)
    assert result["coordinator"]["api_error"] is True
    assert result["coordinator"]["last_exception"] == "UpdateFailed"
    assert result["coordinator"]["rejections_in_a_row"] == 1
    assert DEFAULT_KEY not in json.dumps(result, default=str)


async def test_e2e_30_every_spelling_of_the_key_is_redacted(env):
    entry = await env.add_entry(data={"apikey": DEFAULT_KEY, "busstopId": 7009, "busstopNr": "01", "line": "151"}, setup=False)
    text = json.dumps(await _diagnostics(env, entry), default=str)
    assert DEFAULT_KEY not in text
    assert "apikey" in text


async def test_e2e_30_a_key_in_the_options_is_redacted_too(env):
    entry = await env.add_entry(options={"api_key": DEFAULT_KEY, "departures": 2}, setup=False)
    result = await _diagnostics(env, entry)
    assert result["entry"]["options"] == {"api_key": "**REDACTED**", "departures": 2}
