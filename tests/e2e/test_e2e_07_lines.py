"""E2E-32: a line is one entry and its stops are subentries (new in 1.2.0), next to the 1.1.x entries of one stop."""

from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from custom_components.ztm_warsaw.config_flow import ZtmWarsawConfigFlow, ZtmStopSubentryFlow
from custom_components.ztm_warsaw.const import DOMAIN
from custom_components.ztm_warsaw import config_flow
from custom_components.ztm_warsaw.client import ZTMStopClient
from custom_components.ztm_warsaw.coordinator import ZTMStopCoordinator, store_key

from .helpers import subentry_of
from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN, stop_name_for

NEW_KEY = "22222222-3333-4444-8555-666666666666"  # gitleaks:allow  (synthetic)

pytestmark = pytest.mark.e2e

LINE = "525"  # runs at 7009/01, 7009/02 and 7013/01 in the fake city


async def _line_with_three_stops(env):
    """Create the entry of line 525 through the flow and add its other two stops through the flow too; returns the entry."""
    entry = await env.add_entry_via_flow(line=LINE)
    for stop_id, stop_nr in (("7009", "02"), ("7013", "01")):
        result = await env.submit_flow(line=LINE, stop_id=stop_id, stop_nr=stop_nr)
        assert (result["type"], result["reason"]) == ("abort", "stop_added"), result
    return entry


async def test_e2e_32_more_stops_of_a_line_go_into_its_entry(env):
    entry = await _line_with_three_stops(env)
    assert env.hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.state is ConfigEntryState.LOADED
    stops = sorted((s.data["busstop_id"], s.data["busstop_nr"]) for s in entry.subentries.values())
    assert stops == [(7009, "01"), (7009, "02"), (7013, "01")]
    for stop_id, stop_nr in (("7009", "01"), ("7009", "02"), ("7013", "01")):
        assert env.state(LINE, stop_id, stop_nr).state not in ("unknown", "unavailable"), (stop_id, stop_nr)


async def test_e2e_32_every_entity_belongs_to_its_stop_and_every_stop_has_a_device(env):
    entry = await _line_with_three_stops(env)
    by_stop = {sid: sub.data["busstop_id"] for sid, sub in entry.subentries.items()}
    entities = er.async_entries_for_config_entry(env.entity_registry, entry.entry_id)
    assert len(entities) == 21  # the sensor, its status, its diagnostic sensor, the calendar and Next 1 to 3, for each of three stops
    for entity in entities:
        assert entity.config_subentry_id in by_stop
        assert f"_from_{by_stop[entity.config_subentry_id]}_" in entity.unique_id
    # the unique IDs and entity IDs are the ones a stop of its own entry had
    assert env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7013_01") is not None
    devices = dr.async_entries_for_config_entry(env.device_registry, entry.entry_id)
    assert sorted(next(iter(d.identifiers))[1] for d in devices) == [
        f"line_{LINE}_7009_01",
        f"line_{LINE}_7009_02",
        f"line_{LINE}_7013_01",
    ]  # one device per stop: a device belongs to one subentry
    for device in devices:
        assert {e.config_subentry_id for e in er.async_entries_for_device(env.entity_registry, device.id)} == {
            subentry_of(device, entry.entry_id)
        }


async def test_e2e_32_adding_a_stop_reloads_the_entry_once(env):
    entry = await env.add_entry_via_flow(line=LINE)
    with patch.object(env.hass.config_entries, "async_reload", wraps=env.hass.config_entries.async_reload) as reload:
        result = await env.submit_flow(line=LINE, stop_nr="02")
        await env.settle()
    assert (result["type"], result["reason"]) == ("abort", "stop_added")
    assert reload.call_count == 1
    assert entry.state is ConfigEntryState.LOADED
    assert env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_02") is not None


