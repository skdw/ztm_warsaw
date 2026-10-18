"""E2E-06 .. E2E-13: what the sensors show as the clock runs through the night, the service-day flip,
the hourly refresh, the process time zone and the two DST days.

Time is simulated with ``env.run_to``: it jumps from one scheduled timer to the next and fires each at its
own instant, so the hourly refresh keeps its real phase and nothing is evaluated "in between" unless a timer
asks for it. The first request of a test happens at ``@pytest.mark.start``; the coordinator then refreshes
exactly one hour after that, every hour.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from .conftest import at
from .fake_city import WARSAW
from .helpers import known_bug, local, reference_next, rows_for

pytestmark = pytest.mark.e2e

FRI = date(2026, 10, 16)


def friday_oracle(line: str, check_at: str) -> str | None:
    """Next departure listed for the FRIDAY service day (valid until the API flips at 03:00)."""
    return local(reference_next(rows_for("friday", line), FRI, at(check_at)))


# ===================================================================== E2E-06
TIMELINE = [
    # --- night line N25: 23:24 .. 28:54, identical on both days; the service day runs past midnight
    *[
        ("N25", t, friday_oracle("N25", t))
        for t in (
            "2026-10-16 23:50",
            "2026-10-17 00:00",
            "2026-10-17 00:10",
            "2026-10-17 01:55",
            "2026-10-17 02:29",
            "2026-10-17 02:31",
            "2026-10-17 03:00",
            "2026-10-17 03:05",
            "2026-10-17 04:30",
        )
    ],
    # --- day line with a 24:xx tail (520: ... 24:38): after midnight the tail is still shown, then nothing
    *[
        ("520", t, friday_oracle("520", t))
        for t in (
            "2026-10-16 23:50",
            "2026-10-17 00:10",
            "2026-10-17 00:30",
            "2026-10-17 01:55",
            "2026-10-17 02:29",
        )
    ],
    # --- plain day lines: nothing after the last departure (23:11 / 23:45) until the morning
    ("151", "2026-10-16 23:50", None),
    ("151", "2026-10-17 00:10", None),
    ("151", "2026-10-17 01:55", None),
    ("151", "2026-10-17 00:00", None),
    ("151", "2026-10-17 02:29", None),
    ("151", "2026-10-17 03:05", "2026-10-17 04:41"),  # a refresh at 02:40 has happened, so the morning shows
    ("151", "2026-10-17 04:30", "2026-10-17 04:41"),
    ("523", "2026-10-16 23:50", None),
    ("523", "2026-10-17 02:29", None),
    ("523", "2026-10-17 04:30", "2026-10-17 05:15"),  # Saturday set: reached via the 03:40 refresh
]


@pytest.mark.start("2026-10-16 23:40")
@pytest.mark.parametrize(("line", "check_at", "expected"), TIMELINE, ids=[f"{r[0]}@{r[1][5:]}" for r in TIMELINE])
async def test_e2e_06_state_at_fixed_instants_around_the_night(env, line, check_at, expected):
    """Entry set up Fri 23:40 (hourly refreshes at :40). The state is what the oracle says the schedule holds."""
    await env.add_entry(line=line)
    await env.run_to(check_at)
    assert env.departure_local(line) == expected
    st = env.state(line)
    if expected is None:
        assert st.attributes["Upcoming, Headsign"] == "No service"
        assert st.attributes["Upcoming, Departure Day"] == "Not available"
        assert st.attributes["Note"].startswith("No upcoming schedule available")


def test_e2e_06_oracle_sanity():
    """The reference implementation itself, on facts that can be read off the captured data."""
    assert friday_oracle("N25", "2026-10-16 23:50") == "2026-10-16 23:54"
    assert friday_oracle("N25", "2026-10-17 04:30") == "2026-10-17 04:54"  # 28:54 of the Friday service day
    assert friday_oracle("N25", "2026-10-17 04:55") is None
    assert friday_oracle("151", "2026-10-16 23:12") is None  # last departure 23:11
    assert friday_oracle("520", "2026-10-17 00:30") is not None  # 24:xx tail
    assert friday_oracle("520", "2026-10-17 00:39") is None  # 24:38 was the last


# ===================================================================== E2E-07
@pytest.mark.start("2026-10-16 23:40")
@pytest.mark.parametrize(("line", "check_at", "label"), [("N25", "23:42", "today"), ("N25", "23:58", "tomorrow"), ("520", "23:58", "tomorrow")])
async def test_e2e_07_departure_day_label_before_midnight(env, line, check_at, label):
    """The label is relative to today: a departure on the same date is 'today', one after midnight is 'tomorrow'."""
    await env.add_entry(line=line)
    await env.run_to(f"2026-10-16 {check_at}")
    assert env.state(line).attributes["Upcoming, Departure Day"] == label


@pytest.mark.start("2026-10-16 23:40")
@pytest.mark.parametrize("line", ["N25", "520"])
@known_bug("stale-at-midnight", "'Upcoming/Next N, Departure Day' goes stale at midnight: nothing wakes the sensor")
async def test_e2e_07_departure_day_label_turns_from_tomorrow_to_today_at_midnight(env, line):
    await env.add_entry(line=line)
    await env.run_to("2026-10-17 00:00:30")
    st = env.state(line)
    assert env.departure_local(line) is not None
    assert env.departure_local(line).startswith("2026-10-17 00:"), "the same departure, now just after midnight"
    assert st.attributes["Upcoming, Departure Day"] == "today"


@pytest.mark.start("2026-10-16 23:40")
async def test_e2e_07_the_state_itself_is_right_after_midnight_even_if_labels_lag(env):
    await env.add_entry(line="N25")
    await env.run_to("2026-10-17 00:00:30")
    assert env.departure_local("N25") == "2026-10-17 00:24"


# ===================================================================== E2E-08
@pytest.mark.start("2026-10-16 23:40")
@known_bug(
    "no-wakeup-at-sensor-cutoff", "no wake-up at the sensor's own 02:30 cutoff: day lines stay 'No service' until the next hourly tick"
)
async def test_e2e_08_morning_schedule_appears_at_the_0230_cutoff(env):
    """Encodes the 1.1.4 intent (cutoff 02:30). If the maintainer moves the boundary to the API's 03:00, change the two instants; the point is only that crossing the boundary wakes the sensor."""
    await env.add_entry(line="151")
    await env.run_to("2026-10-17 02:29")
    assert env.departure_local("151") is None
    await env.run_to("2026-10-17 02:31")
    assert env.departure_local("151") == "2026-10-17 04:41"


