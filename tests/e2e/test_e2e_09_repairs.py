"""E2E-34: the token can be pasted in the Repairs notice about an old key (the fix flow of repairs.py)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.components.repairs.issue_handler import RepairsFlowManager
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN

pytestmark = pytest.mark.e2e

LINE = "525"
OTHER_KEY = "22222222-3333-4444-8555-666666666666"  # gitleaks:allow  (synthetic)


async def _flows(env) -> RepairsFlowManager:
    """The manager Home Assistant uses to run the fix flow of a notice, with the repairs integration set up as in a real run."""
    assert await async_setup_component(env.hass, "repairs", {})
    return RepairsFlowManager(env.hass)


async def _open(manager, issue_id):
    """Start the fix flow of a notice and take the menu's *Paste a token*: the form of the token, or whatever ends the flow earlier."""
    first = await manager.async_init(DOMAIN, data={"issue_id": issue_id})
    if first["type"] != "menu":
        return first
    return await manager.async_configure(first["flow_id"], {"next_step_id": "token"})


def _notice(env, entry, key="legacy_key"):
    """The Repairs notice about the old key of this entry (None when there is none)."""
    return ir.async_get(env.hass).async_get_issue(DOMAIN, f"{key}_{entry.entry_id}")


async def test_e2e_34_the_notice_of_a_line_is_fixable_and_carries_its_entry(env):
    entry = await env.add_entry_via_flow(line=LINE)
    notice = _notice(env, entry)
    assert notice is not None
    assert (notice.is_fixable, notice.translation_key, notice.data) == (True, "legacy_key_line", {"entry_id": entry.entry_id})


async def test_e2e_34_pasting_a_token_in_the_notice_replaces_the_key_of_the_whole_line(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await env.submit_flow(line=LINE, stop_nr="02")
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{entry.entry_id}")
    assert (form["type"], form["step_id"]) == ("form", "token")
    assert form["description_placeholders"] == {"line": LINE, "portal": "https://dane.um.warszawa.pl/pl/key-api"}
    with patch.object(env.hass.config_entries, "async_reload", wraps=env.hass.config_entries.async_reload) as reload:
        done = await manager.async_configure(form["flow_id"], {"api_key": f" {DEFAULT_TOKEN} "})
        await env.settle()
    assert done["type"] == "create_entry", done
    assert entry.data["api_key"] == DEFAULT_TOKEN
    assert reload.call_count == 1
    assert entry.state is ConfigEntryState.LOADED
    assert _notice(env, entry) is None, "an entry with a token has nothing to switch to"


async def test_e2e_34_a_key_the_city_does_not_accept_is_refused_and_the_notice_stays(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{entry.entry_id}")
    done = await manager.async_configure(form["flow_id"], {"api_key": "not a key"})
    assert (done["type"], done["errors"]) == ("form", {"base": "invalid_api_key"})
    done = await manager.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN + "9"})  # a token the City does not know
    assert done["type"] == "form"
    assert done["errors"] == {"base": "invalid_token_or_unavailable"}
    assert entry.data["api_key"] == DEFAULT_KEY
    assert _notice(env, entry) is not None


async def test_e2e_34_the_notice_of_a_1_1_x_entry_is_fixable_too(env):
    entry = await env.add_entry(line="151")  # one stop, the shape of 1.1.x
    notice = _notice(env, entry)
    assert (notice.is_fixable, notice.translation_key, notice.data) == (True, "legacy_key", {"entry_id": entry.entry_id})
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{entry.entry_id}")
    done = await manager.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert entry.data["api_key"] == DEFAULT_TOKEN
    assert entry.version == 1
    assert _notice(env, entry) is None


