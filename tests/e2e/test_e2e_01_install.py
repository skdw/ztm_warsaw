"""E2E-01 .. E2E-05, E2E-24: getting an entry into Home Assistant (UI flow, restore, options, duplicates)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs

import pytest
from homeassistant.helpers import issue_registry as ir
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

import custom_components.ztm_warsaw as integration
from tests.contract_shapes import kv
from custom_components.ztm_warsaw.client import ZTMStopClient
from custom_components.ztm_warsaw.const import DOMAIN
from custom_components.ztm_warsaw.utils import get_line_badge

from .fake_city import (
    DEFAULT_KEY,
    DEFAULT_TOKEN,
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
from .helpers import subentry_of

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
    ]
    assert env.city.count() == 0, "showing the form must not call the city"

    entry = await env.add_entry_via_flow(line="151")

    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == f"Line 151 · {stop_name_for('7009')} 01"  # an entry is a line, titled with its stops ...
    assert entry.data == {
        "api_key": DEFAULT_KEY,
        "line": "151",
        "departures": 3,  # no longer asked (3 are always listed); the key stays
    }
    assert set(entry.options) <= {"generated_title"}  # nothing is asked for in options; only the title this integration made is remembered
    (stop,) = entry.subentries.values()  # ... and its stops are subentries
    assert stop.subentry_type == "stop"
    assert stop.title == f"{stop_name_for('7009')} 01"  # the stop's name, not its number
    assert stop.unique_id == "7009_01"
    assert dict(stop.data) == {"busstop_id": 7009, "busstop_nr": "01"}  # an int: the schema coerces it
    # What the integration asked the city for, in order: 2 validation calls in the flow, then the setup
    # (the timetable first, then the stop catalogue for the name).
    assert [(c.contract, c.endpoint) for c in env.city.calls] == [
        ("legacy", "lines"),
        ("legacy", "timetable"),
        ("legacy", "timetable"),
        ("legacy", "stops"),
    ]
    lines_call, flow_tt, setup_tt, stops_call = env.city.calls
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
    assert st.attributes["entity_picture"] == get_line_badge("151")  # the pin on the map card shows the line
    assert "Next 3, Headsign" in st.attributes
    assert "Next 4, Headsign" not in st.attributes


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
    "latitude",  # the standard names: the stop is a pin on the map card
    "longitude",
    "Stop, Timezone",
    "attribution",
    "device_class",
    "icon",
    "entity_picture",  # added in 1.2.0: a badge with the line, the pin on the map card
    "friendly_name",
    "Upcoming, Headsign",
    "Upcoming, Departure Day",
    "Upcoming, Route ID",
    "Upcoming, Brigade",
}
GOLDEN_NEXT_ATTRS = {"Headsign", "Departure Day", "Departure Time", "Route ID", "Brigade"}
TIMETABLE_SPAN = {"Timetable, First Departure", "Timetable, Last Departure"}  # added in 1.2.0
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
    "latitude",  # the standard names: the stop is a pin on the map card
    "longitude",
    "Stop, Timezone",
    "attribution",
    "device_class",
    "icon",
    "entity_picture",  # added in 1.2.0: a badge with the line, the pin on the map card
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
    entry = await env.add_entry_via_flow(line=line)
    slug = line.lower()

    # --- entry
    assert entry.domain == "ztm_warsaw"
    assert entry.version == 2  # a line with its stops as subentries; a 1.1.x entry (version 1, one stop) is read as it was
    assert entry.unique_id is None
    assert set(entry.data) == {"api_key", "line", "departures"}
    (stop,) = entry.subentries.values()
    assert set(stop.data) == {"busstop_id", "busstop_nr"}

    # --- entity registry
    registered = {e.unique_id: e for e in er.async_entries_for_config_entry(env.entity_registry, entry.entry_id)}
    assert set(registered) == {
        f"line_{line}_from_7009_01",
        f"line_{line}_from_7009_01_last_update",
        f"line_{line}_from_7009_01_calendar",  # added in 1.2.0: the timetable as a calendar (the other two are unchanged)
        f"line_{line}_from_7009_01_next_1",  # added in 1.2.0: the departures after the next one as sensors of their own
        f"line_{line}_from_7009_01_next_2",
        f"line_{line}_from_7009_01_next_3",
    }
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
    for position in (1, 2, 3):
        following = registered[f"line_{line}_from_7009_01_next_{position}"]
        assert following.entity_id == f"sensor.line_{slug}_from_7009_01_next_{position}"
        assert following.original_device_class == "timestamp"
        assert following.disabled_by == er.RegistryEntryDisabler.INTEGRATION  # off by default
    calendar = registered[f"line_{line}_from_7009_01_calendar"]
    assert calendar.entity_id == f"calendar.line_{slug}_from_7009_01_timetable"
    assert calendar.disabled_by == er.RegistryEntryDisabler.INTEGRATION  # off by default: it holds every departure of the day

    # --- device registry: a stop of a line entry is a device of its own (a device belongs to one subentry)
    devices = dr.async_entries_for_config_entry(env.device_registry, entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.identifiers == {("ztm_warsaw", f"line_{line}_7009_01")}
    assert subentry_of(device, entry.entry_id) == next(iter(entry.subentries))  # the stop's subentry
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
    expected = GOLDEN_ENTITY_ATTRS_WITH_SERVICE | TIMETABLE_SPAN | {f"Next {n}, {k}" for n in (1, 2, 3) for k in GOLDEN_NEXT_ATTRS}
    assert attrs == expected, (sorted(attrs - expected), sorted(expected - attrs))
    assert st.attributes["Line, Number"] == line
    assert st.attributes["Line, Type"] == line_type
    assert (st.attributes["Stop, ID"], st.attributes["Stop, Number"]) == ("7009", "01")
    assert st.attributes["Line, Timezone"] == st.attributes["Stop, Timezone"] == "Europe/Warsaw"
    assert st.attributes["attribution"] == "Data provided by Miasto Stołeczne Warszawa and Zarząd Transportu Miejskiego (CC BY)"
    assert st.attributes["Line, Full Timetable"] == f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_md=3&wtp_ln={line}"


async def test_e2e_02_golden_attributes_when_there_is_no_service(env):
    """Same entity, different attribute set: the 'no service' shape is public contract too."""
    await env.add_entry_via_flow(line="151")
    await env.run_to("2026-10-17 01:00")
    st = env.state("151")
    assert st.state == "unknown"
    assert set(st.attributes) == GOLDEN_ENTITY_ATTRS_NO_SERVICE | TIMETABLE_SPAN
    assert st.attributes["Upcoming, Headsign"] == "No service"
    assert st.attributes["Upcoming, Departure Day"] == "Not available"
    assert st.attributes["Note"].startswith("No upcoming schedule available")
    assert st.attributes["Line, Full Timetable"].startswith("https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt=2026-10-17")


# ===================================================================== E2E-03
RESTORED_SHAPES = {
    # name: (entry.data, entry.options). The stored number of departures is ignored: three are always listed.
    "plain_1_1_4": (
        {"api_key": DEFAULT_KEY, "busstop_id": 7009, "busstop_nr": "01", "line": "151", "departures": 1},
        {},
    ),
    "options_override_data": (
        {"api_key": DEFAULT_KEY, "busstop_id": 7009, "busstop_nr": "01", "line": "151", "departures": 1},
        {"departures": 3},
    ),
    "string_stop_id_and_padding": (
        {"api_key": f" {DEFAULT_KEY} ", "busstop_id": " 7009 ", "busstop_nr": "01", "line": " 151 ", "departures": 2},
        {},
    ),
    "legacy_alias_keys_no_departures": (
        {"apikey": DEFAULT_KEY, "busstopId": "7009", "busstopNr": "01", "linia": "151"},
        {},
    ),
}


@pytest.mark.parametrize("shape", RESTORED_SHAPES)
async def test_e2e_03_restored_1_1_4_entries_load_and_call_the_city_unchanged(env, shape):
    data, options = RESTORED_SHAPES[shape]
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
    assert "Next 3, Headsign" in attrs
    assert "Next 4, Headsign" not in attrs


# ===================================================================== E2E-04
def _saturday(env):
    """Move the clock to a Saturday midday."""
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
NEW_KEY = "22222222-3333-4444-8555-666666666666"  # gitleaks:allow  (synthetic)
NEW_TOKEN = DEFAULT_TOKEN + "2"  # another synthetic token of the same shape


async def test_e2e_05_the_token_form_replaces_a_token(env):
    token = await env.add_entry(line="151", api_key=DEFAULT_TOKEN)
    flow = env.hass.config_entries.options
    form = await flow.async_init(token.entry_id)
    assert (form["type"], form["step_id"]) == ("form", "token")  # not the form that nudges an old key to a token
    env.city.valid_tokens.add(NEW_TOKEN)
    done = await flow.async_configure(form["flow_id"], {"api_key": f" {NEW_TOKEN} "})
    await env.settle()
    assert done["type"] == "create_entry", done.get("errors")
    assert token.data["api_key"] == NEW_TOKEN


async def test_e2e_05_the_options_flow_asks_for_a_key_and_says_which_kind_is_in_use(env):
    entry = await env.add_entry_via_flow()
    form = await env.hass.config_entries.options.async_init(entry.entry_id)
    assert (form["type"], form["step_id"]) == ("form", "init")
    assert [str(k) for k in form["data_schema"].schema] == ["api_key"]
    assert form["description_placeholders"] == {"current": "api.um.warszawa.pl", "portal": "https://dane.um.warszawa.pl/pl/key-api"}


async def test_e2e_05_a_new_key_replaces_the_old_one_and_reloads_the_entry_once(env):
    entry = await env.add_entry_via_flow()
    env.city.valid_keys.add(NEW_KEY)
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    with patch.object(env.hass.config_entries, "async_reload", wraps=env.hass.config_entries.async_reload) as reload:
        done = await flow.async_configure(form["flow_id"], {"api_key": f" {NEW_KEY} "})
        await env.settle()
    assert done["type"] == "create_entry"
    assert entry.data["api_key"] == NEW_KEY
    (stop,) = entry.subentries.values()
    assert (stop.data["busstop_id"], stop.data["busstop_nr"], entry.data["line"]) == (7009, "01", "151")
    assert set(entry.options) <= {"generated_title"}  # nothing is asked for in options; only the title this integration made is remembered
    assert reload.call_count == 1
    assert entry.state is ConfigEntryState.LOADED
    assert env.hass.states.get("sensor.line_151_from_7009_01") is not None


async def test_e2e_05_a_token_replaces_an_old_key(env):
    entry = await env.add_entry_via_flow()
    env.city.valid_keys.add(DEFAULT_TOKEN)
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    await flow.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert entry.data["api_key"] == DEFAULT_TOKEN
    assert env.city.count(contract="new") > 0, "the entry talks to the new API now"
    form = await flow.async_init(entry.entry_id)
    assert (form["type"], form["step_id"]) == ("form", "token")  # a token is not asked to move to a token
    assert form["description_placeholders"] == {"current": "dane.um.warszawa.pl", "portal": "https://dane.um.warszawa.pl/pl/key-api"}


async def test_e2e_05_a_key_the_city_rejects_is_refused_and_the_entry_keeps_its_own(env):
    entry = await env.add_entry_via_flow()
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    done = await flow.async_configure(form["flow_id"], {"api_key": NEW_KEY})  # not among the valid keys
    assert (done["type"], done["errors"]) == ("form", {"base": "invalid_api_key"})
    assert done["step_id"] == "init"  # an old key that is refused stays on the form that nudges to a token
    assert entry.data["api_key"] == DEFAULT_KEY


async def test_e2e_05_the_options_flow_does_not_ask_for_the_number_of_departures_any_more(env):
    entry = await env.add_entry_via_flow()
    attrs = env.state().attributes
    assert {f"Next {n}, Headsign" for n in (1, 2, 3)} <= set(attrs), "three are always listed"
    assert "Next 4, Headsign" not in attrs
    form = await env.hass.config_entries.options.async_init(entry.entry_id)
    assert "departures" not in [str(k) for k in form["data_schema"].schema]


async def test_e2e_05_the_stop_is_a_pin_on_the_map(env):
    await env.add_entry()
    attrs = env.state().attributes
    assert (attrs["latitude"], attrs["longitude"]) == (float(attrs["Stop, Latitude"]), float(attrs["Stop, Longitude"]))


async def test_e2e_05_options_change_does_not_redownload_the_stop_catalogue(env):
    entry = await env.add_entry()
    assert env.city.count("stops") == 1
    env.city.valid_keys.add(NEW_KEY)
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    await flow.async_configure(form["flow_id"], {"api_key": NEW_KEY})
    await env.settle()
    assert env.city.count("stops") == 1, f"{env.city.count('stops')} catalogue downloads for one entry"


async def test_e2e_05_renaming_an_entry_does_not_reload_it(env):
    entry = await env.add_entry()
    assert entry.state is ConfigEntryState.LOADED
    before = env.city.count()
    assert before > 0, "precondition: setup talked to the city"
    env.hass.config_entries.async_update_entry(entry, title="My bus")
    await env.settle()
    assert env.city.count() == before, "a rename must not hit the city"


# ===================================================================== E2E-24
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


async def test_e2e_24_the_refusal_ignores_spaces_but_not_a_different_pole(env):
    await env.add_entry_via_flow(line="N25")
    again = await env.submit_flow(line=" N25 ")
    assert (again["type"], again["reason"]) == ("abort", "already_configured")
    other_pole = await env.submit_flow(line="N25", stop_nr="02")
    assert (other_pole["type"], other_pole["reason"]) == ("abort", "stop_added"), "another pole is another sensor of the line"
    (entry,) = env.hass.config_entries.async_entries("ztm_warsaw")
    assert sorted(s.data["busstop_nr"] for s in entry.subentries.values()) == ["01", "02"]


async def test_e2e_24_a_refused_duplicate_makes_no_request_to_the_city(env):
    first = await env.add_entry()
    assert first.state is ConfigEntryState.LOADED
    before = env.city.count()
    second = await env.submit_flow()
    assert second["type"] == "abort"
    assert env.city.count() == before


async def test_e2e_24_existing_duplicates_get_a_repairs_notice_that_goes_with_the_twin(env):
    first = await env.add_entry(setup=False)
    second = await env.add_entry(setup=False)
    await env.hass.config_entries.async_setup(first.entry_id)
    await env.settle()
    issues = ir.async_get(env.hass)
    assert issues.async_get_issue(DOMAIN, f"duplicate_{second.entry_id}") is not None
    assert issues.async_get_issue(DOMAIN, f"duplicate_{first.entry_id}") is None, "the first one set up saw no twin yet"
    await env.hass.config_entries.async_remove(first.entry_id)
    await env.settle()
    assert issues.async_get_issue(DOMAIN, f"duplicate_{second.entry_id}") is None


async def test_e2e_24_an_entry_with_broken_data_does_not_break_the_check(env):
    await env.add_entry(data={"api_key": "x"}, setup=False)
    again = await env.submit_flow()
    assert again["type"] != "abort"


async def test_e2e_24_the_notice_goes_even_when_the_removed_twin_is_still_listed(env):
    """Home Assistant before 2026.10 calls async_remove_entry while the entry is still in the list (a review finding)."""
    first = await env.add_entry(setup=False)
    second = await env.add_entry(setup=False)
    await env.hass.config_entries.async_setup(first.entry_id)
    await env.settle()
    issues = ir.async_get(env.hass)
    assert issues.async_get_issue(DOMAIN, f"duplicate_{second.entry_id}") is not None
    await integration.async_remove_entry(env.hass, first)  # first is still in env.hass.config_entries here
    assert issues.async_get_issue(DOMAIN, f"duplicate_{second.entry_id}") is None


async def test_e2e_24_two_flows_for_one_sensor_that_overlap_make_one_entry(env):
    """Both pass the first check before either has finished asking the City (a review finding)."""
    a, b = await asyncio.gather(env.submit_flow(), env.submit_flow())
    results = sorted(r["type"] for r in (a, b))
    assert results == ["abort", "create_entry"], (a, b)
    assert len(env.hass.config_entries.async_entries("ztm_warsaw")) == 1


async def test_e2e_05_an_old_key_gets_a_notice_and_a_token_does_not(env):
    old = await env.add_entry(line="151")
    token = await env.add_entry(line="N25", api_key=DEFAULT_TOKEN)
    issues = ir.async_get(env.hass)
    notice = issues.async_get_issue(DOMAIN, f"legacy_key_{old.entry_id}")
    assert notice is not None
    assert (notice.is_fixable, notice.translation_key) == (True, "legacy_key")  # the token can be pasted in the notice
    assert notice.data == {"entry_id": old.entry_id}
    assert notice.translation_placeholders == {"line": "151", "stop": f"{stop_name_for('7009')} 01 (7009/01)", "portal": "https://dane.um.warszawa.pl/pl/key-api"}
    assert issues.async_get_issue(DOMAIN, f"legacy_key_{token.entry_id}") is None


def test_e2e_26_a_stop_name_cannot_add_markdown_to_a_notice():
    from custom_components.ztm_warsaw import _stop_text

    assert _stop_text("7009", "01", "Rynek [click](http://x.example) *Główny*") == "Rynek clickhttpxexample Główny 01 (7009/01)"
    assert _stop_text("7009", "01", "Al. Jerozolimskie, www.evil.example") == "Al. Jerozolimskie, wwwevilexample 01 (7009/01)"
    assert _stop_text("7009", "01", "Rondo ONZ 02") == "Rondo ONZ 02 01 (7009/01)"
    assert "\n" not in _stop_text("7009", "01", "A\n- B")
    assert _stop_text("7009", "01", "<>[]()") == "7009/01"
    assert _stop_text("7009", "01", None) == "7009/01"


async def test_e2e_26_a_title_the_user_chose_is_kept_and_a_default_one_gets_the_stop_name(env):
    entry = await env.add_entry(line="151")
    default = f"Line 151 from {stop_name_for('7009')} 01"
    assert entry.title == default
    env.hass.config_entries.async_update_entry(entry, title="My bus")
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.hass.async_block_till_done()
    assert entry.title == "My bus"
    env.hass.config_entries.async_update_entry(entry, title="Line 151 from 7009/01")  # the old default of 1.1.x
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.hass.async_block_till_done()
    assert entry.title == default


async def test_e2e_26_a_stop_name_that_arrives_after_the_setup_is_shown_then(env):
    with patch.object(ZTMStopClient, "get_stop_name", AsyncMock(return_value=None)):
        entry = await env.add_entry(line="151")
    issues = ir.async_get(env.hass)
    notice = issues.async_get_issue(DOMAIN, f"legacy_key_{entry.entry_id}")
    assert entry.title == "Line 151 from 7009/01"
    assert notice is not None
    assert notice.translation_placeholders["stop"] == "7009/01"
    coordinator = entry.runtime_data["coordinator"]
    await coordinator.async_refresh()  # the catalogue answers now
    await env.hass.async_block_till_done()
    assert entry.title == f"Line 151 from {stop_name_for('7009')} 01"
    notice = issues.async_get_issue(DOMAIN, f"legacy_key_{entry.entry_id}")
    assert notice is not None
    assert notice.translation_placeholders["stop"] == f"{stop_name_for('7009')} 01 (7009/01)"


async def test_e2e_05_the_notice_goes_when_the_key_becomes_a_token_or_the_entry_is_removed(env):
    entry = await env.add_entry()
    issues = ir.async_get(env.hass)
    env.city.valid_keys.add(DEFAULT_TOKEN)
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    await flow.async_configure(form["flow_id"], {"api_key": DEFAULT_TOKEN})
    await env.settle()
    assert issues.async_get_issue(DOMAIN, f"legacy_key_{entry.entry_id}") is None, "the reload saw a token"
    other = await env.add_entry(line="N25")
    assert issues.async_get_issue(DOMAIN, f"legacy_key_{other.entry_id}") is not None
    await env.hass.config_entries.async_remove(other.entry_id)
    await env.settle()
    assert issues.async_get_issue(DOMAIN, f"legacy_key_{other.entry_id}") is None


async def test_e2e_05_configure_heals_an_entry_whose_setup_failed_and_closes_its_reauth(env):
    """No update listener exists for an entry that never loaded: Configure must reload it itself (a review finding)."""
    env.city.valid_keys.clear()
    entry = await env.add_entry()
    await env.advance(minutes=2)  # three rejections at setup: the entry is in an error state and reauth is open
    assert entry.state is ConfigEntryState.SETUP_ERROR
    reauth = env.hass.config_entries.flow.async_progress_by_handler(DOMAIN, match_context={"source": "reauth"})
    assert len(reauth) == 1
    env.city.valid_keys.add(NEW_KEY)
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    await flow.async_configure(form["flow_id"], {"api_key": NEW_KEY})
    await env.settle()
    assert entry.state is ConfigEntryState.LOADED
    assert not env.hass.config_entries.flow.async_progress_by_handler(DOMAIN, match_context={"source": "reauth"})
    assert env.state().state not in ("unknown", "unavailable")


async def test_e2e_05_the_same_key_again_still_reloads_the_entry_once(env):
    """After three rejections the hourly refresh has stopped; typing the key the user has restarts it."""
    entry = await env.add_entry()
    flow = env.hass.config_entries.options
    with patch.object(env.hass.config_entries, "async_reload", wraps=env.hass.config_entries.async_reload) as reload:
        form = await flow.async_init(entry.entry_id)
        await flow.async_configure(form["flow_id"], {"api_key": DEFAULT_KEY})
        await env.settle()
    assert reload.call_count == 1, "no data changed, so no listener: Configure schedules the reload itself"


async def test_e2e_05_a_stop_position_that_is_not_a_place_is_not_published():
    from custom_components.ztm_warsaw.sensor import _stop_attributes

    ok = _stop_attributes({"szer_geo": "52.2", "dlug_geo": "21.0"})
    assert (ok["latitude"], ok["longitude"]) == (52.2, 21.0)
    for bad in (("nan", "21"), ("52", "inf"), ("91", "21"), ("52", "181"), ("x", "21"), (None, None)):
        attrs = _stop_attributes({"szer_geo": bad[0], "dlug_geo": bad[1]})
        assert "latitude" not in attrs, bad
        assert "longitude" not in attrs, bad


async def test_e2e_05_configure_aborts_for_an_entry_whose_data_cannot_be_read(env):
    entry = await env.add_entry(data={"api_key": DEFAULT_KEY}, setup=False)
    result = await env.hass.config_entries.options.async_init(entry.entry_id)
    assert (result["type"], result["reason"]) == ("abort", "unknown")


async def test_e2e_05_configure_accepts_a_key_for_a_line_that_does_not_run_today(env):
    """A weekday-only line on a Saturday: the key is judged by the key (a review finding of the same kind as reauth)."""
    env.move_to("2026-10-17 12:00")
    entry = await env.add_entry(line="411")
    env.city.valid_keys.add(NEW_KEY)
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    done = await flow.async_configure(form["flow_id"], {"api_key": NEW_KEY})
    assert done["type"] == "create_entry"
    assert entry.data["api_key"] == NEW_KEY


def test_the_host_named_in_the_configure_form_follows_the_kind_of_key():
    from custom_components.ztm_warsaw.config_flow import _host_of

    assert _host_of(DEFAULT_KEY) == "api.um.warszawa.pl"
    assert _host_of(DEFAULT_TOKEN) == "dane.um.warszawa.pl"
    assert _host_of("not a key") == "?"


async def test_e2e_05_configure_closes_a_reauth_flow_that_home_assistant_leaves_open(env):
    """Home Assistant before 2026.10 does not close it on a reload; 2026.10 does (so it is faked here)."""
    entry = await env.add_entry()
    env.city.valid_keys.add(NEW_KEY)
    flows = env.hass.config_entries.flow
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    with (
        patch.object(flows, "async_progress_by_handler", return_value=[{"flow_id": "left-open"}]) as progress,
        patch.object(flows, "async_abort") as abort,
    ):
        await flow.async_configure(form["flow_id"], {"api_key": NEW_KEY})
    assert {"entry_id": entry.entry_id, "source": "reauth"} in [c.kwargs["match_context"] for c in progress.call_args_list]
    abort.assert_any_call("left-open")  # (2026.10's own reload asks the same patched question, so it may be twice)


async def test_e2e_05_configure_clears_the_repairs_issue_and_the_notification_of_the_reauth_it_closes(env):
    """Aborting the flow through the manager does not do it (a review finding); Home Assistant before 2026.10 relied on it."""
    entry = await env.add_entry()
    env.city.valid_keys.add(NEW_KEY)
    issue_id = f"config_entry_reauth_{DOMAIN}_{entry.entry_id}"
    ir.async_create_issue(env.hass, "homeassistant", issue_id, is_fixable=False, severity=ir.IssueSeverity.ERROR, translation_key="config_entry_reauth")
    dismissed = []
    env.hass.services.async_register("persistent_notification", "dismiss", lambda call: dismissed.append(call.data["notification_id"]))
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    await flow.async_configure(form["flow_id"], {"api_key": NEW_KEY})
    await env.settle()
    assert ir.async_get(env.hass).async_get_issue("homeassistant", issue_id) is None
    assert dismissed == ["config_entry_reconfigure"]


async def test_e2e_05_configure_replaces_a_key_that_an_option_overrides(env):
    """A restored entry can have the key in its options (options win over data): the new key must be the one in use."""
    entry = await env.add_entry(options={"api_key": DEFAULT_KEY})
    env.city.valid_keys.add(NEW_KEY)
    flow = env.hass.config_entries.options
    form = await flow.async_init(entry.entry_id)
    with patch.object(env.hass.config_entries, "async_reload", wraps=env.hass.config_entries.async_reload) as reload:
        await flow.async_configure(form["flow_id"], {"api_key": NEW_KEY})
        await env.settle()
    assert entry.data["api_key"] == NEW_KEY
    assert "api_key" not in entry.options
    assert reload.call_count == 1
    assert env.city.matching("timetable")[-1].query["apikey"] == NEW_KEY, "the reload used the new key"