@pytest.mark.start("2026-10-16 23:40")
async def test_e2e_08_the_first_hourly_refresh_after_the_boundary_does_show_the_morning(env):
    await env.add_entry(line="151")
    await env.run_to("2026-10-17 03:41")  # the 03:40 refresh, past both 02:30 and 03:00
    assert env.departure_local("151") == "2026-10-17 04:41"


# ===================================================================== E2E-09
# Hourly refreshes land at :10 (before 02:30 the sensor said 'No service' and nothing re-evaluates it), at :40
# (the 02:40 refresh already shows Friday's morning) and at :55 (the 02:55 refresh does too).
FLIP_PHASES = [
    pytest.param("2026-10-17 00:10", "2026-10-17 03:08", id="refresh_phase_:10"),
    pytest.param("2026-10-17 00:40", "2026-10-17 03:08", id="refresh_phase_:40"),
    pytest.param("2026-10-17 00:55", "2026-10-17 03:08", id="refresh_phase_:55"),
]


@pytest.mark.parametrize(("setup_at", "check_at"), FLIP_PHASES)
@known_bug(
    "no-wakeup-after-api-day-flip", "after the API flips at 03:00 the sensor keeps the previous service day until the next hourly tick"
)
async def test_e2e_09_sensor_follows_the_api_within_minutes_of_the_0300_flip(env, setup_at, check_at):
    env.move_to(setup_at)
    await env.add_entry(line="523")  # Friday set starts 04:50, Saturday set 05:15: distinguishable
    await env.run_to("2026-10-17 02:59")
    assert env.departure_local("523") in ("2026-10-17 04:50", None)
    await env.run_to(check_at)
    assert env.departure_local("523") == "2026-10-17 05:15"


