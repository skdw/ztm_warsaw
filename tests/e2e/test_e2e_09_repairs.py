"""E2E-34: the token can be pasted in the Repairs notice about an old key (the fix flow of repairs.py)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.components.repairs.issue_handler import RepairsFlowManager
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.ztm_warsaw import repairs, config_flow
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
    assert notice is not None, "an ignored notice is kept, not deleted"
    assert notice.dismissed_version is not None
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


OTHER_LINE = "151"


async def _menu(env, manager, entry):
    """The menu a notice's flow starts with."""
    return await manager.async_init(DOMAIN, data={"issue_id": f"legacy_key_{entry.entry_id}"})


async def test_e2e_41_the_menu_offers_the_token_of_another_line_only_when_there_is_one(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = await _flows(env)
    assert (await _menu(env, manager, entry))["menu_options"] == ["token", "ignore"], "no other line has a token"
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    await env.add_entry_via_flow(line=OTHER_LINE, api_key=DEFAULT_TOKEN)
    again = await _menu(env, manager, entry)
    assert again["menu_options"] == ["token", "reuse", "ignore"]


async def test_e2e_41_using_the_token_of_another_line_replaces_the_old_key_without_showing_it(env):
    entry = await env.add_entry_via_flow(line=LINE)
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    await env.add_entry_via_flow(line=OTHER_LINE, api_key=DEFAULT_TOKEN)
    manager = await _flows(env)
    menu = await _menu(env, manager, entry)
    done = await manager.async_configure(menu["flow_id"], {"next_step_id": "reuse"})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert entry.data["api_key"] == DEFAULT_TOKEN
    assert DEFAULT_TOKEN not in str(done)
    assert _notice(env, entry) is None


async def test_e2e_41_a_token_the_city_does_not_accept_for_this_line_is_not_saved(env):
    entry = await env.add_entry_via_flow(line=LINE)
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    await env.add_entry_via_flow(line=OTHER_LINE, api_key=DEFAULT_TOKEN)
    env.city.valid_tokens.discard(DEFAULT_TOKEN)  # the City stops accepting it
    manager = await _flows(env)
    menu = await _menu(env, manager, entry)
    done = await manager.async_configure(menu["flow_id"], {"next_step_id": "reuse"})
    assert (done["type"], done["reason"]) == ("abort", "reuse_rejected")
    assert entry.data["api_key"] == DEFAULT_KEY


async def test_e2e_41_pasting_a_token_can_give_it_to_every_line_that_still_has_an_old_key(env):
    first = await env.add_entry_via_flow(line=LINE)
    second = await env.add_entry_via_flow(line=OTHER_LINE)
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{first.entry_id}")
    assert "all_lines" in [str(k) for k in form["data_schema"].schema], "asked because another line has an old key"
    done = await manager.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})  # the box is ticked by default
    await env.settle()
    assert done["type"] == "create_entry", done
    assert (first.data["api_key"], second.data["api_key"]) == (DEFAULT_TOKEN, DEFAULT_TOKEN)
    assert _notice(env, first) is None
    assert _notice(env, second) is None


async def test_e2e_41_unticking_the_box_leaves_the_other_lines_alone(env):
    first = await env.add_entry_via_flow(line=LINE)
    second = await env.add_entry_via_flow(line=OTHER_LINE)
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{first.entry_id}")
    await manager.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN, "all_lines": False})
    await env.settle()
    assert (first.data["api_key"], second.data["api_key"]) == (DEFAULT_TOKEN, DEFAULT_KEY)


async def test_e2e_41_a_single_line_with_an_old_key_is_not_asked_about_other_lines(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{entry.entry_id}")
    assert [str(k) for k in form["data_schema"].schema] == ["api_key"]


async def test_e2e_41_a_line_for_which_the_city_refuses_the_token_keeps_its_old_key_while_the_others_change(env):
    first = await env.add_entry_via_flow(line=LINE)
    second = await env.add_entry_via_flow(line=OTHER_LINE)
    manager = await _flows(env)
    form = await _open(manager, f"legacy_key_{first.entry_id}")

    async def refuse_for_the_second(hass, entry, key):
        """The City accepts the token for the first line and refuses it for the second."""
        return ("invalid_token_or_unavailable", False) if entry.entry_id == second.entry_id else (None, True)

    with patch.object(repairs, "key_error", refuse_for_the_second), patch.object(config_flow, "key_error", refuse_for_the_second):
        await manager.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN, "all_lines": True})
        await env.settle()
    assert (first.data["api_key"], second.data["api_key"]) == (DEFAULT_TOKEN, DEFAULT_KEY)


