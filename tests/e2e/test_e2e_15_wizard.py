"""E2E-43: the setup dialog starts from the line: the key and the line, then the stop of that line, then the pole with its direction."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState

from custom_components.ztm_warsaw import config_flow
from custom_components.ztm_warsaw.client import ZTMAuthError
from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN, stop_name_for

pytestmark = pytest.mark.e2e

LINE = "151"
NAME = stop_name_for("7009")


async def _first(env):
    """The first screen of the dialog."""
    return await env.hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def _line(env, line=LINE, *, api_key=DEFAULT_KEY, **extra):
    """Open the dialog and submit its first screen (the key and the line)."""
    form = await _first(env)
    return await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": api_key, "line": line, **extra})


async def _stop(env, stop="7009", *, api_key=DEFAULT_KEY, **extra):
    """Run the first two screens: the key and the line, then the stop."""
    result = await _line(env, api_key=api_key)
    return await env.hass.config_entries.flow.async_configure(result["flow_id"], {"stop": stop, **extra})


async def test_e2e_43_the_first_screen_asks_for_the_key_and_the_line_and_does_not_call_the_city(env):
    form = await _first(env)
    assert (form["type"], form["step_id"], form["errors"]) == ("form", "user", {})
    assert [str(k) for k in form["data_schema"].schema] == ["api_key", "line", "manual"]
    options = form["data_schema"].schema["line"].config["options"]
    assert {"value": LINE, "label": LINE} in options
    values = [o["value"] for o in options]
    assert values == sorted(values, key=lambda x: (0, int(x), x) if x.isdigit() else (1, 0, x)), "numbers first, then letters"
    assert env.city.count() == 0


async def test_e2e_43_a_line_leads_to_its_stops_with_their_names_then_the_pole_with_its_direction(env):
    stops = await _line(env)
    assert (stops["type"], stops["step_id"]) == ("form", "stop")
    assert [str(k) for k in stops["data_schema"].schema] == ["stop"], "an old key has no vehicles to show"
    options = stops["data_schema"].schema["stop"].config["options"]
    assert {"value": "7009", "label": f"{NAME} (7009)"} in options
    assert [o["label"] for o in options] == sorted((o["label"] for o in options), key=str.casefold), "sorted by name"
    poles = await env.hass.config_entries.flow.async_configure(stops["flow_id"], {"stop": "7009"})
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


async def test_e2e_43_a_line_is_typed_in_any_case_and_a_line_that_is_not_in_the_list_is_said_so(env):
    assert (await _line(env, "n25"))["step_id"] == "stop"
    result = await _line(env, "999")
    assert (result["step_id"], result["errors"]) == ("user", {"base": "unknown_line"})
    key_field = next(k for k in result["data_schema"].schema if str(k) == "api_key")
    assert key_field.default() == DEFAULT_KEY, "the key is not asked for again"


async def test_e2e_43_a_key_that_is_neither_an_old_key_nor_a_token_is_refused_before_anything_is_asked_of_the_city(env):
    result = await _line(env, api_key="not a key")
    assert (result["step_id"], result["errors"]) == ("user", {"base": "invalid_api_key"})
    assert env.city.count() == 0


async def test_e2e_43_a_list_of_lines_that_cannot_be_read_leads_to_the_form_of_the_numbers(env, tmp_path):
    with patch("custom_components.ztm_warsaw.line_index.INDEX_FILE", tmp_path / "missing.json"):
        form = await _first(env)
    assert (form["step_id"], form["errors"]) == ("manual", {"base": "cannot_load_stops"})


async def test_e2e_43_a_catalogue_that_cannot_be_read_leads_to_the_form_of_the_numbers(env):
    from custom_components.ztm_warsaw.client import StopCatalogue

    with patch.object(StopCatalogue, "stop_names", AsyncMock(return_value=(False, {}))):
        result = await _line(env)
    assert (result["step_id"], result["errors"]) == ("manual", {"base": "cannot_load_stops"})
    assert [str(k) for k in result["data_schema"].schema if str(k) == "line"], "the line chosen is kept"


async def test_e2e_43_i_know_the_numbers_goes_straight_to_the_form_of_the_numbers(env):
    result = await _line(env, manual=True)
    assert (result["step_id"], result["errors"]) == ("manual", {})


async def test_e2e_43_a_stop_the_line_does_not_serve_today_says_so_and_stays_on_the_stop_screen(env):
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=[])):
        result = await _stop(env)
    assert (result["step_id"], result["errors"]) == ("stop", {"base": "line_not_found"})


async def test_e2e_43_a_key_the_city_rejects_at_the_poles_goes_back_to_the_first_screen(env):
    with patch.object(config_flow, "lines_at", AsyncMock(side_effect=ZTMAuthError("rejected"))):
        result = await _stop(env)
    assert (result["step_id"], result["errors"]) == ("user", {"base": "invalid_api_key"})


async def test_e2e_43_a_stop_the_catalogue_has_no_poles_for_says_so_and_stays_on_the_stop_screen(env):
    with patch.object(config_flow, "poles_of_stop", AsyncMock(return_value=[])):
        result = await _stop(env)
    assert (result["step_id"], result["errors"]) == ("stop", {"base": "line_not_found"})


async def test_e2e_43_add_stop_asks_to_pick_a_stop_or_tick_the_numbers(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    result = await manager.async_configure(form["flow_id"], {})
    assert (result["step_id"], result["errors"]) == ("user", {"base": "choose_a_stop"})


async def test_e2e_43_a_line_the_city_then_refuses_is_reported_on_the_pole_screen(env):
    poles = await _stop(env)
    with patch.object(config_flow, "error_for", AsyncMock(return_value=("no_departures", True))):
        result = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert (result["step_id"], result["errors"]) == ("pole", {"base": "no_departures"})


async def test_e2e_43_a_line_that_serves_only_one_pole_of_the_stop_skips_the_pole_screen_and_reports_on_the_stop_screen(env):
    from custom_components.ztm_warsaw.client import StopCatalogue

    only = [{"stop_id": "7009", "stop_nr": "01", "name": NAME, "direction": "x"}]
    with patch.object(config_flow, "poles_for_line", AsyncMock(return_value=only)), patch.object(
        config_flow, "error_for", AsyncMock(return_value=("no_departures", True))
    ):
        result = await _stop(env)
    assert (result["step_id"], result["errors"]) == ("stop", {"base": "no_departures"})
    assert StopCatalogue  # the catalogue is the real one


async def test_e2e_43_the_same_stop_pole_and_line_cannot_be_added_twice_and_another_pole_joins_the_line(env):
    first = await env.submit_wizard(line=LINE, stop="7009", pole="7009/01")
    assert first["type"] == "create_entry"
    again = await env.submit_wizard(line=LINE, stop="7009", pole="7009/01")
    assert (again["type"], again["reason"]) == ("abort", "already_configured")
    other = await env.submit_wizard(line=LINE, stop="7009", pole="7009/02")
    assert (other["type"], other["reason"]) == ("abort", "stop_added")
    entry = first["result"]
    assert sorted(s.data["busstop_nr"] for s in entry.subentries.values()) == ["01", "02"]


async def test_e2e_43_add_stop_on_a_line_lists_its_stops_and_adds_the_pole_picked(env):
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


async def test_e2e_43_add_stop_goes_to_the_numbers_when_the_stops_cannot_be_listed_or_the_numbers_are_chosen(env, tmp_path):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    with patch("custom_components.ztm_warsaw.line_index.INDEX_FILE", tmp_path / "missing.json"):
        env.hass.data.pop("ztm_warsaw_line_index", None)
        unreadable = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    assert (unreadable["step_id"], unreadable["errors"]) == ("manual", {"base": "cannot_load_stops"})
    env.hass.data.pop("ztm_warsaw_line_index", None)
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    manual = await manager.async_configure(form["flow_id"], {"stop": "7009", "manual": True})
    assert manual["step_id"] == "manual"


async def test_e2e_43_add_stop_says_so_when_the_line_serves_no_pole_of_the_stop_or_the_key_is_rejected(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    with patch.object(config_flow, "poles_for_line", AsyncMock(return_value=[])):
        none = await manager.async_configure(form["flow_id"], {"stop": "7009"})
    assert (none["step_id"], none["errors"]) == ("user", {"base": "line_not_found"})
    with patch.object(config_flow, "poles_for_line", AsyncMock(side_effect=ZTMAuthError("rejected"))):
        rejected = await manager.async_configure(none["flow_id"], {"stop": "7009"})
    assert (rejected["step_id"], rejected["errors"]) == ("user", {"base": "invalid_api_key"})


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
    manual = await manager.async_configure(manual["flow_id"], {"stop": "7009", "manual": True})
    env.hass.config_entries.async_update_entry(entry, data={"line": LINE})  # the key is gone
    pole_result = await manager.async_configure(poles["flow_id"], {"pole": "7009/02"})
    manual_result = await manager.async_configure(manual["flow_id"], {"busstop_id": 7009, "busstop_nr": "02"})
    assert (pole_result["type"], pole_result["reason"]) == ("abort", "unknown")
    assert (manual_result["type"], manual_result["reason"]) == ("abort", "unknown")
    assert form["type"] == "form"


async def test_e2e_43_the_catalogue_is_downloaded_once_for_many_setups(env):
    await _line(env)
    first = env.city.count("stops")
    await _line(env, "N25")
    assert env.city.count("stops") == first


async def test_e2e_43_a_token_can_show_the_vehicles_of_the_new_line_on_the_map_from_the_start(env):
    stops = await _line(env, api_key=DEFAULT_TOKEN)
    assert [str(k) for k in stops["data_schema"].schema] == ["stop", "show_vehicles"]
    poles = await env.hass.config_entries.flow.async_configure(stops["flow_id"], {"stop": "7009", "show_vehicles": True})
    done = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert done["type"] == "create_entry", done
    assert dict(done["result"].options) == {"show_vehicles": True}


async def test_e2e_43_the_vehicles_stay_off_unless_they_are_ticked(env):
    poles = await _stop(env, api_key=DEFAULT_TOKEN)
    done = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert dict(done["result"].options) == {}


async def test_e2e_43_ticking_the_vehicles_for_a_line_that_is_set_up_turns_them_on_for_that_line(env):
    entry = await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    done = await env.submit_wizard(line=LINE, stop="7009", pole="7009/02", api_key=DEFAULT_TOKEN, show_vehicles=True)
    await env.settle()
    assert (done["type"], done["reason"]) == ("abort", "stop_added")
    assert entry.options.get("show_vehicles") is True



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


async def test_e2e_43_a_token_already_in_use_can_be_picked_instead_of_pasted_again(env):
    first = await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    form = await _first(env)
    assert (form["type"], form["step_id"]) == ("form", "user_existing")
    assert [str(k) for k in form["data_schema"].schema] == ["token", "api_key", "line", "manual"]
    (choice,) = form["data_schema"].schema["token"].config["options"]
    assert choice["label"] == f"…{DEFAULT_TOKEN[-4:]}  ·  {LINE}", "told by its last four characters and its lines, never whole"
    stops = await env.hass.config_entries.flow.async_configure(form["flow_id"], {"token": choice["value"], "line": "N25"})
    assert (stops["type"], stops["step_id"]) == ("form", "stop"), "no token was pasted"
    poles = await env.hass.config_entries.flow.async_configure(stops["flow_id"], {"stop": "7009"})
    done = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert done["type"] == "create_entry", done
    assert done["result"].data["api_key"] == first.data["api_key"]


async def test_e2e_43_a_token_pasted_below_wins_over_the_one_in_use_and_a_bad_paste_is_refused(env):
    await env.add_entry_via_flow(api_key=DEFAULT_TOKEN)
    refused = await _line(env, api_key="not a key", token="0")
    assert (refused["step_id"], refused["errors"]) == ("user_existing", {"base": "invalid_api_key"})
    again = await env.hass.config_entries.flow.async_configure(refused["flow_id"], {"token": "0", "api_key": DEFAULT_KEY, "line": "N25"})
    assert again["step_id"] == "stop", "an old key pasted is a key: it is checked like one"
    assert [str(k) for k in again["data_schema"].schema] == ["stop"], "it has no vehicles to show"
    key_field = next(k for k in refused["data_schema"].schema if str(k) == "api_key")
    assert key_field.default() == "not a key"


async def test_e2e_43_an_old_key_in_use_is_not_offered_as_a_token(env):
    await env.add_entry_via_flow()  # an old key
    form = await _first(env)
    assert (form["step_id"], [str(k) for k in form["data_schema"].schema]) == ("user", ["api_key", "line", "manual"])
