"""The pure parts of the vehicle feed: what counts as a position, how brigades and distances compare."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.ztm_warsaw.vehicles import _vehicle_of, brigade_key, distance_m

NOW = datetime(2026, 10, 22, 7, 0, tzinfo=timezone.utc)
ROW = {"Lines": "n64", "Brigade": "05", "Lat": 52.2, "Lon": 21.0, "Time": "2026-10-22 08:49:15", "VehicleNumber": " 4414 "}


def test_a_brigade_is_the_same_with_or_without_a_leading_zero():
    assert brigade_key("05") == brigade_key("5") == brigade_key(5) == "5"
    assert brigade_key("0") == brigade_key("00") == "0"
    assert brigade_key("132") != brigade_key("13")


def test_a_row_becomes_a_vehicle_with_a_normalised_line_brigade_and_number():
    vehicle = _vehicle_of(ROW, NOW)
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
    assert _vehicle_of(broken, NOW) is None


def test_distances_are_in_metres():
    assert distance_m(52.0, 21.0, 52.0, 21.0) == 0
    one_degree = distance_m(52.0, 21.0, 53.0, 21.0)
    assert math.isclose(one_degree, 111_195, rel_tol=0.01)


def test_the_hour_that_repeats_when_the_clocks_go_back_is_settled_by_the_time_now():
    """On 25 October 2026 02:30 happens twice (00:30 and 01:30 UTC): a fresh position is fresh in either hour."""
    row = {**ROW, "Time": "2026-10-25 02:30:00"}
    first = _vehicle_of(row, datetime(2026, 10, 25, 0, 31, tzinfo=timezone.utc))
    second = _vehicle_of(row, datetime(2026, 10, 25, 1, 31, tzinfo=timezone.utc))
    assert first is not None
    assert second is not None
    assert (first.moment.hour, second.moment.hour) == (0, 1)
    assert timedelta(0) <= datetime(2026, 10, 25, 1, 31, tzinfo=timezone.utc) - second.moment < timedelta(minutes=3)


async def test_an_old_key_is_not_asked_for_positions_and_an_answer_that_is_not_a_list_is_none():
    """Only the new host knows where the vehicles are; a bare error object instead of a list is no positions."""
    from unittest.mock import AsyncMock, patch

    from custom_components.ztm_warsaw.client import ZTMStopClient

    legacy = ZTMStopClient(None, "11111111-2222-3333-4444-555555555555", "7009", "01", "151")  # type: ignore[arg-type]
    assert await legacy.get_vehicles(1) is None, "an old key makes no request (there is no session to ask with)"
    token = ZTMStopClient(None, "aaa.bbb.ccc", "7009", "01", "151")  # type: ignore[arg-type]
    with patch.object(ZTMStopClient, "_get_with_retry", AsyncMock(return_value={"result": {"error": "no"}})):
        assert await token.get_vehicles(1) is None
    with patch.object(ZTMStopClient, "_get_with_retry", AsyncMock(return_value={"result": [{"Lines": "1"}]})):
        assert await token.get_vehicles(1) == [{"Lines": "1"}]


async def test_a_client_of_the_retired_old_api_asks_nothing(monkeypatch):
    """With the old API gone every question gets no answer, and no request is made (there is no session to make one)."""
    from custom_components.ztm_warsaw.client import ZTMStopClient

    monkeypatch.setattr("custom_components.ztm_warsaw.const.LEGACY_API_RETIRED", True)
    client = ZTMStopClient(None, "11111111-2222-3333-4444-555555555555", "7009", "01", "151")  # type: ignore[arg-type]
    assert client.retired is True
    assert await client.get() is None
    assert await client.get_lines() is None
    assert await client.stop_in_catalogue() is None
    token = ZTMStopClient(None, "aaa.bbb.ccc", "7009", "01", "151")  # type: ignore[arg-type]
    assert token.retired is False
