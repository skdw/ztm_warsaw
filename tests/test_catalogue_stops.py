"""What the setup asks of the stops catalogue: the poles of one stop."""

from __future__ import annotations

from custom_components.ztm_warsaw.client import StopCatalogue, fold


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
    ("1085", "01", "Rondo Daszyńskiego", "Dworzec Centralny"),
    ("1085", "02", "Rondo Daszyńskiego", "Okęcie"),
    ("7009", "01", "Łazienki Królewskie", "Centrum"),
    ("3044", "01", "Żerań FSO", "Dworzec"),
]


def test_folding_ignores_case_diacritics_and_the_polish_l():
    assert fold("Łazienki Żerań ĄĘ") == fold("lazienki zeran ae")


async def test_the_poles_of_a_stop_come_with_their_name_and_direction():
    readable, poles = await StopCatalogue(ttl=0).poles_of(_Client(STOPS), "1085")
    assert readable is True
    assert [(p["stop_nr"], p["name"], p["direction"]) for p in poles] == [("01", "Rondo Daszyńskiego", "Dworzec Centralny"), ("02", "Rondo Daszyńskiego", "Okęcie")]
    assert (await StopCatalogue(ttl=0).poles_of(_Client(STOPS), "9999")) == (True, [])


async def test_a_catalogue_that_cannot_be_read_gives_nothing_and_says_so():
    class Broken(_Client):
        """A client whose download returns nothing."""

        async def _stop_info_rows(self):
            """Nothing readable."""
            return []

    assert await StopCatalogue(ttl=0).poles_of(Broken([]), "1085") == (False, [])
