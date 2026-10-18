"""The timetable the City of Warsaw API serves, and the time arithmetic that goes with it.

The API serves the timetable of one *service day* at a time. A service day starts at 03:00 (measured: the answer
changes between 02:55:51 and 03:00:51) and its times run past midnight: a night bus of the service day of Friday has
a ``czas`` of ``27:24``, which is 03:24 on Saturday. The timetable of Saturday is served from 03:00 on Saturday, so
from then on the 27:xx and 28:xx times of Friday are no longer in the answer although the buses still run.
That is why every reading carries the absolute moment it departs, computed from the service date of the answer,
and why the coordinator keeps the previous answer for as long as its late departures are ahead.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

_LOGGER = logging.getLogger(__name__)

WARSAW = ZoneInfo("Europe/Warsaw")

SERVICE_DAY_FLIP = time(3, 0)  # the API serves the next service day from here
FLIP_SAFETY = timedelta(minutes=1)  # the flip was measured within 02:55:51 to 03:00:51: an answer before 03:01 is not trusted
FLIP_REFRESH = time(3, 2)  # when the coordinator asks again, once the flip has certainly happened


def service_date_at(moment: datetime) -> date:
    """The service day that an answer received at ``moment`` belongs to."""
    local = moment.astimezone(WARSAW)
    flip = datetime.combine(local.date(), SERVICE_DAY_FLIP, WARSAW) + FLIP_SAFETY
    return local.date() if local >= flip else local.date() - timedelta(days=1)


def next_flip_refresh(after: datetime) -> datetime:
    """The next 03:02 in Warsaw after ``after``, in UTC."""
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
    kierunek: str = field(default="unknown")
    czas: Optional[str] = field(default=None)
    symbol_1: Optional[str] = field(default=None)
    symbol_2: Optional[str] = field(default=None)
    trasa: Optional[str] = field(default=None)
    brygada: Optional[str] = field(default=None)
    dt: Optional[datetime] = field(default=None)  # the moment it departs (UTC); None when the reading has no usable time

    @classmethod
    def from_dict(cls, data, service_date: date):
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
    departures: list[ZTMDepartureDataReading]
    stop_info: Optional[dict] = field(default_factory=dict)
    service_date: Optional[date] = None  # the service day of the answer; None only in tests that do not care
