"""The arithmetic of the service day: which moment a `czas` of a timetable is, and which service day an answer is of."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from custom_components.ztm_warsaw.models import (
    in_swap_window,
    ZTMDepartureDataReading,
    departure_datetime,
    next_flip_refresh,
    next_warsaw_midnight,
    service_date_at,
)

WARSAW = ZoneInfo("Europe/Warsaw")
FRI = date(2026, 10, 16)


def local(moment):
    return moment.astimezone(WARSAW).strftime("%Y-%m-%d %H:%M")


def warsaw(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=WARSAW)


@pytest.mark.parametrize(
    ("czas", "expected"),
    [
        ("04:41:00", "2026-10-16 04:41"),
        ("23:59:00", "2026-10-16 23:59"),
        ("24:00:00", "2026-10-17 00:00"),  # the first minute after midnight is 24:00, never 00:00
        ("24:38:00", "2026-10-17 00:38"),
        ("27:24:00", "2026-10-17 03:24"),
        ("29:29:00", "2026-10-17 05:29"),  # the latest time seen on the real API
        ("03:14:00", "2026-10-16 03:14"),  # the earliest: the service day starts at 03:00
    ],
)
def test_a_czas_is_a_moment_of_its_service_day(czas, expected):
    assert local(departure_datetime(FRI, czas)) == expected


@pytest.mark.parametrize("czas", [None, "", "x", "12:30", "12:60:00", "48:00:00", "-1:00:00", "12:30:00:00", 5])
def test_a_czas_that_is_not_a_time_is_no_moment(czas):
    assert departure_datetime(FRI, czas) is None


def test_the_result_is_utc_and_aware():
    moment = departure_datetime(FRI, "12:00:00")
    assert moment.utcoffset() == timedelta(0)
    assert moment == warsaw("2026-10-16 12:00")


def test_a_label_in_the_hour_the_clock_skips_is_no_moment():
    sat = date(2026, 3, 28)  # the night to Sunday 2026-03-29: 02:00 CET jumps to 03:00 CEST
    assert departure_datetime(sat, "25:54:00") is not None  # 01:54 CET
    assert departure_datetime(sat, "26:24:00") is None  # 02:24 does not exist
    assert local(departure_datetime(sat, "27:24:00")) == "2026-03-29 03:24"


def test_a_label_in_the_hour_the_clock_repeats_is_its_first_occurrence():
    sat = date(2026, 10, 24)  # the night to Sunday 2026-10-25: 03:00 CEST falls back to 02:00 CET
    first = departure_datetime(sat, "26:24:00")
    assert first.utcoffset() == timedelta(0)
    assert first == datetime(2026, 10, 25, 0, 24, tzinfo=timezone.utc)  # 02:24 CEST
    assert local(departure_datetime(sat, "27:24:00")) == "2026-10-25 03:24"  # CET, after the repeated hour
    assert departure_datetime(sat, "26:24:00") < departure_datetime(sat, "27:24:00")


@pytest.mark.parametrize(
    ("moment", "service_date"),
    [
        ("2026-10-17 12:00", date(2026, 10, 17)),
        ("2026-10-17 00:00", date(2026, 10, 16)),  # midnight does not flip the day
        ("2026-10-17 02:59", date(2026, 10, 16)),
        ("2026-10-17 03:04", date(2026, 10, 16)),  # the City's update (from 02:10) was measured done by 03:00:51
        ("2026-10-17 03:05", date(2026, 10, 17)),
        ("2026-10-17 23:59", date(2026, 10, 17)),
    ],
)
def test_the_service_day_of_an_answer(moment, service_date):
    assert service_date_at(warsaw(moment)) == service_date


@pytest.mark.parametrize(
    ("moment", "inside"),
    [("2026-10-17 02:09", False), ("2026-10-17 02:10", True), ("2026-10-17 03:04", True), ("2026-10-17 03:05", False), ("2026-10-17 12:00", False)],
)
def test_the_update_window_of_the_city(moment, inside):
    assert in_swap_window(warsaw(moment)) is inside


@pytest.mark.parametrize(
    ("utc", "inside"),
    [
        ("2026-10-25 00:09", False),  # 02:09 CEST, before the update begins
        ("2026-10-25 00:10", True),  # the first 02:10
        ("2026-10-25 01:05", True),  # the second 02:05: still inside, although the wall clock shows 02:05 again
        ("2026-10-25 01:10", True),  # the second 02:10
        ("2026-10-25 02:04", True),  # 03:04 CET
        ("2026-10-25 02:05", False),  # 03:05 CET
        ("2026-03-29 00:09", False),
        ("2026-03-29 00:10", True),  # 01:10 CET: the earlier reading of the missing 02:10 starts the window
        ("2026-03-29 01:04", True),  # 03:04 CEST
        ("2026-03-29 01:05", False),  # 03:05 CEST
    ],
)
def test_the_update_window_is_measured_in_elapsed_time(utc, inside):
    assert in_swap_window(datetime.fromisoformat(utc).replace(tzinfo=timezone.utc)) is inside


def test_the_service_day_is_the_same_whatever_zone_the_moment_is_in():
    moment = warsaw("2026-10-17 03:30")
    assert service_date_at(moment.astimezone(timezone.utc)) == service_date_at(moment.astimezone(ZoneInfo("America/New_York")))


@pytest.mark.parametrize(
    ("after", "expected"),
    [
        ("2026-10-17 12:00", "2026-10-18 03:06"),
        ("2026-10-17 03:01", "2026-10-17 03:06"),
        ("2026-10-17 03:06", "2026-10-18 03:06"),  # strictly after
        ("2026-10-24 20:00", "2026-10-25 03:06"),  # the fall-back night: 03:06 CET
        ("2026-03-28 20:00", "2026-03-29 03:06"),  # the spring-forward night: 03:06 CEST
    ],
)
def test_the_next_refresh_after_the_flip(after, expected):
    assert local(next_flip_refresh(warsaw(after))) == expected


def test_the_next_midnight_in_warsaw_is_one_second_past_it():
    assert next_warsaw_midnight(warsaw("2026-10-16 23:50")) == warsaw("2026-10-17 00:00") + timedelta(seconds=1)


def test_a_reading_without_a_time_has_no_moment():
    assert ZTMDepartureDataReading.from_dict({"kierunek": "X"}, FRI).dt is None
    assert ZTMDepartureDataReading.from_dict({"czas": "12:00:00"}, FRI).dt == warsaw("2026-10-16 12:00")


@pytest.mark.parametrize(
    ("departure", "label"),
    [
        ("2026-10-17 12:00", "today"),
        ("2026-10-18 00:30", "tomorrow"),
        ("2026-10-16 23:50", "yesterday"),
        ("2026-10-20 08:00", "Tue"),
    ],
)
def test_the_day_of_a_departure_is_named_in_warsaw_dates(departure, label):
    from custom_components.ztm_warsaw.sensor import _friendly_day

    assert _friendly_day(warsaw(departure), warsaw("2026-10-17 12:00")) == label


def test_a_reading_without_a_moment_has_no_day_label():
    from custom_components.ztm_warsaw.sensor import NOT_AVAILABLE, _friendly_day

    assert _friendly_day(None, warsaw("2026-10-17 12:00")) == NOT_AVAILABLE
