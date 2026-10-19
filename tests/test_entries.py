"""How an entry is read as stops (entries.py): a 1.1.x entry of one stop and a line entry with its stops as subentries."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from custom_components.ztm_warsaw.const import DOMAIN
from custom_components.ztm_warsaw.entries import (
    StopUnit,
    _entry_values,
    _first_nonempty,
    entry_api_key,
    is_line_entry,
    line_of,
    runtimes,
    stop_keys,
    stop_units,
)

KEY = "11111111-2222-3333-4444-555555555555"  # gitleaks:allow  (synthetic)


def _entry(*, version=1, data=None, options=None, subentries=None):
    return SimpleNamespace(
        entry_id="entry-1", version=version, data=data or {}, options=options or {}, subentries=subentries or {}
    )


def _stop(subentry_type="stop", **data):
    return SimpleNamespace(subentry_type=subentry_type, data=data)


V1 = {"api_key": KEY, "busstop_id": 7009, "busstop_nr": "01", "line": "151", "departures": 1}


@pytest.mark.parametrize(
    ("merged", "expected"),
    [
        ({}, None),
        ({"a": None, "b": "  "}, None),
        ({"a": None, "b": " 7009 "}, "7009"),
        ({"a": 7009}, "7009"),
        ({"a": "  ", "b": "x"}, "x"),
    ],
)
def test_the_first_spelling_with_a_value_wins_and_is_trimmed(merged, expected):
    assert _first_nonempty(merged, "a", "b") == expected


def test_a_1_1_x_entry_is_one_stop_with_the_options_overriding_the_data():
    entry = _entry(data=V1, options={"line": "N25"})
    assert _entry_values(entry) == (KEY, "7009", "01", "N25")
    assert stop_units(entry) == [StopUnit("entry-1", None, KEY, "7009", "01", "N25")]
    assert stop_units(entry)[0].ref == "entry-1"
    assert stop_keys(entry) == {("7009", "01", "N25")}
    assert not is_line_entry(entry)
    assert line_of(entry) is None


def test_a_1_1_x_entry_with_something_missing_is_no_stop_and_says_what_without_naming_the_key(caplog):
    entry = _entry(data={"api_key": KEY, "busstop_id": 7009, "line": "151"})
    with caplog.at_level(logging.DEBUG):
        assert _entry_values(entry) is None
        assert stop_units(entry) == []
    assert "Missing required config: stop_nr" in caplog.text
    assert KEY not in caplog.text


def test_a_1_1_x_entry_without_a_key_is_logged_without_naming_any_field_but_the_harmless_ones(caplog):
    entry = _entry(data={"busstop_id": 7009, "busstop_nr": "01", "line": "151", "api_key": " "})
    with caplog.at_level(logging.DEBUG):
        assert _entry_values(entry) is None
    assert "Missing required configuration" in caplog.text
    assert "Provided non-sensitive keys: busstop_id, busstop_nr, line" in caplog.text


def test_an_entry_that_cannot_be_read_quietly_is_none_when_not_asked_to_log(caplog):
    with caplog.at_level(logging.DEBUG):
        assert _entry_values(_entry(data={}), log=False) is None
    assert caplog.text == ""


def test_a_line_entry_lists_the_stops_that_are_complete_and_only_stops():
    entry = _entry(
        version=2,
        data={"api_key": KEY, "line": "525", "departures": 3},
        subentries={
            "s1": _stop(busstop_id=7009, busstop_nr="01"),
            "s2": _stop(busstop_id="7013", busstop_nr="01"),
            "s3": _stop(busstop_id=7009),  # no pole: left out
            "s4": _stop(subentry_type="something_else", busstop_id=1, busstop_nr="01"),
        },
    )
    assert is_line_entry(entry)
    assert line_of(entry) == "525"
    assert entry_api_key(entry) == KEY
    assert [(u.subentry_id, u.stop_id, u.stop_nr, u.line, u.ref) for u in stop_units(entry)] == [
        ("s1", "7009", "01", "525", "s1"),
        ("s2", "7013", "01", "525", "s2"),
    ]
    assert stop_keys(entry) == {("7009", "01", "525"), ("7013", "01", "525")}


@pytest.mark.parametrize("data", [{"line": "525"}, {"api_key": KEY}, {}])
def test_a_line_entry_without_its_key_or_its_line_runs_nothing(data):
    entry = _entry(version=2, data=data, subentries={"s1": _stop(busstop_id=7009, busstop_nr="01")})
    assert stop_units(entry) == []
    assert stop_keys(entry) == set()


def test_a_line_entry_with_no_stop_left_runs_nothing_but_keeps_its_key_and_line():
    entry = _entry(version=2, data={"api_key": KEY, "line": "525"})
    assert stop_units(entry) == []
    assert (entry_api_key(entry), line_of(entry)) == (KEY, "525")


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        (None, {}),
        ("not a dict", {}),
        ({"client": object()}, {}),  # no coordinator
        ({"coordinator": "c", "client": "k"}, {None: {"coordinator": "c", "client": "k"}}),  # a 1.1.x stop
        ({"units": {"s1": {"coordinator": "c"}}}, {"s1": {"coordinator": "c"}}),  # a line
    ],
)
def test_the_running_stops_of_an_entry_whatever_shape_they_are_kept_in(stored, expected):
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": stored} if stored is not None else {}})
    assert runtimes(hass, _entry()) == expected


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("data", [None, "not a mapping", ["api_key"]])
def test_an_entry_whose_data_and_options_are_not_mappings_is_read_as_empty_not_a_crash(version, data):
    entry = SimpleNamespace(entry_id="entry-1", version=version, data=data, options=data, subentries={})
    assert stop_units(entry) == []
    assert entry_api_key(entry) is None
    assert line_of(entry) is None
    assert _entry_values(entry, log=False) is None


def test_options_override_the_data_of_a_line_entry_too():
    entry = _entry(version=2, data={"api_key": KEY, "line": "525"}, options={"line": "N25"})
    assert line_of(entry) == "N25"