async def test_e2e_32_add_stop_on_the_entry_asks_for_the_stop_by_name_then_the_pole(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    assert (form["type"], form["step_id"]) == ("form", "user")
    assert [str(k) for k in form["data_schema"].schema] == ["stop", "manual"]
    stops = await manager.async_configure(form["flow_id"], {"stop": stop_name_for("7009")[:12]})
    assert (stops["type"], stops["step_id"]) == ("form", "stop"), "the name fits more than one stop: which one is asked first"
    poles = await manager.async_configure(stops["flow_id"], {"stop": "7009"})
    assert (poles["type"], poles["step_id"]) == ("form", "pole")
    assert {o["value"] for o in poles["data_schema"].schema["pole"].config["options"]} == {"7009/01", "7009/02"}
    done = await manager.async_configure(poles["flow_id"], {"pole": "7009/02"})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert sorted(s.data["busstop_nr"] for s in entry.subentries.values()) == ["01", "02"]
    assert env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_02") is not None

async def test_e2e_32_add_stop_refuses_a_stop_the_line_has_and_a_stop_it_does_not_serve(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await env.add_stop_form(entry)
    done = await manager.async_configure(form["flow_id"], {"busstop_id": 7009, "busstop_nr": "01"})
    assert (done["type"], done["reason"]) == ("abort", "already_configured")
    form = await env.add_stop_form(entry)
    done = await manager.async_configure(form["flow_id"], {"busstop_id": 7009, "busstop_nr": "9"})
    assert (done["type"], done["errors"]) == ("form", {"base": "invalid_stop_number"})
    assert len(entry.subentries) == 1


async def test_e2e_32_the_same_stop_is_refused_even_when_a_1_1_x_entry_has_it(env):
    await env.add_entry(line=LINE)  # shaped like a 1.1.x entry: one stop, no subentries
    again = await env.submit_flow(line=LINE)
    assert (again["type"], again["reason"]) == ("abort", "already_configured")
    other = await env.submit_flow(line=LINE, stop_nr="02")  # another pole: a line of its own, the old entry is untouched
    assert other["type"] == "create_entry"
    assert len(env.hass.config_entries.async_entries(DOMAIN)) == 2
    assert env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_01") is not None
    assert env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_02") is not None


async def test_e2e_32_removing_a_stop_removes_its_entities_and_its_stored_answers(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await env.submit_flow(line=LINE, stop_nr="02")
    second = next(sid for sid, sub in entry.subentries.items() if sub.data["busstop_nr"] == "02")
    env.hass.config_entries.async_remove_subentry(entry, second)
    await env.settle()
    assert entry.state is ConfigEntryState.LOADED
    assert env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_02") is None
    assert env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_01") is not None
    assert await Store(env.hass, 1, store_key(second)).async_load() is None


async def test_e2e_32_the_stops_of_a_line_are_titled_with_their_names_unless_the_user_renamed_them(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await env.submit_flow(line=LINE, stop_id="7013", stop_nr="01")
    titles = {s.data["busstop_id"]: s.title for s in entry.subentries.values()}
    assert titles == {7009: f"{stop_name_for('7009')} 01", 7013: f"{stop_name_for('7013')} 01"}
    mine = next(s for s in entry.subentries.values() if s.data["busstop_id"] == 7013)
    env.hass.config_entries.async_update_subentry(entry, mine, title="Home")
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.settle()
    assert next(s.title for s in entry.subentries.values() if s.data["busstop_id"] == 7013) == "Home"


async def test_e2e_32_one_stop_that_fails_stops_the_line_from_loading_and_leaves_nothing_running(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await env.submit_flow(line=LINE, stop_nr="02")
    assert await env.hass.config_entries.async_unload(entry.entry_id)
    failing = AsyncMock(side_effect=ConfigEntryNotReady("The City of Warsaw did not answer in time"))
    with (
        patch.object(ZTMStopCoordinator, "async_config_entry_first_refresh", failing),
        patch.object(ZTMStopCoordinator, "async_shutdown", autospec=True) as shutdown,
    ):
        assert not await env.hass.config_entries.async_setup(entry.entry_id)
        await env.settle()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert failing.await_count == 2  # both stops asked together
    stopped = {call.args[0] for call in shutdown.await_args_list}
    assert {c.stop_nr for c in stopped} == {"01", "02"}, "both stops were stopped when one failed"
    assert not hasattr(entry, "runtime_data")


async def test_e2e_32_configure_replaces_the_key_of_the_whole_line(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await env.submit_flow(line=LINE, stop_nr="02")
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    assert form["step_id"] == "init"  # an old key: nudged to a token
    with patch.object(env.hass.config_entries, "async_reload", wraps=env.hass.config_entries.async_reload) as reload:
        done = await flow.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
        await env.settle()
    assert done["type"] == "create_entry", done
    assert entry.data["api_key"] == DEFAULT_TOKEN
    assert reload.call_count == 1
    assert env.city.count(contract="new") > 0
    form = await flow.async_init(entry.entry_id)
    assert form["step_id"] == "token"


async def test_e2e_32_an_old_key_gets_one_notice_for_the_line_and_a_token_none(env):
    old = await env.add_entry_via_flow(line=LINE)
    await env.submit_flow(line=LINE, stop_nr="02")
    token = await env.add_entry_via_flow(line="N25", api_key=DEFAULT_TOKEN)
    issues = ir.async_get(env.hass)
    notice = issues.async_get_issue(DOMAIN, f"legacy_key_{old.entry_id}")
    assert notice is not None
    assert notice.translation_key == "legacy_key_line"
    assert notice.translation_placeholders == {"line": LINE, "portal": "https://dane.um.warszawa.pl/pl/key-api"}
    assert issues.async_get_issue(DOMAIN, f"legacy_key_{token.entry_id}") is None


async def test_e2e_32_diagnostics_list_every_stop_and_never_the_key(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await env.submit_flow(line=LINE, stop_nr="02")
    module = importlib.import_module("custom_components.ztm_warsaw.diagnostics")
    result = await module.async_get_config_entry_diagnostics(env.hass, entry)
    assert len(result["stops"]) == 2
    assert all(stop["coordinator"]["last_update_success"] for stop in result["stops"])
    assert result["entry"]["data"]["api_key"] == "**REDACTED**"
    assert DEFAULT_KEY not in repr(result)


async def test_e2e_32_only_a_line_offers_add_stop(env):
    old = await env.add_entry(line="151")  # shaped like a 1.1.x entry
    line = await env.add_entry_via_flow(line=LINE)
    assert ZtmWarsawConfigFlow.async_get_supported_subentry_types(old) == {}
    assert ZtmWarsawConfigFlow.async_get_supported_subentry_types(line) == {"stop": ZtmStopSubentryFlow}


async def test_e2e_32_a_stop_added_to_a_line_is_asked_with_the_key_the_line_has(env):
    entry = await env.add_entry_via_flow(line=LINE)
    result = await env.submit_flow(line=LINE, stop_nr="02", api_key=NEW_KEY)  # a key the City does not know
    assert (result["type"], result["reason"]) == ("abort", "stop_added")
    assert entry.data["api_key"] == DEFAULT_KEY  # the typed key is not the line's
    assert env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_02") is not None


async def test_e2e_32_a_1_1_x_entry_keeps_its_shape_through_configure(env):
    entry = await env.add_entry(line="151")
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    assert form["step_id"] == "init"
    done = await flow.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert entry.version == 1
    assert dict(entry.data) == {
        "api_key": DEFAULT_TOKEN,
        "busstop_id": 7009,
        "busstop_nr": "01",
        "line": "151",
        "departures": 1,
    }
    assert not entry.subentries
    assert entry.state is ConfigEntryState.LOADED
    assert env.hass.states.get("sensor.line_151_from_7009_01") is not None


async def test_e2e_32_a_stop_the_city_does_not_answer_for_does_not_hold_back_the_line(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await env.submit_flow(line=LINE, stop_nr="02")
    assert await env.hass.config_entries.async_unload(entry.entry_id)
    original = ZTMStopCoordinator.async_config_entry_first_refresh

    async def second_stop_fails(self):
        """First refresh that fails like an unanswered City for stop 02 and behaves normally for the others."""
        if self.stop_nr == "02":
            raise ConfigEntryNotReady("The City of Warsaw did not answer in time")
        await original(self)

    with patch.object(ZTMStopCoordinator, "async_config_entry_first_refresh", second_stop_fails):
        assert await env.hass.config_entries.async_setup(entry.entry_id)
        await env.settle()
    assert entry.state is ConfigEntryState.LOADED
    assert env.state(LINE, 7009, "01").state not in ("unknown", "unavailable")
    assert env.state(LINE, 7009, "02").state == "unavailable"
    coordinator = entry.runtime_data["units"]
    second = next(rt["coordinator"] for rt in coordinator.values() if rt["coordinator"].stop_nr == "02")
    assert second._started  # it runs like the others: it asks for the stop's name and wakes at the day change
    assert second._flip_unsub is not None
    await second.async_refresh()  # the hourly refresh, once the City answers
    await env.settle()
    assert env.state(LINE, 7009, "02").state not in ("unknown", "unavailable")


async def test_e2e_32_a_rejected_key_on_one_stop_is_the_lines_to_solve(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await env.submit_flow(line=LINE, stop_nr="02")
    assert await env.hass.config_entries.async_unload(entry.entry_id)
    original = ZTMStopCoordinator.async_config_entry_first_refresh

    async def second_stop_is_rejected(self):
        """First refresh that fails like a rejected key for stop 02 and behaves normally for the others."""
        if self.stop_nr == "02":
            raise ConfigEntryAuthFailed("rejected")
        await original(self)

    with (
        patch.object(ZTMStopCoordinator, "async_config_entry_first_refresh", second_stop_is_rejected),
        patch.object(
            ZTMStopCoordinator, "async_shutdown", autospec=True, side_effect=ZTMStopCoordinator.async_shutdown
        ) as shutdown,
    ):
        assert not await env.hass.config_entries.async_setup(entry.entry_id)
        await env.settle()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    stopped = {call.args[0].stop_nr for call in shutdown.await_args_list}
    assert stopped == {"01", "02"}, "the stop that answered is stopped too, not left running without an entry"


async def test_e2e_32_a_line_without_stops_still_changes_its_key_and_keeps_its_notice(env):
    entry = await env.add_entry_via_flow(line=LINE)
    (only,) = entry.subentries
    env.hass.config_entries.async_remove_subentry(entry, only)
    await env.settle()
    assert entry.state is ConfigEntryState.LOADED
    issues = ir.async_get(env.hass)
    assert issues.async_get_issue(DOMAIN, f"legacy_key_{entry.entry_id}") is not None  # the key is still an old one
    env.city.valid_tokens.add(DEFAULT_TOKEN)
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    done = await flow.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert entry.data["api_key"] == DEFAULT_TOKEN
    assert issues.async_get_issue(DOMAIN, f"legacy_key_{entry.entry_id}") is None
    refused = await flow.async_configure((await flow.async_init(entry.entry_id))["flow_id"], {"api_key": "not a key"})
    assert refused["errors"] == {"base": "invalid_api_key"}


async def test_e2e_32_renaming_a_stop_does_not_reload_the_line(env):
    entry = await env.add_entry_via_flow(line=LINE)
    (only,) = entry.subentries.values()
    with patch.object(env.hass.config_entries, "async_reload", wraps=env.hass.config_entries.async_reload) as reload:
        env.hass.config_entries.async_update_subentry(entry, only, title="Home")
        await env.settle()
    assert reload.call_count == 0
    assert env.hass.states.get(f"sensor.line_{LINE.lower()}_from_7009_01") is not None


async def test_e2e_32_a_stop_that_another_flow_added_meanwhile_is_refused_not_a_failure(env):
    entry = await env.add_entry_via_flow(line=LINE)
    with patch.object(env.hass.config_entries, "async_add_subentry", side_effect=HomeAssistantError("exists")):
        result = await env.submit_flow(line=LINE, stop_nr="02")  # joins the line, but the stop is there by then
    assert (result["type"], result["reason"]) == ("abort", "already_configured")
    assert len(entry.subentries) == 1


async def test_e2e_32_add_stop_refuses_a_stop_that_another_flow_added_while_the_city_was_asked(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await env.add_stop_form(entry)
    real = config_flow.error_for

    async def another_flow_finishes_first(hass, user_input, **kwargs):
        """Check the stop as usual, then add the same stop as another flow would have, before this flow finishes."""
        result = await real(hass, user_input, **kwargs)
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                subentry_type="stop",
                title="7009/02",
                data={"busstop_id": 7009, "busstop_nr": "02"},
                unique_id="7009_02",
            ),
        )
        return result

    with patch.object(config_flow, "error_for", another_flow_finishes_first):
        done = await manager.async_configure(form["flow_id"], {"busstop_id": 7009, "busstop_nr": "02"})
    assert (done["type"], done["reason"]) == ("abort", "already_configured")
    assert len(entry.subentries) == 2


async def test_e2e_32_add_stop_on_an_entry_without_a_key_aborts(env):
    entry = MockConfigEntry(domain=DOMAIN, version=2, title="Line 525", data={"line": LINE})
    entry.add_to_hass(env.hass)
    form = await env.hass.config_entries.subentries.async_init((entry.entry_id, "stop"), context={"source": "user"})
    assert (form["type"], form["reason"]) == ("abort", "unknown")


async def test_e2e_32_a_stop_name_that_arrives_after_the_setup_titles_the_stop_then(env):
    with patch.object(ZTMStopClient, "get_stop_name", AsyncMock(return_value=None)):
        entry = await env.add_entry_via_flow(line=LINE)
    (stop,) = entry.subentries.values()
    assert stop.title == "7009/01"
    (runtime,) = entry.runtime_data["units"].values()
    with patch.object(ZTMStopClient, "get_stop_name", AsyncMock(return_value=None)):
        await runtime["coordinator"].async_refresh()  # the catalogue still does not answer: nothing to show yet
    assert stop.title == "7009/01"
    await runtime["coordinator"].async_refresh()  # now it does
    await env.settle()
    assert stop.title == f"{stop_name_for('7009')} 01"


async def test_e2e_32_the_stop_id_is_a_text_field_that_starts_empty_in_both_dialogs(env):
    """A number field starts as 0 in the form; a text that must be a number starts empty."""
    entry = await env.add_entry_via_flow(line=LINE)
    first = await env.manual_form()
    add_stop = await env.add_stop_form(entry)
    for form in (first, add_stop):
        field, validator = next((k, v) for k, v in form["data_schema"].schema.items() if str(k) == "busstop_id")
        assert validator.type is str  # a text field: the frontend shows no 0 in it
        assert field.default is vol.UNDEFINED


@pytest.mark.parametrize("typed", ["", "abc", "70 09", "-7009", "7009.0", "٧٠٠٩", "1" * 5000, "1234567890"])
async def test_e2e_32_a_stop_id_that_is_not_a_number_is_refused_in_both_dialogs(env, typed):
    entry = await env.add_entry_via_flow(line=LINE)
    flow = env.hass.config_entries.flow
    form = await env.manual_form()
    done = await flow.async_configure(
        form["flow_id"], {"api_key": DEFAULT_KEY, "busstop_id": typed, "busstop_nr": "02", "line": LINE}
    )
    assert (done["type"], done["errors"]) == ("form", {"base": "invalid_stop_id"})
    manager = env.hass.config_entries.subentries
    form = await env.add_stop_form(entry)
    done = await manager.async_configure(form["flow_id"], {"busstop_id": typed, "busstop_nr": "02"})
    assert (done["type"], done["errors"]) == ("form", {"base": "invalid_stop_id"})
    assert done["description_placeholders"] == {"line": LINE}, "the title of the form names the line again"
    assert len(entry.subentries) == 1


async def test_e2e_32_a_stop_id_with_spaces_around_it_is_stored_as_the_number(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await env.add_stop_form(entry)
    done = await manager.async_configure(form["flow_id"], {"busstop_id": " 7009 ", "busstop_nr": "02"})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert sorted((s.data["busstop_id"], s.data["busstop_nr"]) for s in entry.subentries.values()) == [(7009, "01"), (7009, "02")]


async def test_e2e_38_a_line_is_titled_with_the_line_only_however_many_stops_it_has(env):
    entry = await env.add_entry_via_flow(line=LINE)
    await env.submit_flow(line=LINE, stop_nr="02")
    await env.settle()
    assert len(entry.subentries) == 2
    assert entry.title == f"Line {LINE}", "the stops are listed under the line; naming them in the title would grow the list"
    assert not entry.options


async def test_e2e_38_a_title_the_user_chose_is_kept(env):
    entry = await env.add_entry_via_flow(line=LINE)
    env.hass.config_entries.async_update_entry(entry, title="My bus")
    await env.submit_flow(line=LINE, stop_nr="02")
    await env.settle()
    assert entry.title == "My bus"


async def test_e2e_38_the_title_that_1_2_0b5_made_with_the_stops_goes_back_to_the_plain_one(env):
    """b5 and b6 titled a line "Line 525 · Marcelin 01, Marcelin 02" and remembered it in an option; both are cleaned up."""
    entry = await env.add_entry_via_flow(line=LINE)
    old = f"Line {LINE} · {stop_name_for('7009')} 01, {stop_name_for('7009')} 02"
    env.hass.config_entries.async_update_entry(entry, title=old, options={"generated_title": old})
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.settle()
    assert entry.title == f"Line {LINE}"
    assert "generated_title" not in entry.options


async def test_e2e_38_a_title_the_user_chose_over_the_one_of_b5_is_kept_and_the_option_dropped(env):
    entry = await env.add_entry_via_flow(line=LINE)
    old = f"Line {LINE} · {stop_name_for('7009')} 01"
    env.hass.config_entries.async_update_entry(entry, title="Night route", options={"generated_title": old})
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.settle()
    assert entry.title == "Night route"
    assert "generated_title" not in entry.options
