"""E2E-01 .. E2E-05, E2E-24: getting an entry into Home Assistant (UI flow, restore, options, duplicates)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

import custom_components.ztm_warsaw as integration
from tests.contract_shapes import kv
from custom_components.ztm_warsaw.client import ZTMStopClient
from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import (
    DEFAULT_KEY,
    DEFAULT_TOKEN,
    FULL_CATALOGUE,
    LEGACY_LINES_ID,
    LEGACY_STOPS_ID,
    LEGACY_TIMETABLE_ID,
    EmptyList,
    Hang,
    Html,
    Http,
    InvalidJson,
    NullResult,
    Reset,
    SMALL_CATALOGUE,
    Respond,
    stop_name_for,
)
from .fake_city.data import stops_catalogue_bytes
from .helpers import known_bug

EN = json.loads((Path(integration.__file__).parent / "translations" / "en.json").read_text(encoding="utf-8"))
FLOW_ERROR_STRINGS = EN["config"]["error"]

pytestmark = pytest.mark.e2e


# ===================================================================== E2E-01
async def test_e2e_01_stop_attributes_come_from_the_catalogue_record(env):
    await env.add_entry()
    record = next(
        fields
        for fields in map(kv, json.loads(stops_catalogue_bytes(SMALL_CATALOGUE))["result"])
        if (fields["zespol"], fields["slupek"]) == ("7009", "01")
    )
    attrs = env.state().attributes
    assert attrs["Stop, Name"] == record["nazwa_zespolu"]
    assert attrs["Stop, Street ID"] == record["id_ulicy"]
    assert attrs["Stop, Latitude"] == record["szer_geo"]
    assert attrs["Stop, Longitude"] == record["dlug_geo"]


async def test_e2e_01_fresh_install_through_the_real_config_flow(env):
    """UI path: form -> user input -> city validation -> entry -> platform -> entities, over real HTTP."""
    result = await env.hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert [str(k) for k in result["data_schema"].schema] == [
        "api_key",
        "busstop_id",
        "busstop_nr",
        "line",
        "departures",
    ]
    assert env.city.count() == 0, "showing the form must not call the city"

    entry = await env.add_entry_via_flow(line="151", departures=2)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == "Line 151 from 7009/01"
    assert entry.data == {
        "api_key": DEFAULT_KEY,
        "busstop_id": 7009,  # an int: the schema coerces it, restored entries keep it that way
        "busstop_nr": "01",
        "line": "151",
        "departures": 2,
    }
    assert entry.options == {}
    # What the integration asked the city for, in order: 2 validation calls in the flow, then the setup
    # (stop catalogue first, then the timetable).
    assert [(c.contract, c.endpoint) for c in env.city.calls] == [
        ("legacy", "lines"),
        ("legacy", "timetable"),
        ("legacy", "stops"),
        ("legacy", "timetable"),
    ]
    lines_call, flow_tt, stops_call, setup_tt = env.city.calls
    assert lines_call.query == {"id": LEGACY_LINES_ID, "busstopId": "7009", "busstopNr": "01", "apikey": DEFAULT_KEY}
    expected_tt = {
        "id": LEGACY_TIMETABLE_ID,
        "busstopId": "7009",
        "busstopNr": "01",
        "line": "151",
        "apikey": DEFAULT_KEY,
    }
    assert flow_tt.query == expected_tt
    assert setup_tt.query == expected_tt
    assert set(stops_call.query) == {"id", "apikey"}
    assert env.city.count(contract="new") == 0

    st = env.state()
    assert st.state not in ("unknown", "unavailable")
    assert st.attributes["Stop, Name"] == stop_name_for("7009")
    assert st.attributes["friendly_name"] == f"Line 151 {stop_name_for('7009')} 01"
    assert "Next 2, Headsign" in st.attributes
    assert "Next 3, Headsign" not in st.attributes


# ===================================================================== E2E-02
GOLDEN_ENTITY_ATTRS_WITH_SERVICE = {
    "Line, Number",
    "Line, Type",
    "Line, Timezone",
    "Line, Full Timetable",
    "Stop, ID",
    "Stop, Number",
    "Stop, Name",
    "Stop, Street ID",
    "Stop, Latitude",
    "Stop, Longitude",
    "Stop, Timezone",
    "attribution",
    "device_class",
    "icon",
    "friendly_name",
    "Upcoming, Headsign",
    "Upcoming, Departure Day",
    "Upcoming, Route ID",
    "Upcoming, Brigade",
}
GOLDEN_NEXT_ATTRS = {"Headsign", "Departure Day", "Departure Time", "Route ID", "Brigade"}
GOLDEN_ENTITY_ATTRS_NO_SERVICE = {
    "Line, Number",
    "Line, Type",
    "Line, Timezone",
    "Line, Full Timetable",
    "Stop, ID",
    "Stop, Number",
    "Stop, Name",
    "Stop, Street ID",
    "Stop, Latitude",
    "Stop, Longitude",
    "Stop, Timezone",
    "attribution",
    "device_class",
    "icon",
    "friendly_name",
    "Upcoming, Headsign",
    "Upcoming, Departure Day",
    "Upcoming, Route ID",
    "Upcoming, Brigade",
    "Note",
}


@pytest.mark.parametrize(
    ("line", "line_type", "icon"),
    [("151", "Normal bus", "mdi:bus"), ("N25", "Night bus", "mdi:bus")],
)
async def test_e2e_02_golden_public_contract(env, line, line_type, icon):
    """Everything an automation, dashboard or the entity registry may rely on is frozen here.

    unique_id / entity_id / attribute names / device identifiers / entry.data keys are PUBLIC API of
    the integration; the unique_id format has already changed once without a migration.
    """
    entry = await env.add_entry_via_flow(line=line, departures=3)
    slug = line.lower()

    # --- entry
    assert entry.domain == "ztm_warsaw"
    assert entry.version == 1
    assert entry.unique_id is None
    assert set(entry.data) == {"api_key", "busstop_id", "busstop_nr", "line", "departures"}

    # --- entity registry
    registered = {e.unique_id: e for e in er.async_entries_for_config_entry(env.entity_registry, entry.entry_id)}
    assert set(registered) == {f"line_{line}_from_7009_01", f"line_{line}_from_7009_01_last_update"}
    main = registered[f"line_{line}_from_7009_01"]
    assert (main.entity_id, main.platform, main.domain) == (f"sensor.line_{slug}_from_7009_01", "ztm_warsaw", "sensor")
    assert main.original_device_class == "timestamp"
    assert main.original_icon == icon
    assert main.disabled_by is None
    assert main.entity_category is None
    diag = registered[f"line_{line}_from_7009_01_last_update"]
    assert diag.entity_id == f"sensor.line_{slug}_from_7009_01_last_update"
    assert diag.entity_category == "diagnostic"
    assert diag.disabled_by == er.RegistryEntryDisabler.INTEGRATION  # off by default

    # --- device registry: one device per LINE (shared by every stop of that line)
    devices = dr.async_entries_for_config_entry(env.device_registry, entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.identifiers == {("ztm_warsaw", f"line_{line}")}
    assert (device.name, device.manufacturer, device.model) == (
        f"Line {line}",
        "Zarząd Transportu Miejskiego",
        line_type,
    )
    assert str(device.entry_type) == "service"
    assert device.configuration_url.startswith(
        "https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt=2026-10-16&wtp_md=3&wtp_ln="
    )

    # --- state + attribute names (with service)
    st = env.state(line)
    assert st.attributes["device_class"] == "timestamp"
    assert st.attributes["icon"] == icon
    attrs = set(st.attributes)
    expected = GOLDEN_ENTITY_ATTRS_WITH_SERVICE | {f"Next {n}, {k}" for n in (1, 2, 3) for k in GOLDEN_NEXT_ATTRS}
    assert attrs == expected, (sorted(attrs - expected), sorted(expected - attrs))
    assert st.attributes["Line, Number"] == line
    assert st.attributes["Line, Type"] == line_type
    assert (st.attributes["Stop, ID"], st.attributes["Stop, Number"]) == ("7009", "01")
    assert st.attributes["Line, Timezone"] == st.attributes["Stop, Timezone"] == "Europe/Warsaw"
    assert st.attributes["attribution"] == "Data provided by Miasto Stołeczne Warszawa and Zarząd Transportu Miejskiego (CC BY)"
    assert st.attributes["Line, Full Timetable"] == f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_md=3&wtp_ln={line}"


async def test_e2e_02_golden_attributes_when_there_is_no_service(env):
    """Same entity, different attribute set: the 'no service' shape is public contract too."""
    await env.add_entry_via_flow(line="151", departures=3)
    await env.run_to("2026-10-17 01:00")
    st = env.state("151")
    assert st.state == "unknown"
    assert set(st.attributes) == GOLDEN_ENTITY_ATTRS_NO_SERVICE
    assert st.attributes["Upcoming, Headsign"] == "No service"
    assert st.attributes["Upcoming, Departure Day"] == "Not available"
    assert st.attributes["Note"].startswith("No upcoming schedule available")
    assert st.attributes["Line, Full Timetable"].startswith("https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt=2026-10-17")


# ===================================================================== E2E-03
RESTORED_SHAPES = {
    # name: (entry.data, entry.options, how many "Next N" blocks the sensor must show)
    "plain_1_1_4": (
        {"api_key": DEFAULT_KEY, "busstop_id": 7009, "busstop_nr": "01", "line": "151", "departures": 1},
        {},
        1,
    ),
    "options_override_data": (
        {"api_key": DEFAULT_KEY, "busstop_id": 7009, "busstop_nr": "01", "line": "151", "departures": 1},
        {"departures": 3},
        3,
    ),
    "string_stop_id_and_padding": (
        {"api_key": f" {DEFAULT_KEY} ", "busstop_id": " 7009 ", "busstop_nr": "01", "line": " 151 ", "departures": 2},
        {},
        2,
    ),
    "legacy_alias_keys_no_departures": (
        {"apikey": DEFAULT_KEY, "busstopId": "7009", "busstopNr": "01", "linia": "151"},
        {},
        1,
    ),
}


@pytest.mark.parametrize("shape", RESTORED_SHAPES)
async def test_e2e_03_restored_1_1_4_entries_load_and_call_the_city_unchanged(env, shape):
    data, options, next_blocks = RESTORED_SHAPES[shape]
    entry = await env.add_entry(data=data, options=options)

    assert entry.state is ConfigEntryState.LOADED
    tt = env.city.matching("timetable")
    assert len(tt) == 1
    assert tt[0].query == {
        "id": LEGACY_TIMETABLE_ID,
        "apikey": DEFAULT_KEY,
        "busstopId": "7009",
        "busstopNr": "01",
        "line": "151",
    }, "the GET the city sees must not change between versions"
    attrs = env.state().attributes
    assert f"Next {next_blocks}, Headsign" in attrs
    assert f"Next {next_blocks + 1}, Headsign" not in attrs


# ===================================================================== E2E-04
def _saturday(env):
    env.move_to("2026-10-17 12:00")


TRANSPORT_KEYS = {"api_http_error", "api_connection_error", "cannot_connect"}
FLOW_CASES = [
    # id, user-input overrides, city scripting, accepted error keys (semantic, so a renamed key still counts)
    ("bad_key", {"api_key": "wrong-key"}, lambda e: None, {"invalid_api_key"}),
    ("unknown_stop", {"stop_id": 7999}, lambda e: None, {"line_check_failed", "line_not_found", "cannot_find_stop"}),
    ("line_not_at_stop", {"line": "999"}, lambda e: None, {"line_not_found"}),
    ("line_not_running_today", {"line": "411"}, _saturday, {"line_not_found", "no_departures"}),
    ("stop_number_not_two_digits", {"stop_nr": "1"}, lambda e: None, {"invalid_stop_number"}),
    ("http_500", {}, lambda e: e.city.always("lines", Http(500)), TRANSPORT_KEYS),
    ("connection_reset", {}, lambda e: e.city.always("lines", Reset()), TRANSPORT_KEYS),
    ("invalid_json", {}, lambda e: e.city.always("lines", InvalidJson()), TRANSPORT_KEYS),
    ("html_maintenance_page", {}, lambda e: e.city.always("lines", Html()), TRANSPORT_KEYS),
    ("not_a_key_at_all", {"api_key": "wrong-key"}, lambda e: None, {"invalid_api_key"}),
    ("token_rejected", {"api_key": DEFAULT_TOKEN}, lambda e: e.city.valid_tokens.clear(), {"invalid_token_or_unavailable"}),
    ("token_unknown_stop", {"api_key": DEFAULT_TOKEN, "stop_id": 7999}, lambda e: None, {"line_not_found"}),
    ("token_lines_outage", {"api_key": DEFAULT_TOKEN}, lambda e: e.city.always("lines", Http(500), contract="new"), TRANSPORT_KEYS),
    ("timetable_only_unreadable_rows", {}, lambda e: e.city.always("timetable", Respond(200, {"result": [[{"key": "czas", "value": "garbage"}]]}, name="junk")), {"no_valid_times"}),
    ("timetable_null", {}, lambda e: e.city.always("timetable", NullResult()), {"no_departures"}),
    ("timetable_empty", {}, lambda e: e.city.always("timetable", EmptyList()), {"no_valid_times", "no_departures"}),
]


@pytest.mark.parametrize(("case", "overrides", "arrange", "accepted"), FLOW_CASES, ids=[c[0] for c in FLOW_CASES])
async def test_e2e_04_config_flow_failures_are_reported_not_swallowed(env, case, overrides, arrange, accepted):
    arrange(env)
    result = await env.submit_flow(**overrides)

    assert result["type"] == "form", f"{case}: a failing validation must keep the form open"
    assert result["errors"]["base"] in accepted, result["errors"]
    assert env.hass.config_entries.async_entries(DOMAIN) == [], "nothing may be created on failure"
    if case in {"http_500", "connection_reset", "invalid_json", "html_maintenance_page"}:
        assert result["errors"]["base"] != "invalid_api_key", "an outage must never look like a wrong key"


async def test_e2e_04_an_unexpected_error_is_reported_as_unknown_and_only_its_class_is_logged(env, caplog):
    with patch.object(ZTMStopClient, "get_lines", AsyncMock(side_effect=RuntimeError(f"boom {DEFAULT_KEY}"))):
        result = await env.submit_flow()
    assert result["errors"]["base"] == "unknown"
    assert "RuntimeError" in caplog.text
    assert DEFAULT_KEY not in caplog.text


async def test_e2e_04_config_flow_slow_server_times_out_with_a_connection_error(env):
    env.city.always("lines", Hang())
    task = asyncio.ensure_future(env.submit_flow())
    result = await env.drive_timeouts(task)
    assert result["type"] == "form"
    assert result["errors"]["base"] in TRANSPORT_KEYS
    assert env.sleeps.requested == [1.5], "one retry with the documented back-off, no real waiting"


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            c[0],
            id=c[0],
        )
        for c in FLOW_CASES
    ],
)
async def test_e2e_04_every_error_the_user_can_see_has_a_translation(env, case):
    _, overrides, arrange, _ = next(c for c in FLOW_CASES if c[0] == case)
    arrange(env)
    result = await env.submit_flow(**overrides)
    assert result["type"] == "form", f"case {case!r} is meant to show an error"
    assert result["errors"], f"case {case!r} is meant to show an error"
    key = result["errors"]["base"]
    assert key in FLOW_ERROR_STRINGS, f"flow error '{key}' has no string in translations/en.json"


@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param({"line": " 151 "}, id="line_with_spaces"),
        pytest.param({"api_key": f"  {DEFAULT_KEY}\n"}, id="key_with_newline"),
    ],
)
async def test_e2e_04_pasted_whitespace_is_forgiven(env, user_input):
    result = await env.submit_flow(**user_input)
    assert result["type"] == "create_entry", result.get("errors")
    assert result["result"].state is ConfigEntryState.LOADED


async def test_e2e_04_user_input_cannot_inject_query_parameters(env):
    result = await env.submit_flow(api_key=f"{DEFAULT_KEY}&busstopId=9999&id={LEGACY_STOPS_ID}")
    if not env.city.calls:  # rejecting a key that is not a key before any request is a fine fix as well
        assert result["type"] == "form", "nothing was sent, so the flow must have refused the key"
        assert result["errors"], "nothing was sent, so the flow must have refused the key"
    for call in env.city.calls:
        counts = {k: len(v) for k, v in parse_qs(call.query_string).items()}
        assert all(n == 1 for n in counts.values()), f"duplicated parameters reached the city: {counts}"


# ===================================================================== E2E-05
async def test_e2e_05_options_flow_changes_departures_and_reloads_the_entry(env):
    entry = await env.add_entry_via_flow(departures=1)
    assert "Next 2, Headsign" not in env.state().attributes
    flow = env.hass.config_entries.options

    form = await flow.async_init(entry.entry_id)
    assert form["type"] == "form"
    assert form["step_id"] == "init"
    assert [str(k) for k in form["data_schema"].schema] == ["departures"]
    assert form["data_schema"]({}) == {"departures": 1}  # default = current value

    done = await flow.async_configure(form["flow_id"], {"departures": 3})
    assert done["type"] == "create_entry"
    await env.settle()

    assert entry.options == {"departures": 3}
    assert entry.data["departures"] == 1, "options never rewrite entry.data"
    assert entry.state is ConfigEntryState.LOADED
    attrs = env.state().attributes
    assert {f"Next {n}, Headsign" for n in (1, 2, 3)} <= set(attrs)
    assert "Next 4, Headsign" not in attrs
    # the entity (and its registry identity) survived the reload
    assert env.hass.states.get("sensor.line_151_from_7009_01") is not None
    assert len(er.async_entries_for_config_entry(env.entity_registry, entry.entry_id)) == 2


@pytest.mark.city(catalogue_bytes=FULL_CATALOGUE)
@known_bug("stops-catalogue-redownloaded", "every reload re-downloads the whole 1.6 MB stops catalogue")
async def test_e2e_05_options_change_does_not_redownload_the_stop_catalogue(env):
    entry = await env.add_entry(departures=1)
    assert env.city.count("stops") == 1
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    await flow.async_configure(form["flow_id"], {"departures": 2})
    await env.settle()
    assert env.city.count("stops") == 1, f"{env.city.count('stops')} catalogue downloads for one entry"


@known_bug("update-listener-reloads-on-any-change", "the update listener reloads the entry on ANY change, e.g. a plain title rename")
async def test_e2e_05_renaming_an_entry_does_not_reload_it(env):
    entry = await env.add_entry()
    assert entry.state is ConfigEntryState.LOADED
    before = env.city.count()
    assert before > 0, "precondition: setup talked to the city"
    env.hass.config_entries.async_update_entry(entry, title="My bus")
    await env.settle()
    assert env.city.count() == before, "a rename must not hit the city"


# ===================================================================== E2E-24
@known_bug("duplicate-entries-allowed", "the same stop+pole+line can be added twice; the second entry silently loses its sensor")
async def test_e2e_24_adding_the_same_stop_pole_and_line_twice_is_refused(env):
    await env.add_entry_via_flow()
    second = await env.submit_flow()
    assert second["type"] == "abort", second
    assert second["reason"] == "already_configured"


async def test_e2e_24_existing_duplicates_keep_loading(env):
    """Users already have duplicates; whatever fixes duplicate entries must not break or delete them."""
    first = await env.add_entry(setup=False)
    second = await env.add_entry(setup=False)
    await env.hass.config_entries.async_setup(first.entry_id)
    await env.settle()
    assert first.state is ConfigEntryState.LOADED
    assert second.state is ConfigEntryState.LOADED
    assert env.hass.states.get("sensor.line_151_from_7009_01") is not None