@pytest.mark.parametrize("setup_at", ["2026-10-17 00:10", "2026-10-17 00:55", "2026-10-17 02:40"])
async def test_e2e_09_every_refresh_phase_converges_within_an_hour_of_the_flip(env, setup_at):
    env.move_to(setup_at)
    await env.add_entry(line="523")
    await env.run_to("2026-10-17 04:01")  # one full hour after the 03:00 flip
    assert env.departure_local("523") == "2026-10-17 05:15"
    served = [(c.at_utc.astimezone(WARSAW).strftime("%H:%M"), c.day_set) for c in env.city.matching("timetable")]
    before_flip = [d for t, d in served if t < "03:00"]
    after_flip = [d for t, d in served if t >= "03:00"]
    assert set(before_flip) == {"friday"}, served
    assert set(after_flip) == {"saturday"}, served


# ===================================================================== E2E-10
async def test_e2e_10_the_sensor_wakes_itself_at_every_departure_without_calling_the_city(env):
    await env.add_entry(line="151", departures=2)  # Fri 12:00
    assert env.departure_local() == "2026-10-16 12:04"
    api_calls = env.city.count()

    await env.run_to("2026-10-16 12:04:30")
    assert env.departure_local() == "2026-10-16 12:24"
    assert env.state().attributes["Next 1, Departure Time"] == "12:44"
    await env.run_to("2026-10-16 12:24:30")
    assert env.departure_local() == "2026-10-16 12:44"
    assert env.city.count() == api_calls, "waking up at a departure is local arithmetic, no HTTP"


async def test_e2e_10_the_timetable_is_not_refetched_at_departures_only_hourly(env):
    await env.add_entry(line="151")
    await env.run_to("2026-10-16 12:59")
    assert env.city.count("timetable") == 1
    await env.run_to("2026-10-16 13:01")
    assert env.city.count("timetable") == 2


# ===================================================================== E2E-11
async def test_e2e_11_one_timetable_request_per_hour_and_no_more_catalogue_downloads(env):
    await env.add_entry(line="151")
    assert (env.city.count("stops"), env.city.count("timetable")) == (1, 1)
    await env.advance(hours=24, minutes=1)
    assert env.city.count("stops") == 1, "the catalogue is fetched once, at setup"
    assert env.city.count("timetable") - 1 == 24, "exactly one refresh per hour"
    # the hourly requests are the same GET the config flow validated, nothing else
    assert {tuple(sorted(c.query)) for c in env.city.matching("timetable")} == {
        ("apikey", "busstopId", "busstopNr", "id", "line")
    }


async def test_e2e_11_coordinator_notices_a_changed_schedule_and_the_sensor_follows(env):
    env.move_to("2026-10-17 02:30")
    await env.add_entry(line="151")
    first = env.coordinator(env.hass.config_entries.async_entries("ztm_warsaw")[0]).data
    assert len(first.departures) == 81  # Friday set still served before 03:00
    await env.run_to("2026-10-17 03:31")
    coord = env.coordinator(env.hass.config_entries.async_entries("ztm_warsaw")[0])
    assert len(coord.data.departures) == 53  # Saturday set
    assert coord.last_update_success is True


# ===================================================================== E2E-12
_TZ_BUG = known_bug("process-timezone-used", "sensor.py uses the process zone (.astimezone() with no argument)")
PROCESS_ZONES = ["Europe/Warsaw", pytest.param("UTC", marks=_TZ_BUG), pytest.param("America/New_York", marks=_TZ_BUG)]


@pytest.mark.parametrize("zone", PROCESS_ZONES)
@pytest.mark.start("2026-10-16 23:40")
async def test_e2e_12_next_n_labels_are_warsaw_time_whatever_the_process_zone(env, process_tz, zone):
    process_tz(zone)
    await env.add_entry(line="N25", departures=2)
    await env.run_to("2026-10-17 00:30")
    attrs = env.state("N25").attributes
    assert env.departure_local("N25") == "2026-10-17 00:54", "the state is an absolute instant: right in every zone"
    assert attrs["Next 1, Departure Time"] == "01:24"
    assert attrs["Next 2, Departure Time"] == "01:54"


@pytest.mark.parametrize("zone", ["Europe/Warsaw", pytest.param("UTC", marks=_TZ_BUG)])
@pytest.mark.start("2026-10-16 23:40")
async def test_e2e_12_morning_cutoff_is_warsaw_time_whatever_the_process_zone(env, process_tz, zone):
    process_tz(zone)
    await env.add_entry(line="151")
    await env.run_to("2026-10-17 03:05")
    assert env.departure_local("151") == "2026-10-17 04:41"


