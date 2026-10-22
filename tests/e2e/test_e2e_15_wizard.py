"""E2E-43: the setup dialog is short screens (the key and part of the stop's name, the stop if the name fits several, the line, the pole with its direction), not four empty fields."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState

from custom_components.ztm_warsaw import config_flow
from custom_components.ztm_warsaw.client import ZTMAuthError, StopCatalogue
from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN, stop_name_for

pytestmark = pytest.mark.e2e

LINE = "151"
NAME = stop_name_for("7009")


async def _first(env):
    """The first screen of the dialog."""
    return await env.hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def _search(env, query, *, api_key=DEFAULT_KEY, **extra):
    """Open the dialog and submit its first screen."""
    form = await _first(env)
    return await env.hass.config_entries.flow.async_configure(form["flow_id"], {"api_key": api_key, "stop": query, **extra})


async def test_e2e_43_the_first_screen_asks_for_the_key_and_a_part_of_the_name_and_does_not_call_the_city(env):
    form = await _first(env)
    assert (form["type"], form["step_id"], form["errors"]) == ("form", "user", {})
    assert [str(k) for k in form["data_schema"].schema] == ["api_key", "stop", "manual"]
    assert env.city.count() == 0


async def test_e2e_43_a_part_of_the_name_leads_to_the_stop_then_the_line_then_the_pole_with_its_direction(env):
    stops = await _search(env, NAME[:12].lower())
    assert (stops["type"], stops["step_id"]) == ("form", "stop"), "the name fits more than one stop"
    options = stops["data_schema"].schema["stop"].config["options"]
    assert {"label": f"{NAME} (7009)", "value": "7009"} in options
    lines = await env.hass.config_entries.flow.async_configure(stops["flow_id"], {"stop": "7009"})
    assert (lines["type"], lines["step_id"]) == ("form", "line")
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


async def test_e2e_43_a_line_that_serves_only_one_pole_of_the_stop_skips_the_pole_screen(env):
    done = await env.submit_wizard(query="7009/01", line=LINE)
    assert (done["type"], done["result"].data["line"]) == ("create_entry", LINE), "a pole typed as numbers is the only pole"


async def test_e2e_43_the_words_of_a_name_find_it_whatever_the_abbreviation(env):
    from custom_components.ztm_warsaw.client import _matches

    assert _matches(None, "dworzec centralny", "1", "01", "Dw. Centralny")
    assert _matches(None, "dw centr", "1", "01", "Dw. Centralny")
    assert _matches(None, "osiedle gorczewska", "1", "01", "Os. Gorczewska")
    assert not _matches(None, "dworzec zachodni", "1", "01", "Dw. Centralny")


async def test_e2e_43_a_stop_id_goes_to_its_lines_and_the_poles_it_has_are_chosen_after_the_line(env):
    lines = await _search(env, "7009")
    assert (lines["type"], lines["step_id"]) == ("form", "line"), "one stop: it is not asked which"
    poles = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert [o["value"] for o in poles["data_schema"].schema["pole"].config["options"]][:2] == ["7009/01", "7009/02"]


async def test_e2e_43_nothing_found_stays_on_the_first_screen_with_the_key_kept_and_says_so(env):
    result = await _search(env, "no such stop anywhere")
    assert (result["type"], result["step_id"], result["errors"]) == ("form", "user", {"base": "no_stop_found"})
    key_field = next(k for k in result["data_schema"].schema if str(k) == "api_key")
    assert key_field.default() == DEFAULT_KEY, "the key is not asked for again"


async def test_e2e_43_a_search_that_matches_too_many_stops_asks_for_more_of_the_name(env):
    result = await _search(env, "Testowa")  # every stop of the fake catalogue
    assert (result["step_id"], result["errors"]) == ("user", {"base": "too_many_matches"})


async def test_e2e_43_a_key_that_is_neither_an_old_key_nor_a_token_is_refused_before_anything_is_asked_of_the_city(env):
    result = await _search(env, "7009", api_key="not a key")
    assert (result["step_id"], result["errors"]) == ("user", {"base": "invalid_api_key"})
    assert env.city.count() == 0


async def test_e2e_43_a_list_of_stops_that_cannot_be_read_leads_to_the_form_of_the_numbers(env):
    with patch.object(StopCatalogue, "search", AsyncMock(return_value=(False, []))):
        result = await _search(env, "7009")
    assert (result["step_id"], result["errors"]) == ("manual", {"base": "cannot_load_stops"})
    assert [str(k) for k in result["data_schema"].schema] == ["api_key", "busstop_id", "busstop_nr", "line"]


async def test_e2e_43_i_know_the_numbers_goes_straight_to_the_form_of_the_numbers(env):
    result = await _search(env, "7009", manual=True)
    assert (result["step_id"], result["errors"]) == ("manual", {})


async def test_e2e_43_a_stop_no_line_stops_at_today_says_so_and_goes_back(env):
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=[])):
        result = await _search(env, "7009")
    assert (result["step_id"], result["errors"]) == ("user", {"base": "no_lines"})


async def test_e2e_43_lines_the_city_does_not_give_are_reported_and_the_search_offered_again(env):
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=None)):
        result = await _search(env, "7009")
    assert (result["step_id"], result["errors"]) == ("user", {"base": "cannot_load_lines"})


async def test_e2e_43_a_key_the_city_rejects_at_the_lines_goes_back_to_the_first_screen(env):
    with patch.object(config_flow, "lines_at", AsyncMock(side_effect=ZTMAuthError("rejected"))):
        result = await _search(env, "7009")
    assert (result["step_id"], result["errors"]) == ("user", {"base": "invalid_api_key"})


async def test_e2e_43_a_name_that_fits_several_stops_goes_back_to_the_choice_of_the_stop_when_no_line_is_found(env):
    stops = await _search(env, NAME[:12].lower())
    with patch.object(config_flow, "lines_at", AsyncMock(return_value=[])):
        result = await env.hass.config_entries.flow.async_configure(stops["flow_id"], {"stop": "7009"})
    assert (result["step_id"], result["errors"]) == ("stop", {"base": "no_lines"})


async def test_e2e_43_a_line_that_no_pole_serves_any_more_is_reported_on_the_line_screen(env):
    lines = await _search(env, "7009")
    with patch.object(config_flow, "poles_for_line", AsyncMock(return_value=[])):
        result = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert (result["step_id"], result["errors"]) == ("line", {"base": "cannot_load_lines"})


async def test_e2e_43_a_line_the_city_then_refuses_is_reported_on_the_pole_screen(env):
    lines = await _search(env, "7009")
    poles = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    with patch.object(config_flow, "error_for", AsyncMock(return_value=("no_departures", True))):
        result = await env.hass.config_entries.flow.async_configure(poles["flow_id"], {"pole": "7009/01"})
    assert (result["step_id"], result["errors"]) == ("pole", {"base": "no_departures"})


async def test_e2e_43_a_line_the_city_then_refuses_at_its_only_pole_is_reported_on_the_line_screen(env):
    lines = await _search(env, "7009/01")
    with patch.object(config_flow, "error_for", AsyncMock(return_value=("no_departures", True))):
        result = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert (result["step_id"], result["errors"]) == ("line", {"base": "no_departures"})


async def test_e2e_43_the_same_stop_pole_and_line_cannot_be_added_twice_and_another_stop_joins_the_line(env):
    first = await env.submit_wizard(query="7009/01", line=LINE)
    assert first["type"] == "create_entry"
    again = await env.submit_wizard(query="7009/01", line=LINE)
    assert (again["type"], again["reason"]) == ("abort", "already_configured")
    other = await env.submit_wizard(query="7009/02", line=LINE)
    assert (other["type"], other["reason"]) == ("abort", "stop_added")
    entry = first["result"]
    assert sorted(s.data["busstop_nr"] for s in entry.subentries.values()) == ["01", "02"]


async def test_e2e_43_add_stop_on_a_line_searches_by_name_and_reports_what_goes_wrong(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    nothing = await manager.async_configure(form["flow_id"], {"stop": "no such stop anywhere"})
    assert (nothing["step_id"], nothing["errors"]) == ("user", {"base": "no_stop_found"})
    many = await manager.async_configure(form["flow_id"], {"stop": "Testowa"})
    assert (many["step_id"], many["errors"]) == ("user", {"base": "too_many_matches"})
    with patch.object(StopCatalogue, "search", AsyncMock(return_value=(None, []))):
        unreadable = await manager.async_configure(form["flow_id"], {"stop": "7009"})
    assert (unreadable["step_id"], unreadable["errors"]) == ("manual", {"base": "cannot_load_stops"})


async def test_e2e_43_add_stop_refuses_a_pole_the_line_does_not_stop_at(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    poles = await manager.async_configure(form["flow_id"], {"stop": "7009"})
    assert poles["step_id"] == "pole", "the line serves both poles of the stop"
    with patch.object(config_flow, "error_for", AsyncMock(return_value=("line_not_found", True))):
        result = await manager.async_configure(poles["flow_id"], {"pole": "7009/02"})
    assert (result["step_id"], result["errors"]) == ("user", {"base": "line_not_found"})
    assert len(entry.subentries) == 1


async def test_e2e_43_the_catalogue_is_downloaded_once_for_many_searches(env):
    await _search(env, "7009")
    first = env.city.count("stops")
    await _search(env, "7009/02")
    assert env.city.count("stops") == first


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


async def test_e2e_43_add_stop_with_a_line_that_serves_one_pole_adds_it_without_asking_which(env):
    entry = await env.add_entry_via_flow(line=LINE)
    manager = env.hass.config_entries.subentries
    form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
    with patch.object(config_flow, "poles_for_line", AsyncMock(return_value=[{"stop_id": "7009", "stop_nr": "02", "name": NAME, "direction": "x"}])):
        done = await manager.async_configure(form["flow_id"], {"stop": "7009"})
    assert done["type"] == "create_entry", done


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


async def test_e2e_43_a_key_the_city_rejects_when_the_poles_of_the_line_are_looked_up_goes_back_to_the_first_screen(env):
    lines = await _search(env, "7009")
    with patch.object(config_flow, "poles_for_line", AsyncMock(side_effect=ZTMAuthError("rejected"))):
        result = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert (result["step_id"], result["errors"]) == ("user", {"base": "invalid_api_key"})


async def test_e2e_43_a_token_can_show_the_vehicles_of_the_new_line_on_the_map_from_the_start(env):
    lines = await _search(env, "7009/01", api_key=DEFAULT_TOKEN)
    assert "show_vehicles" in [str(k) for k in lines["data_schema"].schema]
    done = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE, "show_vehicles": True})
    assert done["type"] == "create_entry", done
    assert dict(done["result"].options) == {"show_vehicles": True}


async def test_e2e_43_the_vehicles_stay_off_unless_they_are_ticked_and_an_old_key_is_not_asked(env):
    lines = await _search(env, "7009/01", api_key=DEFAULT_TOKEN)
    done = await env.hass.config_entries.flow.async_configure(lines["flow_id"], {"line": LINE})
    assert dict(done["result"].options) == {}
    old = await _search(env, "7009/01")
    assert "show_vehicles" not in [str(k) for k in old["data_schema"].schema], "positions are a service of the token"
