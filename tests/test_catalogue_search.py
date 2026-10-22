"""The search of the stops catalogue behind the setup dialog: by name (diacritics and case do not matter) and by number."""

from __future__ import annotations

import pytest

from custom_components.ztm_warsaw.client import SEARCH_LIMIT, StopCatalogue, _fold


class _Client:
    """A stand-in client whose catalogue download gives these rows (the shape of the legacy answer)."""

    uses_token = False
    retired = False

    def __init__(self, stops):
        """Remember the stops: ``(stop id, pole, name, direction)``."""
        self._stops = stops

    async def _stop_info_rows(self):
        """The rows of the catalogue."""
        return [
            {"values": [{"key": "zespol", "value": sid}, {"key": "slupek", "value": nr}, {"key": "nazwa_zespolu", "value": name}, {"key": "kierunek", "value": direction}]}
            for sid, nr, name, direction in self._stops
        ]


STOPS = [
    ("1085", "01", "Marcelin", "Metro Wilanowska"),
    ("1085", "02", "Marcelin", "Okęcie"),
    ("7009", "01", "Łazienki Królewskie", "Centrum"),
    ("7009", "02", "Łazienki Królewskie", "Wilanów"),
    ("3044", "01", "Żerań FSO", "Dworzec"),
]


async def _search(query, stops=STOPS, **kwargs):
    """Search a fresh catalogue (nothing kept) of these stops."""
    return await StopCatalogue(ttl=0).search(_Client(stops), query, **kwargs)


def test_folding_ignores_case_diacritics_and_the_polish_l():
    assert _fold("Łazienki Żerań ĄĘ") == _fold("lazienki zeran ae")


@pytest.mark.parametrize("query", ["marc", "MARCELIN", "  marcelin "])
async def test_a_name_is_found_by_any_part_of_it_whatever_the_case(query):
    readable, poles = await _search(query)
    assert readable is True
    assert [(p["stop_id"], p["stop_nr"]) for p in poles] == [("1085", "01"), ("1085", "02")]


async def test_polish_letters_can_be_typed_without_their_diacritics():
    _, poles = await _search("lazienki")
    assert {p["stop_id"] for p in poles} == {"7009"}
    _, poles = await _search("zeran")
    assert [p["name"] for p in poles] == ["Żerań FSO"]


async def test_a_stop_id_or_an_id_and_pole_finds_that_stop_or_pole():
    _, whole = await _search("7009")
    assert [p["stop_nr"] for p in whole] == ["01", "02"]
    _, one = await _search("7009/02")
    assert [(p["stop_id"], p["stop_nr"], p["direction"]) for p in one] == [("7009", "02", "Wilanów")]


async def test_nothing_matches_gives_an_empty_list_and_an_empty_query_matches_nothing():
    assert await _search("nonexistent") == (True, [])
    assert await _search("   ") == (True, [])


async def test_a_search_returns_one_more_than_the_limit_so_the_caller_can_tell_too_many():
    many = [(str(1000 + i), "01", f"Stop {i}", "x") for i in range(SEARCH_LIMIT + 5)]
    readable, poles = await _search("stop", many)
    assert readable is True
    assert len(poles) == SEARCH_LIMIT + 1


async def test_a_catalogue_that_cannot_be_read_is_reported_and_finds_nothing():
    readable, poles = await StopCatalogue(ttl=0).search(_Client([]), "marcelin")
    assert (readable, poles) == (False, [])