async def test_e2e_41_the_steps_abort_when_their_entry_or_a_donor_token_is_gone(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = await _flows(env)
    menu = await _menu(env, manager, entry)
    handler = manager._progress[menu["flow_id"]]  # the running flow, to call a step the menu would not offer
    no_donor = await handler.async_step_reuse()
    assert (no_donor["type"], no_donor["reason"]) == ("abort", "unknown")
    await env.hass.config_entries.async_remove(entry.entry_id)
    gone = await handler.async_step_token()
    assert (gone["type"], gone["reason"]) == ("abort", "unknown")
    gone_reuse = await handler.async_step_reuse()
    assert (gone_reuse["type"], gone_reuse["reason"]) == ("abort", "unknown")


THIRD_LINE = "523"


async def _two_tokens(env):
    """A line with an old key, and two other lines that have different tokens; returns the entry, the second token and the flow manager."""
    entry = await env.add_entry_via_flow(line=LINE)
    second_token = DEFAULT_TOKEN[:-4] + "wXyZ"
    env.city.valid_tokens.update({DEFAULT_TOKEN, second_token})
    await env.add_entry_via_flow(line=OTHER_LINE, api_key=DEFAULT_TOKEN)
    await env.add_entry_via_flow(line=THIRD_LINE, api_key=second_token)
    return entry, second_token, await _flows(env)


async def test_e2e_41_with_several_tokens_the_user_picks_one_by_its_end_and_its_lines(env):
    entry, second_token, manager = await _two_tokens(env)
    menu = await _menu(env, manager, entry)
    form = await manager.async_configure(menu["flow_id"], {"next_step_id": "reuse"})
    assert form["type"] == "form"
    assert form["step_id"] == "reuse"
    choices = list(form["data_schema"].schema.values())[0].container
    assert len(choices) == 2
    assert any(label.endswith(f"{DEFAULT_TOKEN[-4:]}  ·  {OTHER_LINE}") for label in choices.values())
    assert any(label.endswith(f"wXyZ  ·  {THIRD_LINE}") for label in choices.values())
    assert not any(DEFAULT_TOKEN in label or second_token in label for label in choices.values()), "only the end of a token is shown"
    pick = next(key for key, label in choices.items() if THIRD_LINE in label)
    done = await manager.async_configure(form["flow_id"], {"token": pick})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert entry.data["api_key"] == second_token


async def test_e2e_41_a_token_picked_but_not_accepted_for_the_line_is_not_saved(env):
    entry, second_token, manager = await _two_tokens(env)
    menu = await _menu(env, manager, entry)
    form = await manager.async_configure(menu["flow_id"], {"next_step_id": "reuse"})
    choices = list(form["data_schema"].schema.values())[0].container
    env.city.valid_tokens.discard(second_token)
    done = await manager.async_configure(form["flow_id"], {"token": next(k for k, v in choices.items() if THIRD_LINE in v)})
    assert (done["type"], done["reason"]) == ("abort", "reuse_rejected")
    assert entry.data["api_key"] == DEFAULT_KEY


async def test_e2e_41_an_answer_that_is_not_one_of_the_choices_shows_the_choices_again(env):
    entry, _second_token, manager = await _two_tokens(env)
    menu = await _menu(env, manager, entry)
    handler = manager._progress[menu["flow_id"]]  # the running flow: the form itself refuses an answer that is not listed
    again = await handler.async_step_reuse({"token": "7"})
    assert again["type"] == "form"
    assert again["step_id"] == "reuse"
    assert entry.data["api_key"] == DEFAULT_KEY
