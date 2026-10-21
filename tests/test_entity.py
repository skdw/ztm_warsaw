"""The helpers every entity of a stop shares (entity.py): they never raise, whatever the coordinator holds."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.ztm_warsaw import entity


class _Broken:
    """A coordinator whose data cannot be read."""

    def __init__(self, error):
        """Remember which error reading the data raises."""
        self._error = error

    @property
    def data(self):
        """Raise instead of giving data."""
        raise self._error


def test_the_stop_record_is_empty_when_there_is_no_coordinator_or_no_data():
    assert entity.stop_info_of(None) == {}
    assert entity.stop_info_of(SimpleNamespace(data=None)) == {}
    assert entity.stop_info_of(SimpleNamespace(data=SimpleNamespace(stop_info=None))) == {}


@pytest.mark.parametrize("error", [AttributeError("no data"), TypeError("not a timetable")])
def test_the_stop_record_is_empty_when_reading_the_data_fails(error):
    assert entity.stop_info_of(_Broken(error)) == {}


def test_the_stop_record_is_what_the_data_holds():
    assert entity.stop_info_of(SimpleNamespace(data=SimpleNamespace(stop_info={"nazwa_zespolu": "Marcelin"}))) == {"nazwa_zespolu": "Marcelin"}


def test_the_timetable_link_has_the_line_and_falls_back_to_the_general_one_when_the_date_cannot_be_made():
    assert "wtp_ln=176" in entity.timetable_url("176")
    assert "wtp_dt=" in entity.timetable_url("176")
    with patch.object(entity, "datetime") as broken:
        broken.now.side_effect = RuntimeError("no clock")
        link = entity.timetable_url("N 25")
    assert link.endswith("wtp_md=3&wtp_ln=N%2025")
    assert "wtp_dt" not in link
