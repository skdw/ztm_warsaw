"""The pure parts of the vehicle feed: what counts as a position, how brigades and distances compare."""

from __future__ import annotations

import math

import pytest

from custom_components.ztm_warsaw.vehicles import _vehicle_of, brigade_key, distance_m

ROW = {"Lines": "n64", "Brigade": "05", "Lat": 52.2, "Lon": 21.0, "Time": "2026-10-22 08:49:15", "VehicleNumber": " 4414 "}


def test_a_brigade_is_the_same_with_or_without_a_leading_zero():
    assert brigade_key("05") == brigade_key("5") == brigade_key(5) == "5"
    assert brigade_key("0") == brigade_key("00") == "0"
    assert brigade_key("132") != brigade_key("13")


def test_a_row_becomes_a_vehicle_with_a_normalised_line_brigade_and_number():
    vehicle = _vehicle_of(ROW)
    assert vehicle is not None
    assert (vehicle.line, vehicle.brigade, vehicle.number) == ("N64", "5", "4414")
    assert vehicle.moment.isoformat() == "2026-10-22T06:49:15+00:00", "the City's time is Warsaw wall-clock time"


@pytest.mark.parametrize(
    "broken",
    [
        None,
        "text",
        {**ROW, "Lat": "north"},
        {**ROW, "Lat": 91},
        {**ROW, "Lon": float("nan")},
        {**ROW, "Time": "yesterday"},
        {k: v for k, v in ROW.items() if k != "Brigade"},
    ],
)
def test_a_row_that_is_not_a_usable_position_is_dropped(broken):
    assert _vehicle_of(broken) is None


def test_distances_are_in_metres():
    assert distance_m(52.0, 21.0, 52.0, 21.0) == 0
    one_degree = distance_m(52.0, 21.0, 53.0, 21.0)
    assert math.isclose(one_degree, 111_195, rel_tol=0.01)
