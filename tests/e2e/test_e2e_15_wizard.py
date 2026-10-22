"""E2E-43: the setup dialog is short screens: the key, the stop (a list of the City's stops), the line that stops there, and the pole
with its direction when the line serves more than one."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState

from custom_components.ztm_warsaw import config_flow
from custom_components.ztm_warsaw.client import StopCatalogue, ZTMAuthError, fold
from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN, stop_name_for

pytestmark = pytest.mark.e2e

LINE = "151"
NAME = stop_name_for("7009")


async def _first(env):
    """The first screen of the dialog."""
    return await env.hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def _stops(env, *, api_key=DEFAULT_KEY):
    """Open the dialog and submit its first screen (the key): the screen with the list of stops."""
    form = await _first(env)
    return await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": api_key})


async def _lines(env, stop="7009", *, api_key=DEFAULT_KEY):
    """Run the first two screens: the key, then the stop: the screen with the lines that stop there."""
    result = await _stops(env, api_key=api_key)
    return await env.hass.config_entries.flow.async_configure(result["flow_id"], {"stop": stop})


async def test_e2e_43_the_first_screen_asks_only_for_the_key_and_does_not_call_the_city(env):
    form = await _first(env)
    assert (form["type"], form["step_id"], form["errors"]) == ("form", "user", {})
    assert [str(k) for k in form["data_schema"].schema] == ["api_key", "manual"]
    assert env.city.count() == 0


async def test_e2e_43_the_key_leads_to_every_stop_of_the_city_then_its_lines_then_the_pole_with_its_direction(env):
    stops = await _stops(env)
    assert (stops["type"], stops["step_id"]) == ("form", "stop")
    options = stops["data_schema"].schema["stop"].config["options"]
    assert {"value": "7009", "label": f"{NAME} (7009)"} in options
    assert len(options) > 3, "every stop of the catalogue, not only one"
    assert [o["label"] for o in options] == sorted((o["label"] for o in options), key=fold), "sorted by name, diacritics ignored"
    lines = await env.hass.config_entries.flow.async_configure(stops["flow_id"], {"stop": "7009"})
    assert (lines["type"], lines["step_id"]) == ("form", "line")
    assert [str(k) for k in lines["data_schema"].schema] == ["line"], "an old key has no vehicles to show"
    choices = [o["value"] for o in lines["data_schema"].schema["line"].config["options"]]
    assert LINE in choices
    assert choices == sorted(choices, key=lambda x: (0, int(x), x) if x.isdigit() else (1, 0, x)), "numbers first, then letters"
    poles = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert (poles["type"], poles["step_id"]) == ("form", "pole"), "the line serves more than one pole of the stop"
    options = poles["data_schema"].schema["pole"].config["options"]
    assert {"7009/01", "7009/02"} <= {o["value"] for o in options}
    label = next(o["label"] for o in options if o["value"] == "7009/01")
    assert label.startswith(f"{NAME} 01 → "), "the direction the line takes from the pole is shown"
    assert label.endswith("(7009/01)")
    done = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    await env.settle()
    assert done["type"] == "create_entry", done
    entry = done["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert dict(entry.data) == {"api_key": DEFAULT_KEY, "line": LINE, "departures": 3}
    (stop,) = entry.subentries.values()
    assert dict(stop.data) == {"busstop_id": 7009, "busstop_nr": "01"}


async def test_e2e_43_a_key_that_is_neither_an_old_key_nor_a_token_is_refused_before_anything_is_asked_of_the_city(env):
    form = await _first(env)
    result = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": "not a key"})
    assert (result["step_id"], result["errors"]) == ("user", {"base": "invalid_api_key"})
    assert env.city.count() == 0


async def test_e2e_43_a_catalogue_that_cannot_be_read_leads_to_the_form_of_the_numbers(env):
    with patch.object(StopCatalogue, "all_stops", AsyncMock(return_value=(False, {}))):
        result = await _stops(env)
    assert (result["step_id"], result["errors"]) == ("manual", {"base": "cannot_load_stops"})


async def test_e2e_43_i_know_the_numbers_goes_straight_to_the_form_of_the_numbers(env):
    form = await _first(env)
    result = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": DEFAULT_KEY, "manual": True})
    assert (result["step_id"], result["errors"]) == ("manual", {})


async def test_e2e_43_a_stop_no_line_stops_at_today_says_so_and_stays_on_the_stop_screen(env):
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=[])):
        result = await _lines(env)
    assert (result["step_id"], result["errors"]) == ("stop", {"base": "no_lines"})


async def test_e2e_43_lines_the_city_does_not_give_are_a_connection_error_not_a_missing_line(env):
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=None)):
        result = await _lines(env)
    assert (result["step_id"], result["errors"]) == ("stop", {"base": "cannot_load_lines"})


async def test_e2e_43_a_key_the_city_rejects_at_the_lines_goes_back_to_the_first_screen(env):
    with patch.object(config_flow, "lines_at", AsyncMock(side_effect=ZTMAuthError("rejected"))):
        result = await _lines(env)
    assert (result["step_id"], result["errors"]) == ("user", {"base": "invalid_api_key"})


async def test_e2e_43_a_city_that_does_not_say_what_stops_at_the_poles_is_a_connection_error_for_the_line(env):
    lines = await _lines(env)
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=None)):
        result = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert (result["step_id"], result["errors"]) == ("line", {"base": "api_connection_error"})


async def test_e2e_43_a_key_the_city_rejects_when_the_poles_of_the_line_are_looked_up_goes_back_to_the_first_screen(env):
    lines = await _lines(env)
    with patch.object(config_flow, "poles_for_line", AsyncMock(side_effect=ZTMAuthError("rejected"))):
        result = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert (result["step_id"], result["errors"]) == ("user", {"base": "invalid_api_key"})


async def test_e2e_43_a_line_that_no_pole_serves_any_more_is_reported_on_the_line_screen(env):
    lines = await _lines(env)
    with patch.object(config_flow, "poles_for_line", AsyncMock(return_value=[])):
        result = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert (result["step_id"], result["errors"]) == ("line", {"base": "line_not_found"})


async def test_e2e_43_a_line_the_city_then_refuses_is_reported_on_the_pole_screen(env):
    lines = await _lines(env)
    poles = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    with patch.object(config_flow, "error_for", AsyncMock(return_value=("no_departures", True))):
        result = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert (result["step_id"], result["errors"]) == ("pole", {"base": "no_departures"})


async def test_e2e_43_a_line_that_serves_only_one_pole_skips_the_pole_screen_and_reports_on_the_line_screen(env):
    lines = await _lines(env)
    only = [{"stop_id": "7009", "stop_nr": "01", "name": NAME, "direction": "x"}]
    with patch.object(config_flow, "poles_for_line", AsyncMock(return_value=only)), patch.object(
        config_flow, "error_for", AsyncMock(return_value=("no_departures", True))
    ):
        result = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert (result["step_id"], result["errors"]) == ("line", {"base": "no_departures"})


async def test_e2e_43_the_same_stop_pole_and_line_cannot_be_added_twice_and_another_pole_joins_the_line(env):
    first = await env.submit_wizard(stop="7009", line=LINE, pole="7009/01")
    assert first["type"] == "create_entry"
    again = await env.submit_wizard(stop="7009", line=LINE, pole="7009/01")
    assert (again["type"], again["reason"]) == ("abort", "already_configured")
    other = await env.submit_wizard(stop="7009", line=LINE, pole="7009/02")
    assert (other["type"], other["reason"]) == ("abort", "stop_added")
    entry = first["result"]
    assert sorted(s.data["busstop_nr"] for s in entry.subentries.values()) == ["01", "02"]


async def test_e2e_43_add_stop_on_a_line_lists_the_stops_and_adds_the_pole_picked(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    assert (form["step_id"], [str(k) for k in form["data_schema"].schema]) == ("user", ["stop", "manual"])
    assert {"value": "7009", "label": f"{NAME} (7009)"} in form["data_schema"].schema["stop"].config["options"]
    poles = await manager.async_configure(form["flow_id"], {"stop": "7009"})
    assert poles["step_id"] == "pole", "the line serves both poles of the stop"
    done = await manager.async_configure(poles["flow_id"], {"pole": "7009/02"})
    await env.settle()
    assert done["type"] == "create_entry", done
    assert sorted(s.data["busstop_nr"] for s in entry.subentries.values()) == ["01", "02"]


async def test_e2e_43_add_stop_goes_to_the_numbers_when_the_stops_cannot_be_listed_or_the_numbers_are_chosen(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    with patch.object(StopCatalogue, "all_stops", AsyncMock(return_value=(False, {}))):
        unreadable = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    assert (unreadable["step_id"], unreadable["errors"]) == ("manual", {"base": "cannot_load_stops"})
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    manual = await manager.async_configure(form["flow_id"], {"manual": True})
    assert manual["step_id"] == "manual"


async def test_e2e_43_add_stop_asks_to_pick_a_stop_or_tick_the_numbers(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    result = await manager.async_configure(form["flow_id"], {})
    assert (result["step_id"], result["errors"]) == ("user", {"base": "choose_a_stop"})


async def test_e2e_43_add_stop_says_so_when_the_line_serves_no_pole_of_the_stop_or_the_city_or_the_key_fails(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    with patch.object(config_flow, "poles_for_line", AsyncMock(return_value=[])):
        none = await manager.async_configure(form["flow_id"], {"stop": "7009"})
    assert (none["step_id"], none["errors"]) == ("user", {"base": "line_not_found"})
    with patch.object(config_flow, "poles_for_line", AsyncMock(side_effect=ZTMAuthError("rejected"))):
        rejected = await manager.async_configure(none["flow_id"], {"stop": "7009"})
    assert (rejected["step_id"], rejected["errors"]) == ("user", {"base": "invalid_api_key"})
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=None)):
        down = await manager.async_configure(rejected["flow_id"], {"stop": "7009"})
    assert (down["step_id"], down["errors"]) == ("user", {"base": "api_connection_error"})


async def test_e2e_43_add_stop_with_a_line_that_serves_one_pole_adds_it_without_asking_which(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    with patch.object(config_flow, "poles_for_line", AsyncMock(return_value=[{"stop_id": "7009", "stop_nr": "02", "name": NAME, "direction": "x"}])):
        done = await manager.async_configure(form["flow_id"], {"stop": "7009"})
    assert done["type"] == "create_entry", done


async def test_e2e_43_add_stop_refuses_a_pole_the_line_does_not_stop_at(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    poles = await manager.async_configure(form["flow_id"], {"stop": "7009"})
    with patch.object(config_flow, "error_for", AsyncMock(return_value=("line_not_found", True))):
        result = await manager.async_configure(poles["flow_id"], {"pole": "7009/02"})
    assert (result["step_id"], result["errors"]) == ("pole", {"base": "line_not_found"})
    assert len(entry.subentries) == 1


async def test_e2e_43_add_stop_aborts_when_the_entry_loses_its_key_between_the_screens(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    poles = await manager.async_configure(form["flow_id"], {"stop": "7009"})
    manual = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    manual = await manager.async_configure(manual["flow_id"], {"manual": True})
    env.hass.config_entries.async_update_entry(entry, data={"line": LINE})  # the key is gone
    pole_result = await manager.async_configure(poles["flow_id"], {"pole": "7009/02"})
    manual_result = await manager.async_configure(manual["flow_id"], {"busstop_id": 7009, "busstop_nr": "02"})
    assert (pole_result["type"], pole_result["reason"]) == ("abort", "unknown")
    assert (manual_result["type"], manual_result["reason"]) == ("abort", "unknown")
    assert form["type"] == "form"


async def test_e2e_43_the_catalogue_is_downloaded_once_for_many_setups(env):
    await _stops(env)
    first = env.city.count("stops")
    await _stops(env)
    assert env.city.count("stops") == first


async def test_e2e_43_a_token_can_show_the_vehicles_of_the_new_line_on_the_map_from_the_start(env):
    lines = await _lines(env, api_key=DEFAULT_TOKEN)
    assert [str(k) for k in lines["data_schema"].schema] == ["line", "show_vehicles"]
    poles = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE, "show_vehicles": True})
    done = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert done["type"] == "create_entry", done
    assert dict(done["result"].options) == {"show_vehicles": True}


async def test_e2e_43_the_vehicles_stay_off_unless_they_are_ticked(env):
    lines = await _lines(env, api_key=DEFAULT_TOKEN)
    poles = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    done = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert dict(done["result"].options) == {}


async def test_e2e_43_ticking_the_vehicles_for_a_line_that_is_set_up_turns_them_on_for_that_line(env):
    entry = await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    done = await env.submit_wizard(stop="7009", line=LINE, pole="7009/02", api_key=DEFAULT_TOKEN, show_vehicles=True)
    await env.settle()
    assert (done["type"], done["reason"]) == ("abort", "stop_added")
    assert entry.options.get("show_vehicles") is True


async def test_e2e_43_a_token_already_in_use_can_be_picked_instead_of_pasted_again(env):
    first = await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    form = await _first(env)
    assert (form["type"], form["step_id"]) == ("form", "user_existing")
    assert [str(k) for k in form["data_schema"].schema] == ["token", "api_key", "manual"]
    (choice,) = form["data_schema"].schema["token"].config["options"]
    assert choice["label"] == f"…{DEFAULT_TOKEN[-4:]}  ·  {LINE}", "told by its last four characters and its lines, never whole"
    stops = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"token": choice["value"]})
    assert (stops["type"], stops["step_id"]) == ("form", "stop"), "no token was pasted"
    lines = await env.hass.config_entries.flow.async_configure(stops["flow_id"], {"stop": "7009"})
    poles = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": "N25"})
    done = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert done["type"] == "create_entry", done
    assert done["result"].data["api_key"] == first.data["api_key"]


async def test_e2e_43_a_token_pasted_below_wins_over_the_one_in_use_and_a_bad_paste_is_refused(env):
    await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    form = await _first(env)
    refused = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"token": "0", "api_key": "not a key"})
    assert (refused["step_id"], refused["errors"]) == ("user_existing", {"base": "invalid_api_key"})
    key_field = next(k for k in refused["data_schema"].schema if str(k) == "api_key")
    assert key_field.default() == "not a key"
    again = await env.hass.config_entries.flow.async_configure(refused["flow_id"], {"token": "0", "api_key": DEFAULT_KEY})
    assert again["step_id"] == "stop", "an old key pasted is a key: it is checked like one"


async def test_e2e_43_an_old_key_in_use_is_not_offered_as_a_token(env):
    await env.add_entry_via_flow()  # an old key
    form = await _first(env)
    assert (form["step_id"], [str(k) for k in form["data_schema"].schema]) == ("user", ["api_key", "manual"])


async def test_e2e_43_a_token_picked_from_those_in_use_is_not_put_in_the_form_of_the_numbers(env):
    await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    form = await _first(env)
    manual = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"token": "0", "manual": True})
    assert manual["step_id"] == "manual"
    key_field = next(k for k in manual["data_schema"].schema if str(k) == "api_key")
    assert key_field.default() == "", "the whole token is not sent to the browser"
    done = await env.hass.config_entries.flow.async_configure(manual["flow_id"], {"busstop_id": 7009, "busstop_nr": "02", "line": LINE})
    assert (done["type"], done["reason"]) == ("abort", "stop_added")



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


async def test_e2e_43_a_name_the_city_abbreviates_can_be_found_by_typing_it_in_full(env):
    from custom_components.ztm_warsaw.client import spelled_out

    assert spelled_out("Dw. Centralny") == "Dworzec Centralny"
    assert spelled_out("os. Gorczewska") == "Osiedle Gorczewska"
    assert spelled_out("Marcelin") == "Marcelin"
    assert config_flow._stop_label("Dw. Centralny", "5003") == "Dw. Centralny (Dworzec Centralny) (5003)"
    assert config_flow._stop_label("Marcelin", "7009") == "Marcelin (7009)"