# ===================================================================== E2E-13
DST_NIGHTS = {
    "spring_forward_2026-03-29": ("2026-03-28 23:40", "2026-03-29 05:10"),  # 02:00 CET -> 03:00 CEST
    "fall_back_2026-10-25": ("2026-10-24 23:40", "2026-10-25 05:10"),  # 03:00 CEST -> 02:00 CET
}


@pytest.mark.parametrize("night", DST_NIGHTS)
async def test_e2e_13_night_line_states_never_go_backwards_across_a_dst_change(env, night):
    start, end = DST_NIGHTS[night]
    env.move_to(start)
    await env.add_entry(line="N25")
    seen = []
    while env.now < at(end):
        if not seen or env.state("N25").state != seen[-1][1]:
            seen.append((env.now, env.state("N25").state))
        await env.advance(minutes=1)
    states = [s for _, s in seen]
    assert len(states) >= 9, states
    assert states == sorted(states), f"departures went backwards in absolute time: {states}"
    assert len(set(states)) == len(states), "the same departure was announced twice"
    for moment, state in seen:
        assert datetime.fromisoformat(state) >= moment, f"announced {state} when it was already {moment}"


@pytest.mark.parametrize("night", DST_NIGHTS)
async def test_e2e_13_end_of_the_dst_night_is_on_the_local_wall_clock(env, night):
    start, end = DST_NIGHTS[night]
    env.move_to(start)
    await env.add_entry(line="N25")
    await env.run_to(end.replace("05:10", "04:30"))
    assert env.departure_local("N25") == end[:11] + "04:54", "28:54 of the service day is 04:54 local, CET or CEST"


@known_bug(
    "fixed-offset-across-dst", "'Next N, Departure Time' is rendered with the fixed offset of NOW: wrong by 1 h across the change"
)
async def test_e2e_13_labels_after_the_fall_back_change_are_in_the_new_offset(env):
    env.move_to("2026-10-24 23:40")
    await env.add_entry(line="N25", departures=3)
    await env.run_to("2026-10-25 02:30")  # first pass of the repeated hour, still CEST
    attrs = env.state("N25").attributes
    assert env.departure_local("N25") == "2026-10-25 02:54"
    # 27:24 / 27:54 / 28:24 of the service day are 03:24 / 03:54 / 04:24 CET
    assert [attrs[f"Next {n}, Departure Time"] for n in (1, 2, 3)] == ["03:24", "03:54", "04:24"]


@known_bug("skipped-hour-collision", "times inside the skipped spring-forward hour collide: 26:24 and 27:24 become the same instant")
async def test_e2e_13_no_two_listed_departures_collapse_into_one_in_the_skipped_hour(env):
    env.move_to("2026-03-28 23:40")
    await env.add_entry(line="N25", departures=3)
    await env.run_to("2026-03-29 01:30")
    attrs = env.state("N25").attributes
    labels = [attrs[f"Next {n}, Departure Time"] for n in (1, 2, 3)]
    assert len(set(labels)) == 3, f"duplicate departures announced: {labels}"


@pytest.mark.parametrize(
    ("day", "check_at", "expected"),
    [
        ("sat_before_change", "2026-10-24 12:00", "2026-10-24 12:04"),
        ("sun_after_change", "2026-10-25 12:00", "2026-10-25 12:04"),
        ("spring_before", "2026-03-28 12:00", "2026-03-28 12:04"),
        ("spring_after", "2026-03-29 12:00", "2026-03-29 12:04"),
    ],
)
async def test_e2e_13_daytime_departures_are_right_on_both_sides_of_each_change(env, day, check_at, expected):
    env.move_to(check_at)
    await env.add_entry(line="151")
    assert env.departure_local("151") is not None
    assert env.departure_local("151")[:10] == expected[:10]
    assert env.departure_local("151") >= check_at
    assert env.departure_local("151") <= (at(check_at) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M")


@pytest.mark.start("2026-10-17 00:10")  # Saturday 00:10: still Friday's service day, the API has not flipped yet
async def test_e2e_07_a_day_line_shows_its_after_midnight_departure_before_the_service_day_flips(env):
    await env.add_entry(line="520")  # a day line whose Friday timetable ends at 24:38
    shown = env.departure_local("520")
    assert shown is not None, "the 00:xx departures of the Friday timetable are still ahead"
    assert shown.startswith("2026-10-17 00:")
