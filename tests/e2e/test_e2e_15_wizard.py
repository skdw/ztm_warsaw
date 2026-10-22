"""E2E-43: the setup dialog is short screens: the key, part of the stop's name, the stop when the name fits several, the pole with the
direction it goes (when the stop has more than one with lines) and the line that stops there."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState

from custom_components.ztm_warsaw import config_flow
from custom_components.ztm_warsaw.client import StopCatalogue, ZTMAuthError
from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN, stop_name_for

pytestmark = pytest.mark.e2e

LINE = "151"
NAME = stop_name_for("7009")


async def _first(env):
    """The first screen of the dialog."""
    return await env.hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def _search(env, query, *, api_key=DEFAULT_KEY):
    """Run the first two screens: the key, then what to search for."""
    form = await _first(env)
    result = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": api_key})
    return await env.hass.config_entries.flow.async_configure(result["flow_id"], {"query": query})


async def test_e2e_43_the_first_screen_asks_only_for_the_key_and_does_not_call_the_city(env):
    form = await _first(env)
    assert (form["type"], form["step_id"], form["errors"]) == ("form", "user", {})
    assert [str(k) for k in form["data_schema"].schema] == ["api_key", "manual"]
    assert env.city.count() == 0


async def test_e2e_43_the_key_leads_to_the_search_then_the_stop_then_the_pole_with_its_direction_then_the_line(env):
    form = await _first(env)
    search = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": DEFAULT_KEY})
    assert (search["type"], search["step_id"]) == ("form", "stop")
    pick = await env.hass.config_entries.flow.async_configure(search["flow_id"], {"query": NAME[:12].lower()})
    assert (pick["type"], pick["step_id"]) == ("form", "pick"), "the name fits more than one stop"
    assert {"label": f"{NAME} (7009)", "value": "7009"} in pick["data_schema"].schema["stop"].config["options"]
    poles = await env.hass.config_entries.flow.async_configure(pick["flow_id"], {"stop": "7009"})
    assert (poles["type"], poles["step_id"]) == ("form", "pole"), "the stop has two poles with lines"
    options = poles["data_schema"].schema["pole"].config["options"]
    assert {"7009/01", "7009/02"} <= {o["value"] for o in options}
    label = next(o["label"] for o in options if o["value"] == "7009/01")
    assert label.startswith(f"{NAME} 01 → "), "where the pole goes is shown: the catalogue has no direction, the timetable has"
    assert label.endswith("(7009/01)")
    lines = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert (lines["type"], lines["step_id"]) == ("form", "line")
    assert [str(k) for k in lines["data_schema"].schema] == ["line"], "an old key has no vehicles to show"
    choices = [o["value"] for o in lines["data_schema"].schema["line"].config["options"]]
    assert LINE in choices
    assert choices == sorted(choices, key=lambda x: (0, int(x), x) if x.isdigit() else (1, 0, x)), "numbers first, then letters"
    done = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    await env.settle()
    assert done["type"] == "create_entry", done
    entry = done["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert dict(entry.data) == {"api_key": DEFAULT_KEY, "line": LINE, "departures": 3}
    (stop,) = entry.subentries.values()
    assert dict(stop.data) == {"busstop_id": 7009, "busstop_nr": "01"}


async def test_e2e_43_a_pole_typed_as_numbers_skips_the_stop_and_the_pole_screens(env):
    lines = await _search(env, "7009/01")
    assert (lines["type"], lines["step_id"]) == ("form", "line")


async def test_e2e_43_a_stop_with_one_name_skips_the_stop_screen(env):
    poles = await _search(env, NAME)
    assert (poles["type"], poles["step_id"]) == ("form", "pole")


async def test_e2e_43_nothing_found_stays_on_the_search_screen_and_says_so(env):
    result = await _search(env, "no such stop anywhere")
    assert (result["step_id"], result["errors"]) == ("stop", {"base": "no_stop_found"})


async def test_e2e_43_a_search_that_matches_too_many_stops_asks_for_more_of_the_name(env):
    result = await _search(env, "Testowa")  # every stop of the fake catalogue
    assert (result["step_id"], result["errors"]) == ("stop", {"base": "too_many_matches"})


async def test_e2e_43_a_key_that_is_neither_an_old_key_nor_a_token_is_refused_before_anything_is_asked_of_the_city(env):
    form = await _first(env)
    result = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": "not a key"})
    assert (result["step_id"], result["errors"]) == ("user", {"base": "invalid_api_key"})
    assert env.city.count() == 0


async def test_e2e_43_a_catalogue_that_cannot_be_read_leads_to_the_form_of_the_numbers(env):
    with patch.object(StopCatalogue, "search", AsyncMock(return_value=(None, []))):
        result = await _search(env, "7009")
    assert (result["step_id"], result["errors"]) == ("manual", {"base": "cannot_load_stops"})


async def test_e2e_43_i_know_the_numbers_goes_straight_to_the_form_of_the_numbers(env):
    form = await _first(env)
    result = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": DEFAULT_KEY, "manual": True})
    assert (result["step_id"], result["errors"]) == ("manual", {})


async def test_e2e_43_a_stop_no_line_stops_at_today_says_so_and_goes_back_to_the_search(env):
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=[])):
        result = await _search(env, NAME)
    assert (result["step_id"], result["errors"]) == ("stop", {"base": "no_lines"})


async def test_e2e_43_a_name_that_fits_several_stops_goes_back_to_the_choice_of_the_stop_when_no_line_is_found(env):
    pick = await _search(env, NAME[:12].lower())
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=[])):
        result = await env.hass.config_entries.flow.async_configure(pick["flow_id"], {"stop": "7009"})
    assert (result["step_id"], result["errors"]) == ("pick", {"base": "no_lines"})


async def test_e2e_43_lines_the_city_does_not_give_are_a_connection_error_not_a_missing_line(env):
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=None)):
        result = await _search(env, NAME)
    assert (result["step_id"], result["errors"]) == ("stop", {"base": "cannot_load_lines"})


async def test_e2e_43_a_key_the_city_rejects_at_the_lines_goes_back_to_the_first_screen(env):
    with patch.object(config_flow, "lines_at", AsyncMock(side_effect=ZTMAuthError("rejected"))):
        result = await _search(env, NAME)
    assert (result["step_id"], result["errors"]) == ("user", {"base": "invalid_api_key"})


async def test_e2e_43_a_line_the_city_then_refuses_is_reported_on_the_line_screen(env):
    lines = await _search(env, "7009/01")
    with patch.object(config_flow, "error_for", AsyncMock(return_value=("no_departures", True))):
        result = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert (result["step_id"], result["errors"]) == ("line", {"base": "no_departures"})


async def test_e2e_43_the_same_stop_pole_and_line_cannot_be_added_twice_and_another_pole_joins_the_line(env):
    first = await env.submit_wizard(query="7009/01", line=LINE)
    assert first["type"] == "create_entry"
    again = await env.submit_wizard(query="7009/01", line=LINE)
    assert (again["type"], again["reason"]) == ("abort", "already_configured")
    other = await env.submit_wizard(query="7009/02", line=LINE)
    assert (other["type"], other["reason"]) == ("abort", "stop_added")
    entry = first["result"]
    assert sorted(s.data["busstop_nr"] for s in entry.subentries.values()) == ["01", "02"]


async def test_e2e_43_add_stop_on_a_line_searches_by_name_and_adds_the_pole_the_line_serves(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    assert (form["step_id"], [str(k) for k in form["data_schema"].schema]) == ("user", ["query", "manual"])
    pick = await manager.async_configure(form["flow_id"], {"query": NAME[:12].lower()})
    assert pick["step_id"] == "pick"
    poles = await manager.async_configure(pick["flow_id"], {"stop": "7009"})
    assert poles["step_id"] == "pole", "the line serves both poles of the stop"
    done = await manager.async_configure(poles["flow_id"], {"pole": "7009/02"})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert sorted(s.data["busstop_nr"] for s in entry.subentries.values()) == ["01", "02"]


async def test_e2e_43_add_stop_reports_what_goes_wrong_in_the_search(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    empty = await manager.async_configure(form["flow_id"], {})
    assert (empty["step_id"], empty["errors"]) == ("user", {"base": "choose_a_stop"})
    nothing = await manager.async_configure(form["flow_id"], {"query": "no such stop anywhere"})
    assert (nothing["step_id"], nothing["errors"]) == ("user", {"base": "no_stop_found"})
    many = await manager.async_configure(form["flow_id"], {"query": "Testowa"})
    assert (many["step_id"], many["errors"]) == ("user", {"base": "too_many_matches"})
    with patch.object(StopCatalogue, "search", AsyncMock(return_value=(None, []))):
        unreadable = await manager.async_configure(form["flow_id"], {"query": "7009"})
    assert (unreadable["step_id"], unreadable["errors"]) == ("manual", {"base": "cannot_load_stops"})


async def test_e2e_43_add_stop_says_so_when_the_line_serves_no_pole_of_the_stop_or_the_city_or_the_key_fails(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    with patch.object(config_flow, "poles_for_line", AsyncMock(return_value=[])):
        none = await manager.async_configure(form["flow_id"], {"query": NAME})
    assert (none["step_id"], none["errors"]) == ("user", {"base": "line_not_found"})
    with patch.object(config_flow, "poles_for_line", AsyncMock(side_effect=ZTMAuthError("rejected"))):
        rejected = await manager.async_configure(none["flow_id"], {"query": NAME})
    assert (rejected["step_id"], rejected["errors"]) == ("user", {"base": "invalid_api_key"})
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=None)):
        down = await manager.async_configure(rejected["flow_id"], {"query": NAME})
    assert (down["step_id"], down["errors"]) == ("user", {"base": "api_connection_error"})


async def test_e2e_43_add_stop_with_a_line_that_serves_one_pole_adds_it_without_asking_which(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    with patch.object(config_flow, "poles_for_line", AsyncMock(return_value=[{"stop_id": "7009", "stop_nr": "02", "name": NAME, "direction": "x"}])):
        done = await manager.async_configure(form["flow_id"], {"query": NAME})
    assert done["type"] == "create_entry", done


async def test_e2e_43_add_stop_refuses_a_pole_the_line_does_not_stop_at(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    poles = await manager.async_configure(form["flow_id"], {"query": NAME})
    with patch.object(config_flow, "error_for", AsyncMock(return_value=("line_not_found", True))):
        result = await manager.async_configure(poles["flow_id"], {"pole": "7009/02"})
    assert (result["step_id"], result["errors"]) == ("pole", {"base": "line_not_found"})
    assert len(entry.subentries) == 1


async def test_e2e_43_add_stop_aborts_when_the_entry_loses_its_key_between_the_screens(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    poles = await manager.async_configure(form["flow_id"], {"query": NAME})
    manual = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    manual = await manager.async_configure(manual["flow_id"], {"manual": True})
    env.hass.config_entries.async_update_entry(entry, data={"line": LINE})  # the key is gone
    pole_result = await manager.async_configure(poles["flow_id"], {"pole": "7009/02"})
    manual_result = await manager.async_configure(manual["flow_id"], {"busstop_id": 7009, "busstop_nr": "02"})
    assert (pole_result["type"], pole_result["reason"]) == ("abort", "unknown")
    assert (manual_result["type"], manual_result["reason"]) == ("abort", "unknown")


async def test_e2e_43_the_catalogue_is_downloaded_once_for_many_searches(env):
    await _search(env, "7009")
    first = env.city.count("stops")
    await _search(env, "7009/02")
    assert env.city.count("stops") == first


async def test_e2e_43_a_token_can_show_the_vehicles_of_the_new_line_on_the_map_from_the_start(env):
    lines = await _search(env, "7009/01", api_key=DEFAULT_TOKEN)
    assert [str(k) for k in lines["data_schema"].schema] == ["line", "show_vehicles"]
    done = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE, "show_vehicles": True})
    assert done["type"] == "create_entry", done
    assert dict(done["result"].options) == {"show_vehicles": True}


async def test_e2e_43_the_vehicles_stay_off_unless_they_are_ticked(env):
    lines = await _search(env, "7009/01", api_key=DEFAULT_TOKEN)
    done = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert dict(done["result"].options) == {}


async def test_e2e_43_ticking_the_vehicles_for_a_line_that_is_set_up_turns_them_on_for_that_line(env):
    entry = await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    done = await env.submit_wizard(query="7009/02", line=LINE, api_key=DEFAULT_TOKEN, show_vehicles=True)
    await env.settle()
    assert (done["type"], done["reason"]) == ("abort", "stop_added")
    assert entry.options.get("show_vehicles") is True


async def test_e2e_43_a_token_already_in_use_is_offered_in_a_menu_and_used_without_pasting_it_again(env):
    first = await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    menu = await _first(env)
    assert (menu["type"], menu["step_id"]) == ("menu", "user_existing")
    assert menu["menu_options"] == ["use_token", "paste_token"]
    assert f"…{DEFAULT_TOKEN[-4:]}  ·  {LINE}" in menu["description_placeholders"]["tokens"], "told by its last four characters and its lines, never whole"
    assert DEFAULT_TOKEN not in str(menu)
    search = await env.hass.config_entries.flow.async_configure(menu["flow_id"], {"next_step_id": "use_token"})
    assert (search["type"], search["step_id"]) == ("form", "stop"), "one token in use: no pasting and no choice"
    lines = await env.hass.config_entries.flow.async_configure(search["flow_id"], {"query": "7009/01"})
    done = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": "N25"})
    assert done["type"] == "create_entry", done
    assert done["result"].data["api_key"] == first.data["api_key"]


async def test_e2e_43_with_more_than_one_token_in_use_the_one_to_use_is_asked(env):
    await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    other = DEFAULT_TOKEN[:-4] + "ZZZZ"
    await env.add_entry(api_key=other, line="523")
    menu = await _first(env)
    pick = await env.hass.config_entries.flow.async_configure(menu["flow_id"], {"next_step_id": "use_token"})
    assert (pick["type"], pick["step_id"]) == ("form", "use_token")
    labels = [o["label"] for o in pick["data_schema"].schema["token"].config["options"]]
    assert len(labels) == 2
    assert all(DEFAULT_TOKEN not in label for label in labels)
    search = await env.hass.config_entries.flow.async_configure(pick["flow_id"], {"token": "1"})
    assert (search["type"], search["step_id"]) == ("form", "stop")


async def test_e2e_43_pasting_another_token_from_the_menu_is_the_plain_form_of_the_key(env):
    await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    menu = await _first(env)
    form = await env.hass.config_entries.flow.async_configure(menu["flow_id"], {"next_step_id": "paste_token"})
    assert (form["type"], form["step_id"]) == ("form", "user")
    assert [str(k) for k in form["data_schema"].schema] == ["api_key", "manual"]
    refused = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": "not a key"})
    assert (refused["step_id"], refused["errors"]) == ("user", {"base": "invalid_api_key"})
    ok = await env.hass.config_entries.flow.async_configure(refused["flow_id"], {"api_key": DEFAULT_KEY})
    assert ok["step_id"] == "stop", "an old key pasted is a key: it is checked like one"
    numbers = await env.hass.config_entries.flow.async_configure(
        (await env.hass.config_entries.flow.async_configure((await _first(env))["flow_id"], {"next_step_id": "paste_token"}))["flow_id"],
        {"api_key": DEFAULT_TOKEN, "manual": True},
    )
    assert numbers["step_id"] == "manual"


async def test_e2e_43_an_old_key_in_use_is_not_offered_as_a_token(env):
    await env.add_entry_via_flow()  # an old key
    form = await _first(env)
    assert (form["step_id"], [str(k) for k in form["data_schema"].schema]) == ("user", ["api_key", "manual"])


async def test_e2e_43_a_menu_asked_for_again_shows_itself_again(env):
    await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    menu = await _first(env)
    assert (await env.hass.config_entries.flow.async_configure(menu["flow_id"], None))["step_id"] == "user_existing"


async def test_e2e_43_the_poles_of_a_stop_are_told_apart_by_the_places_their_first_lines_go(env):
    poles = [{"stop_id": "7009", "stop_nr": "01", "name": NAME, "direction": "catalogue"}, {"stop_id": "7009", "stop_nr": "02", "name": NAME, "direction": "catalogue"}]
    lines = {"01": ["151", "523", "N25"], "02": []}
    heads = {"151": "Rechniewskiego", "523": "Rechniewskiego", "N25": "Dworzec Centralny"}
    with patch.object(config_flow, "direction_of", AsyncMock(side_effect=lambda hass, key, pole, line: heads[line])):
        found = await config_flow.pole_directions(env.hass, DEFAULT_KEY, poles, lines)
    assert [(p["stop_nr"], p["direction"]) for p in found] == [("01", "Rechniewskiego")], "two lines, one place; a pole without lines is left out"



async def test_e2e_43_the_list_of_lines_at_a_pole_is_ordered_for_a_person_and_failures_are_told_apart(env):
    from custom_components.ztm_warsaw.client import ZTMApiError, ZTMStopClient

    async def answer(*_args, **_kwargs):
        """The lines the City gives, in a jumble."""
        return ["N25", "523", "9", "151", "E-2", "151"]

    with patch.object(ZTMStopClient, "get_lines", answer):
        assert await config_flow.lines_at(env.hass, DEFAULT_KEY, "7009", "01") == ["9", "151", "523", "E-2", "N25"]
    with patch.object(ZTMStopClient, "get_lines", AsyncMock(return_value=None)):
        assert await config_flow.lines_at(env.hass, DEFAULT_KEY, "7009", "01") is None
    with patch.object(ZTMStopClient, "get_lines", AsyncMock(side_effect=ZTMApiError("odd answer"))):
        assert await config_flow.lines_at(env.hass, DEFAULT_KEY, "7009", "01") is None
    with patch.object(ZTMStopClient, "get_lines", AsyncMock(side_effect=ZTMAuthError("rejected"))):
        with pytest.raises(ZTMAuthError):
            await config_flow.lines_at(env.hass, DEFAULT_KEY, "7009", "01")


async def test_e2e_43_the_check_of_the_timetable_tells_a_broken_answer_from_a_missing_one(env):
    from custom_components.ztm_warsaw.client import ZTMApiError, ZTMStopClient

    client = ZTMStopClient(None, DEFAULT_KEY, "7009", "01", LINE)
    with patch.object(ZTMStopClient, "get", AsyncMock(side_effect=ZTMApiError("odd answer"))):
        with pytest.raises(ValueError, match="no_valid_times"):
            await config_flow._check_timetable(client)
    with patch.object(ZTMStopClient, "get", AsyncMock(return_value=None)):
        with pytest.raises(ValueError, match="api_connection_error"):
            await config_flow._check_timetable(client)


async def test_e2e_43_a_direction_the_timetable_cannot_give_falls_back_to_the_catalogue_and_a_rejected_key_is_passed_on(env):
    from custom_components.ztm_warsaw.client import ZTMApiError, ZTMStopClient

    pole = {"stop_id": "7009", "stop_nr": "01", "name": NAME, "direction": "Catalogue direction"}
    with patch.object(ZTMStopClient, "get", AsyncMock(side_effect=ZTMApiError("down"))):
        assert await config_flow.direction_of(env.hass, DEFAULT_KEY, pole, LINE) == "Catalogue direction"
    with patch.object(ZTMStopClient, "get", AsyncMock(side_effect=ZTMAuthError("rejected"))), pytest.raises(ZTMAuthError):
        await config_flow.direction_of(env.hass, DEFAULT_KEY, pole, LINE)


async def test_e2e_43_a_screen_asked_for_again_shows_itself_again(env):
    flow = env.hass.config_entries.flow
    pick = await _search(env, NAME[:12].lower())
    assert (await flow.async_configure(pick["flow_id"], None))["step_id"] == "pick"
    poles = await flow.async_configure(pick["flow_id"], {"stop": "7009"})
    assert (await flow.async_configure(poles["flow_id"], None))["step_id"] == "pole"
    lines = await flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert (await flow.async_configure(lines["flow_id"], None))["step_id"] == "line"
    search = await _search(env, "no such stop anywhere")
    assert (await flow.async_configure(search["flow_id"], None))["step_id"] == "stop"


async def test_e2e_43_a_token_that_disappears_while_the_menu_is_open_goes_back_to_the_form_of_the_key(env):
    entry = await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    menu = await _first(env)
    await env.hass.config_entries.async_remove(entry.entry_id)
    form = await env.hass.config_entries.flow.async_configure(menu["flow_id"], {"next_step_id": "use_token"})
    assert (form["type"], form["step_id"]) == ("form", "user")


async def test_e2e_43_a_token_picked_by_a_number_that_is_gone_shows_the_menu_again(env):
    await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    other = await env.add_entry(api_key=DEFAULT_TOKEN[:-4] + "ZZZZ", line="523")
    menu = await _first(env)
    pick = await env.hass.config_entries.flow.async_configure(menu["flow_id"], {"next_step_id": "use_token"})
    await env.hass.config_entries.async_remove(other.entry_id)
    again = await env.hass.config_entries.flow.async_configure(pick["flow_id"], {"token": "1"})
    assert (again["type"], again["step_id"]) == ("menu", "user_existing")


async def test_e2e_43_the_numbers_can_be_typed_with_a_token_picked_from_those_in_use(env):
    first = await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    menu = await _first(env)
    search = await env.hass.config_entries.flow.async_configure(menu["flow_id"], {"next_step_id": "use_token"})
    assert [str(k) for k in search["data_schema"].schema] == ["query", "manual"]
    manual = await env.hass.config_entries.flow.async_configure(search["flow_id"], {"query": "", "manual": True})
    assert manual["step_id"] == "manual"
    done = await env.hass.config_entries.flow.async_configure(manual["flow_id"], {"busstop_id": 7009, "busstop_nr": "02", "line": LINE})
    assert (done["type"], done["reason"]) == ("abort", "stop_added")
    assert first.data["api_key"] == DEFAULT_TOKEN


async def test_e2e_43_a_choice_of_tokens_means_the_token_that_was_shown_even_when_another_one_is_removed(env):
    gone = await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    kept_token = DEFAULT_TOKEN[:-4] + "ZZZZ"
    await env.add_entry(api_key=kept_token, line="523")
    menu = await _first(env)
    pick = await env.hass.config_entries.flow.async_configure(menu["flow_id"], {"next_step_id": "use_token"})
    await env.hass.config_entries.async_remove(gone.entry_id)  # the token that was number 0 on the screen
    again = await env.hass.config_entries.flow.async_configure(pick["flow_id"], {"token": "0"})
    assert (again["type"], again["step_id"]) == ("menu", "user_existing"), "token 0 was the removed one: nothing is guessed"


async def test_e2e_43_a_menu_that_showed_one_token_does_not_use_another_one_that_is_left_after_a_removal(env):
    gone = await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    await env.add_entry(api_key=DEFAULT_TOKEN[:-4] + "ZZZZ", line="523")
    # one token is shown by the menu when the other line has none of its own: remove the second and start again
    await env.hass.config_entries.async_remove(next(e for e in env.hass.config_entries.async_entries(DOMAIN) if e.data["line"] == "523").entry_id)
    menu = await _first(env)
    assert DEFAULT_TOKEN[-4:] in menu["description_placeholders"]["tokens"]
    await env.hass.config_entries.async_remove(gone.entry_id)
    await env.add_entry(api_key=DEFAULT_TOKEN[:-4] + "ZZZZ", line="523")  # a different token is now the only one
    again = await env.hass.config_entries.flow.async_configure(menu["flow_id"], {"next_step_id": "use_token"})
    assert (again["type"], again["step_id"]) == ("menu", "user_existing"), "the token the menu showed is gone: nothing is guessed"
