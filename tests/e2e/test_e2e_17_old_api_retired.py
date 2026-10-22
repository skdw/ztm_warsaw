"""E2E-47: the City's old API is gone (const.LEGACY_API_RETIRED): an old key gets no request, only a clear message."""

from __future__ import annotations

import logging

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import issue_registry as ir

from custom_components.ztm_warsaw import config_flow
from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN

pytestmark = pytest.mark.e2e

STATUS = "sensor.line_151_from_7009_01_status"


@pytest.fixture
def retired(monkeypatch):
    """Treat the City's old API as gone, as production does (the e2e environment switches it off for the other tests)."""
    monkeypatch.setattr("custom_components.ztm_warsaw.const.LEGACY_API_RETIRED", True)


async def test_e2e_47_an_old_key_sends_no_request_and_the_line_says_why_it_has_no_timetable(env, retired, caplog):
    caplog.set_level(logging.INFO)
    entry = await env.add_entry()
    assert entry.state is ConfigEntryState.LOADED, "the line loads, so that the key can be replaced in the notice"
    assert env.city.count() == 0, "nothing is asked of the old API"
    assert env.state().state == "unavailable"
    assert env.hass.states.get(STATUS).state == "old_api"
    registry = ir.async_get(env.hass)
    assert registry.async_get_issue(DOMAIN, f"legacy_key_{entry.entry_id}") is None, "one notice per line: Home Assistant's own"
    flows = env.hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    reauth = [f for f in flows if f["context"].get("source") == "reauth"]
    assert len(reauth) == 1
    said = [r for r in caplog.records if r.levelno >= logging.WARNING and "old API" in r.getMessage()]
    assert len(said) == 1


async def test_e2e_47_the_reauth_notice_names_the_line_not_its_stops(env, monkeypatch):
    entry = await env.add_entry_via_flow(line="151")  # a line entry, made while the old API still answered
    old = "Line 151 · Rondo Daszyńskiego 01"
    env.hass.config_entries.async_update_entry(entry, title=old, options={"generated_title": old})
    monkeypatch.setattr("custom_components.ztm_warsaw.const.LEGACY_API_RETIRED", True)
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.settle()
    reauth = [f for f in env.hass.config_entries.flow.async_progress_by_handler(DOMAIN) if f["context"].get("source") == "reauth"]
    assert len(reauth) == 1
    assert reauth[0]["context"]["title_placeholders"]["name"] == "Line 151"


async def test_e2e_47_it_is_said_once_for_all_the_lines(env, retired, caplog):
    caplog.set_level(logging.INFO)
    await env.add_entry()
    await env.add_entry(line="523")
    said = [r for r in caplog.records if r.levelno >= logging.WARNING and "old API" in r.getMessage()]
    assert len(said) == 1


async def test_e2e_47_the_timetable_saved_before_is_kept_and_nothing_is_asked(env, monkeypatch):
    entry = await env.add_entry()  # the old API still answers: a timetable is fetched and saved
    await env.advance(seconds=31)
    shown = env.state().state
    assert shown != "unavailable"
    monkeypatch.setattr("custom_components.ztm_warsaw.const.LEGACY_API_RETIRED", True)
    env.city.reset_counts()
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.settle()
    assert env.state().state == shown, "the saved timetable is shown while it is valid"
    assert env.city.count() == 0
    assert env.hass.states.get(STATUS).state == "old_api"


async def test_e2e_47_a_token_works_as_before(env, retired):
    await env.add_entry(api_key=DEFAULT_TOKEN)
    assert env.state().state != "unavailable"
    assert env.hass.states.get(STATUS).state == "running"
    assert env.city.count("timetable", contract="new") >= 1


async def test_e2e_47_a_new_line_with_an_old_key_is_refused_with_the_reason(env, retired):
    result = await env.hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    done = await env.hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": DEFAULT_KEY, "manual": False}
    )
    assert done["type"] == "form"
    assert done["errors"] == {"base": "old_api_retired"}
    assert env.city.count() == 0


