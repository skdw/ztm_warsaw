"""The timetable the City of Warsaw API serves, and the time arithmetic that goes with it.

The API serves the timetable of one *service day* at a time, and its times run past midnight: a night bus of the
service day of Friday has a ``czas`` of ``27:24``, which is 03:24 on Saturday. The City says (letter CRWIP/3980/25)
that the update starts at 02:10 and then publishes the day's timetables together with the night lines of the coming
night; the change was measured to be complete between 02:55:51 and 03:00:51. So from some moment in that window the
27:xx and 28:xx times of the previous service day are no longer in the answer although the buses still run.
An answer fetched inside the window cannot be told apart from the old or the new day, so none is fetched there:
the integration keeps the answer it has, tags a fresh one with its service date and keeps the previous answer for
as long as its late departures are ahead.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

_LOGGER = logging.getLogger(__name__)

WARSAW = ZoneInfo("Europe/Warsaw")

SWAP_START = time(2, 10)  # the City starts replacing the timetables here (its letter); nothing fetched from now on is trusted
SWAP_END = time(3, 5)  # complete: measured by 03:00:51, plus a margin. From here an answer belongs to the new service day
FLIP_REFRESH = time(3, 6)  # when the coordinator asks again, once the swap is over


def _warsaw_moment(day: date, at: time, *, first: bool) -> datetime:
    """The UTC instant of a Warsaw wall time that may exist twice (autumn) or not at all (spring)."""
    options = [datetime.combine(day, at, WARSAW).replace(fold=fold).astimezone(timezone.utc) for fold in (0, 1)]
    return min(options) if first else max(options)


def in_swap_window(moment: datetime) -> bool:
    """Whether an answer fetched at ``moment`` could be either the old or the new service day.

    Measured in elapsed time, not wall time: on the autumn night the clock shows 02:00-02:09 twice, and the second
    pass is still inside the update that began at the first 02:10. On the spring night 02:10 does not exist and the
    window starts at the earlier of the two readings of it (an hour of caution, once a year)."""
    day = moment.astimezone(WARSAW).date()
    return _warsaw_moment(day, SWAP_START, first=True) <= moment < _warsaw_moment(day, SWAP_END, first=False)


def next_swap_boundary(after: datetime) -> datetime:
    """The next moment, after ``after``, at which ``in_swap_window`` changes (the start or the end of the City's update), in UTC."""
    day = after.astimezone(WARSAW).date()
    boundaries = [
        _warsaw_moment(d, at, first=first)
        for d in (day, day + timedelta(days=1))
        for at, first in ((SWAP_START, True), (SWAP_END, False))
    ]
    return min(b for b in boundaries if b > after)


def service_date_at(moment: datetime) -> date:
    """The service day that an answer received at ``moment`` belongs to."""
    local = moment.astimezone(WARSAW)
    return local.date() if local.time() >= SWAP_END else local.date() - timedelta(days=1)


def next_flip_refresh(after: datetime) -> datetime:
    """The next 03:06 in Warsaw after ``after``, in UTC."""
    local = after.astimezone(WARSAW)
    candidate = datetime.combine(local.date(), FLIP_REFRESH, WARSAW)
    if candidate <= after:
        candidate = datetime.combine(local.date() + timedelta(days=1), FLIP_REFRESH, WARSAW)
    return candidate.astimezone(timezone.utc)


def next_warsaw_midnight(after: datetime) -> datetime:
    """The first second of the next day in Warsaw after ``after``, in UTC (when 'today' turns into 'yesterday')."""
    local = after.astimezone(WARSAW)
    return datetime.combine(local.date() + timedelta(days=1), time(0, 0, 1), WARSAW).astimezone(timezone.utc)


def departure_datetime(service_date: date, czas) -> Optional[datetime]:
    """The moment (UTC) of a ``czas`` in the timetable of ``service_date``: ``HH:MM:SS``, hours from 24 on are after midnight.

    The times are read as the clock shows them. A label inside the hour that the clock skips (spring) is not a
    moment: None. A label inside the hour that the clock repeats (autumn) is its first occurrence.
    """
    try:
        hours, minutes, _ = (int(part) for part in czas.split(":"))
    except (AttributeError, TypeError, ValueError):
        return None
    if not 0 <= minutes < 60 or not 0 <= hours < 48:
        return None
    day = service_date + timedelta(days=hours // 24)
    wall = datetime(day.year, day.month, day.day, hours % 24, minutes, tzinfo=WARSAW)
    moment = wall.astimezone(timezone.utc)
    if moment.astimezone(WARSAW).replace(tzinfo=None) != wall.replace(tzinfo=None):
        return None
    return moment


@dataclass
class ZTMDepartureDataReading:
    """One departure as the City describes it (direction, the label of the time, the brigade ...) with the moment it departs."""

    kierunek: str = field(default="unknown")
    czas: Optional[str] = field(default=None)
    symbol_1: Optional[str] = field(default=None)
    symbol_2: Optional[str] = field(default=None)
    trasa: Optional[str] = field(default=None)
    brygada: Optional[str] = field(default=None)
    dt: Optional[datetime] = field(default=None)  # the moment it departs (UTC); None when the reading has no usable time

    @classmethod
    def from_dict(cls, data, service_date: date):
        """A reading built from the City's key/value pairs; ``dt`` is the moment of ``czas`` on ``service_date`` (None when it has no usable time)."""
        czas = data.get("czas")
        return cls(
            kierunek=data.get("kierunek", "unknown"),
            czas=czas,
            symbol_1=data.get("symbol_1"),
            symbol_2=data.get("symbol_2"),
            trasa=data.get("trasa"),
            brygada=data.get("brygada"),
            dt=departure_datetime(service_date, czas),
        )


@dataclass
class ZTMDepartureData:
    """The timetable of one stop for one service day: its departures in order and what the City says about the stop."""

    departures: list[ZTMDepartureDataReading]
    stop_info: Optional[dict] = field(default_factory=dict)
    service_date: Optional[date] = None  # the service day of the answer; None only in tests that do not care