async def test_e2e_34_a_notice_whose_entry_is_gone_aborts_the_flow(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = await _flows(env)
    issue_id = f"legacy_key_{entry.entry_id}"
    await env.hass.config_entries.async_remove(entry.entry_id)
    ir.async_create_issue(  # the notice outlived its entry: one more run of the flow must not fail
        env.hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        data={"entry_id": entry.entry_id},
        severity=ir.IssueSeverity.WARNING,
        translation_key="legacy_key_line",
        translation_placeholders={"line": LINE, "portal": "x"},
    )
    form = await _open(manager, issue_id)
    assert (form["type"], form["reason"]) == ("abort", "unknown")


async def test_e2e_34_a_notice_without_an_entry_id_aborts_the_flow(env):
    assert await async_setup_component(env.hass, DOMAIN, {})  # the integration is loaded, so its fix flow is the one that runs
    manager = await _flows(env)
    ir.async_create_issue(
        env.hass,
        DOMAIN,
        "legacy_key_orphan",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="legacy_key_line",
        translation_placeholders={"line": LINE, "portal": "x"},
    )
    form = await _open(manager, "legacy_key_orphan")
    assert (form["type"], form["reason"]) == ("abort", "unknown")


async def test_e2e_34_a_key_that_works_for_a_line_that_does_not_run_today_is_accepted(env):
    """A weekday-only line on a Saturday: the key is judged by the key, as in Configure."""
    env.move_to("2026-10-17 12:00")
    entry = await env.add_entry(line="411")
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{entry.entry_id}")
    done = await manager.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert entry.data["api_key"] == DEFAULT_TOKEN


async def test_e2e_34_an_entry_whose_data_cannot_be_read_is_not_changed_blindly(env):
    entry = await env.add_entry(data={"api_key": DEFAULT_KEY}, setup=False)  # no stop: a 1.1.x entry that cannot be run
    assert await async_setup_component(env.hass, DOMAIN, {})
    manager = await _flows(env)
    ir.async_create_issue(
        env.hass,
        DOMAIN,
        "legacy_key_broken",
        is_fixable=True,
        data={"entry_id": entry.entry_id},
        severity=ir.IssueSeverity.WARNING,
        translation_key="legacy_key",
        translation_placeholders={"line": "?", "stop": "?", "portal": "x"},
    )
    form = await _open(manager, "legacy_key_broken")
    assert (form["type"], form["reason"]) == ("abort", "unknown")
    assert entry.data["api_key"] == DEFAULT_KEY


async def test_e2e_34_another_old_key_leaves_the_notice_and_a_token_ends_it(env):
    """Home Assistant deletes the notice when the flow finishes; it is the setup after the reload that decides if it is back."""
    env.city.valid_keys.add(OTHER_KEY)
    entry = await env.add_entry_via_flow(line=LINE)
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{entry.entry_id}")
    done = await manager.async_configure(form["flow_id"], {"api_key": OTHER_KEY})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert entry.data["api_key"] == OTHER_KEY
    assert _notice(env, entry) is not None, "still an old key: the reload makes the notice again"
    form = await _open(manager, f"legacy_key_{entry.entry_id}")
    await manager.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert _notice(env, entry) is None, "a token: the reload does not make it again"


async def test_e2e_34_the_flow_closes_a_reauth_that_was_waiting_for_the_key(env):
    entry = await env.add_entry_via_flow(line=LINE)
    entry.async_start_reauth(env.hass)
    await env.settle()
    assert env.hass.config_entries.flow.async_progress_by_handler(DOMAIN, match_context={"source": "reauth"})
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{entry.entry_id}")
    done = await manager.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert not env.hass.config_entries.flow.async_progress_by_handler(DOMAIN, match_context={"source": "reauth"})


async def test_e2e_34_a_line_without_stops_takes_a_key_checked_by_its_shape(env):
    entry = await env.add_entry_via_flow(line=LINE)
    (only,) = entry.subentries
    env.hass.config_entries.async_remove_subentry(entry, only)
    await env.settle()
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{entry.entry_id}")
    assert form["description_placeholders"]["line"] == LINE  # the line is known without a stop
    done = await manager.async_configure(form["flow_id"], {"api_key": "not a key"})
    assert done["errors"] == {"base": "invalid_api_key"}
    done = await manager.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert entry.data["api_key"] == DEFAULT_TOKEN


async def test_e2e_34_the_flow_starts_with_a_menu_of_pasting_a_token_or_ignoring_the_notice(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = await _flows(env)
    menu = await manager.async_init(DOMAIN, data={"issue_id": f"legacy_key_{entry.entry_id}"})
    assert (menu["type"], menu["step_id"], menu["menu_options"]) == ("menu", "init", ["token", "ignore"])
    assert menu["description_placeholders"]["line"] == LINE


async def test_e2e_34_ignoring_the_notice_keeps_the_old_key_and_the_notice_stays_ignored(env):
    """A fixable notice has no Ignore button in the Repairs list, so the flow offers it; the entry is not touched."""
    entry = await env.add_entry_via_flow(line=LINE)
    manager = await _flows(env)
    menu = await manager.async_init(DOMAIN, data={"issue_id": f"legacy_key_{entry.entry_id}"})
    done = await manager.async_configure(menu["flow_id"], {"next_step_id": "ignore"})
    assert (done["type"], done["reason"]) == ("abort", "ignored")
    notice = _notice(env, entry)
    assert notice is not None and notice.dismissed_version is not None
    assert entry.data["api_key"] == DEFAULT_KEY
    await env.hass.config_entries.async_reload(entry.entry_id)  # the notice is created again on a reload: it stays ignored
    await env.settle()
    assert _notice(env, entry).dismissed_version is not None
    assert entry.state is ConfigEntryState.LOADED


async def test_e2e_34_an_ignored_notice_does_not_hide_the_reauth_of_a_key_the_city_rejects(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = await _flows(env)
    menu = await manager.async_init(DOMAIN, data={"issue_id": f"legacy_key_{entry.entry_id}"})
    await manager.async_configure(menu["flow_id"], {"next_step_id": "ignore"})
    env.city.valid_keys.discard(DEFAULT_KEY)  # the City stops accepting the old key
    await env.hass.config_entries.async_reload(entry.entry_id)
    await env.advance(minutes=2)  # three rejections at setup: the entry is in an error state and reauth is open
    reauth = env.hass.config_entries.flow.async_progress_by_handler(DOMAIN, match_context={"source": "reauth"})
    assert len(reauth) == 1, "the ignored notice is about the old key; a rejected key is a reauth of its own"
    assert _notice(env, entry).dismissed_version is not None