async def test_e2e_47_pasting_an_old_key_as_the_new_one_is_refused_with_the_reason(env, retired):
    entry = await env.add_entry()
    assert await config_flow.key_error(env.hass, entry, DEFAULT_KEY) == ("old_api_retired", False)
    assert await config_flow.key_error(env.hass, entry, DEFAULT_TOKEN) is not None  # a token is asked about at the City as before


def _reauths(env, entry):
    """The reauth flows open for an entry."""
    return env.hass.config_entries.flow.async_progress_by_handler(DOMAIN, match_context={"source": "reauth", "entry_id": entry.entry_id})


async def _token_line(env, line, token=DEFAULT_TOKEN):
    """A line that has a token (the City accepts it), so that an old key can be replaced by it."""
    env.city.valid_tokens.add(token)
    return await env.add_entry(line=line, api_key=token)


async def test_e2e_47_an_old_key_opens_a_reauth_so_the_integration_page_asks_for_a_token(env, retired):
    entry = await env.add_entry()
    assert len(_reauths(env, entry)) == 1
    await env.hass.config_entries.async_reload(entry.entry_id)
    await env.settle()
    assert len(_reauths(env, entry)) == 1, "reloading does not open a second one"


async def test_e2e_47_a_token_is_not_asked_for(env, retired):
    entry = await env.add_entry(api_key=DEFAULT_TOKEN)
    assert _reauths(env, entry) == []


async def test_e2e_47_pasting_a_token_in_the_reauth_replaces_the_old_key_and_ends_it(env, retired):
    entry = await env.add_entry()
    (flow,) = _reauths(env, entry)
    assert flow["step_id"] == "reauth_confirm", "no other line has a token: the form of the key at once"
    done = await env.hass.config_entries.flow.async_configure(flow["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert (done["type"], done["reason"]) == ("abort", "reauth_successful")
    assert entry.data["api_key"] == DEFAULT_TOKEN
    assert _reauths(env, entry) == []


async def test_e2e_47_the_reauth_offers_the_token_of_another_line(env, retired):
    await _token_line(env, "523")
    entry = await env.add_entry()
    (flow,) = _reauths(env, entry)
    assert flow["step_id"] == "reauth_menu"
    done = await env.hass.config_entries.flow.async_configure(flow["flow_id"], {"next_step_id": "reauth_reuse"})
    await env.settle()
    assert (done["type"], done["reason"]) == ("abort", "reauth_successful")
    assert entry.data["api_key"] == DEFAULT_TOKEN
    assert DEFAULT_TOKEN not in str(done)


async def test_e2e_47_with_several_tokens_the_reauth_asks_which_by_its_end_and_lines(env, retired):
    second = DEFAULT_TOKEN[:-4] + "wXyZ"
    await _token_line(env, "523")
    await _token_line(env, "411", second)
    entry = await env.add_entry()
    (flow,) = _reauths(env, entry)
    form = await env.hass.config_entries.flow.async_configure(flow["flow_id"], {"next_step_id": "reauth_reuse"})
    assert form["type"] == "form"
    assert form["step_id"] == "reauth_reuse"
    choices = list(form["data_schema"].schema.values())[0].container
    assert sorted(choices.values()) == sorted([f"…{DEFAULT_TOKEN[-4:]}  ·  523", "…wXyZ  ·  411"])
    pick = next(k for k, v in choices.items() if "411" in v)
    done = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"token": pick})
    await env.settle()
    assert done["type"] == "abort"
    assert entry.data["api_key"] == second


async def test_e2e_47_a_token_the_city_refuses_for_the_line_is_not_saved(env, retired):
    await _token_line(env, "523")
    entry = await env.add_entry()
    (flow,) = _reauths(env, entry)
    env.city.valid_tokens.discard(DEFAULT_TOKEN)
    done = await env.hass.config_entries.flow.async_configure(flow["flow_id"], {"next_step_id": "reauth_reuse"})
    assert (done["type"], done["reason"]) == ("abort", "reuse_rejected")
    assert entry.data["api_key"] == DEFAULT_KEY


async def test_e2e_47_reconfigure_offers_the_token_of_another_line_and_a_box_for_all_the_old_keys(env, retired):
    first = await env.add_entry()
    second = await env.add_entry(line="525")
    result = await first.start_reconfigure_flow(env.hass)
    assert result["type"] == "form", "no token on any line: the form at once"
    assert "all_lines" in [str(k) for k in result["data_schema"].schema], "another line has an old key: asked whether it gets the token too"
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    done = await env.hass.config_entries.flow.async_configure(result["flow_id"], {"api_key": DEFAULT_TOKEN, "all_lines": True})
    await env.settle()
    assert done["type"] == "abort"
    assert (first.data["api_key"], second.data["api_key"]) == (DEFAULT_TOKEN, DEFAULT_TOKEN)


async def test_e2e_47_reconfigure_with_a_token_elsewhere_starts_with_a_menu(env, retired):
    await _token_line(env, "523")
    entry = await env.add_entry()
    result = await entry.start_reconfigure_flow(env.hass)
    assert result["type"] == "menu"
    assert result["menu_options"] == ["reconfigure_form", "reconfigure_reuse"]
    done = await env.hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "reconfigure_reuse"})
    await env.settle()
    assert (done["type"], done["reason"]) == ("abort", "reconfigure_successful")
    assert entry.data["api_key"] == DEFAULT_TOKEN


async def test_e2e_47_configure_offers_the_token_of_another_line(env, retired):
    await _token_line(env, "523")
    entry = await env.add_entry()
    menu = await env.hass.config_entries.options.async_init(entry.entry_id)
    assert menu["type"] == "menu"
    assert menu["menu_options"] == ["paste", "reuse"]
    done = await env.hass.config_entries.options.async_configure(menu["flow_id"], {"next_step_id": "reuse"})
    await env.settle()
    assert done["type"] == "create_entry"
    assert entry.data["api_key"] == DEFAULT_TOKEN
    form_again = await env.hass.config_entries.options.async_init(entry.entry_id)
    assert form_again["type"] == "form", "the line has a token now: the form of the token"


async def test_e2e_47_the_menus_offer_the_form_of_the_key_and_come_back_when_asked_again(env, retired):
    await _token_line(env, "523")
    entry = await env.add_entry()
    (flow,) = _reauths(env, entry)
    again = await env.hass.config_entries.flow._progress[flow["flow_id"]].async_step_reauth_menu()  # the step Home Assistant wants for the menu
    assert again["type"] == "menu"
    form = await env.hass.config_entries.flow.async_configure(flow["flow_id"], {"next_step_id": "reauth_confirm"})
    assert (form["type"], form["step_id"]) == ("form", "reauth_confirm")

    result = await entry.start_reconfigure_flow(env.hass)
    assert result["type"] == "menu"
    handler = env.hass.config_entries.flow._progress[result["flow_id"]]
    assert (await handler.async_step_reconfigure_menu())["type"] == "menu"
    form = await env.hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "reconfigure_form"})
    assert (form["type"], form["step_id"]) == ("form", "reconfigure")

    menu = await env.hass.config_entries.options.async_init(entry.entry_id)
    assert (await env.hass.config_entries.options._progress[menu["flow_id"]].async_step_menu())["type"] == "menu"
    form = await env.hass.config_entries.options.async_configure(menu["flow_id"], {"next_step_id": "paste"})
    assert (form["type"], form["step_id"]) == ("form", "init")


async def test_e2e_47_a_token_of_one_line_listed_twice_names_the_line_once(env, retired):
    from custom_components.ztm_warsaw.config_flow import tokens_of_others

    await _token_line(env, "523")
    entry = await env.add_entry()
    other = next(e for e in env.hass.config_entries.async_entries(DOMAIN) if e.data.get("line") == "523")
    assert tokens_of_others(env.hass, entry) == [(DEFAULT_TOKEN, [other.data.get("line") or "523"])]
