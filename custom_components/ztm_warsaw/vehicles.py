"""Where the vehicles are: one shared feed of the City's positions for every entity that follows a vehicle.

The City sends every bus (or tram) in one answer and ignores the line asked for, so the positions are fetched once per
token, whoever follows how many vehicles, and the vehicle of a departure is looked up in them by its line and brigade
(the timetable names the brigade of every departure). The feed asks only while an entity wants a vehicle (its next
departure is near), slows down when the City fails, and keeps a position's age so that an entity can refuse an old one:
the City keeps reporting vehicles that have long stopped (a depot, a record from years ago).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .models import WARSAW
from .utils import TRAM_LINE

if TYPE_CHECKING:
    from .client import ZTMStopClient

_LOGGER = logging.getLogger(__name__)

POLL_EVERY = timedelta(seconds=30)  # how often the City is asked while a vehicle is wanted
MAX_BACKOFF = timedelta(minutes=10)  # the longest wait after failures
MAX_AGE = timedelta(minutes=3)  # a position older than this is not shown (the median is ten seconds on a day)
FLEET_REFRESH = timedelta(days=1)  # how old the City's fleet may be before it is read again
FLEET_RETRY = timedelta(hours=1)  # how long to wait after a failed read
WANTED_WITHIN = timedelta(minutes=15)  # a vehicle is followed when its departure is this near
BUS, TRAM = 1, 2  # the City's codes for the kind of vehicle

Wanted = Callable[[], str | None]  # the line an entity wants a vehicle of now, or None


def brigade_key(brigade: object) -> str:
    """A brigade as the timetable and the positions may spell it differently ("05" and "5") compared as one."""
    text = str(brigade).strip().lstrip("0")
    return text or "0"


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """The direction from the first place to the second in degrees from the north (0-359)."""
    phi1, phi2, delta = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(delta) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta)
    return round((math.degrees(math.atan2(y, x)) + 360) % 360) % 360


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """The distance in metres between two points on the Earth (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Vehicle:
    """One position the City reported: the vehicle, the line and brigade it works, where it was and when."""

    number: str
    line: str
    brigade: str
    latitude: float
    longitude: float
    moment: datetime  # UTC

    def age(self, now: datetime) -> timedelta:
        """How long ago the City saw it."""
        return now - self.moment


def _moment_of(text: str, now: datetime) -> datetime:
    """The UTC moment of a Warsaw wall-clock time. In the hour that is repeated when the clocks go back it is ambiguous: of the
    two moments it can be, the one that is not ahead of ``now`` and nearest to it is taken (a fresh position is fresh in either hour)."""
    wall = datetime.fromisoformat(text.replace(" ", "T"))
    candidates = [wall.replace(tzinfo=WARSAW, fold=fold).astimezone(dt_util.UTC) for fold in (0, 1)]
    past = [c for c in candidates if c <= now + timedelta(seconds=60)]
    return max(past) if past else min(candidates)


def _vehicle_of(row: Any, now: datetime) -> Vehicle | None:
    """One row of the City's answer as a Vehicle, or None when it is not a position that can be used (``now`` settles the hour that repeats when the clocks go back)."""
    if not isinstance(row, dict):
        return None
    try:
        latitude, longitude = float(row["Lat"]), float(row["Lon"])
        moment = _moment_of(str(row["Time"]), now)
        line, brigade, number = str(row["Lines"]).strip(), brigade_key(row["Brigade"]), str(row["VehicleNumber"]).strip()
    except (KeyError, TypeError, ValueError):
        return None
    if not (math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return Vehicle(number, line.upper(), brigade, latitude, longitude, moment)


class VehicleFeed:
    """The positions of the vehicles that some entity follows, fetched together every ``POLL_EVERY`` while one is wanted."""

    def __init__(self, hass: HomeAssistant, client: ZTMStopClient) -> None:
        """Ask the City through ``client`` (any client with the token this feed is for)."""
        self._hass = hass
        self._client = client
        self._wants: dict[Wanted, CALLBACK_TYPE] = {}  # follower -> what to call when positions arrive
        self._vehicles: dict[tuple[str, str], list[Vehicle]] = {}
        self._unsub: CALLBACK_TYPE | None = None
        self._failures = 0
        self._skip = 0  # polls still to skip after a failure
        self.failed = False  # the last poll failed (cleared by the next that worked)
        self._polled: set[str] = set()  # the lines a poll has worked for since the feed was made (what it holds for them is what the City reports)
        self._fleet: dict[str, dict[str, Any]] = {}  # the City's fleet by fleet number, as far as it was read
        self._fleet_read: datetime | None = None  # when it was asked for last, whatever the outcome
        self._fleet_ok = False  # whether that last ask worked (a later failure keeps what was read, but is retried soon)

    async def ensure_fleet(self) -> bool:
        """Read the City's fleet when it is not read yet or is a day old (an hour after a failure): True when it was read now.
        The facts about a vehicle (operator, depot, registration ...) change slowly, and are shown on a pin as they are."""
        now = dt_util.utcnow()
        wait = FLEET_REFRESH if self._fleet_ok else FLEET_RETRY
        if self._fleet_read is not None and now - self._fleet_read < wait:
            return False
        self._fleet_read = now
        self._fleet_ok = False
        try:
            fleet = await self._client.get_fleet()
        except Exception as err:  # noqa: BLE001
            # The facts are a courtesy: only the class is logged, because the text of an error can carry the URL.
            _LOGGER.debug("The City's fleet could not be read (%s)", type(err).__name__)
            return False
        if not fleet:
            return False
        self._fleet, self._fleet_ok = fleet, True
        return True

    def has_polled(self, line: str) -> bool:
        """Whether a poll that asked for this line has worked: before that the feed knows nothing about its vehicles."""
        return line.upper() in self._polled

    def details_of(self, line: str, number: str) -> dict[str, Any]:
        """What the City's fleet says about this vehicle of this line (empty while the fleet is not read or does not know it). A bus and a
        tram can have the same number, so the kind (by the line) is part of the key."""
        kind = TRAM if TRAM_LINE.fullmatch(line.upper()) else BUS
        return self._fleet.get(f"{kind}/{str(number).strip()}", {})

    def uses_key_of(self, client: ZTMStopClient) -> bool:
        """Whether this feed asks the City with the same key as ``client`` does."""
        return self._client.has_same_key_as(client)

    @callback
    def subscribe(self, wanted: Wanted, changed: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Follow the feed: ``wanted`` says which line to look for (None: nothing now), ``changed`` is called after each poll.
        Returns what stops following; the last follower to go stops the polling."""
        self._wants[wanted] = changed
        if self._unsub is None:
            self._unsub = async_track_time_interval(self._hass, self._tick, POLL_EVERY)
            self._hass.async_create_task(self.poll())  # the first positions need not wait half a minute

        @callback
        def unsubscribe() -> None:
            """Stop following; the timer goes with the last follower."""
            self._wants.pop(wanted, None)
            self._polled &= {line.upper() for line in (w() for w in tuple(self._wants)) if line}  # a line that left must be polled again when it returns
            if not self._wants and self._unsub is not None:
                self._unsub()
                self._unsub = None

        return unsubscribe

    async def _tick(self, _now: datetime) -> None:
        """Poll, unless a failure asked for a pause."""
        if self._skip > 0:
            self._skip -= 1
            self._notify()  # a position grows old while the City is not asked
            return
        await self.poll()

    async def poll(self) -> None:
        """Ask the City for the vehicles of the lines that are wanted now (nothing is asked when none is), then tell the followers."""
        lines = {line.upper() for line in (wanted() for wanted in tuple(self._wants)) if line}
        if not lines:
            self._vehicles = {}
            self._notify()  # the followers' state depends on the time too
            return
        found, failed = await self._fetch(lines)
        if failed:
            self._failures += 1
            self._skip = min(2 ** (self._failures - 1) - 1, int(MAX_BACKOFF / POLL_EVERY))
            if self._failures == 1:
                _LOGGER.warning("The City did not send the positions of the vehicles; trying again soon")
        else:
            if self._failures:
                _LOGGER.info("The positions of the vehicles are back")
            self._failures, self._skip = 0, 0
            self._vehicles = found
            self._polled |= lines
        self.failed = failed
        self._notify()

    async def _fetch(self, lines: set[str]) -> tuple[dict[tuple[str, str], list[Vehicle]], bool]:
        """The positions of the vehicles of ``lines`` by (line, brigade), and whether any of the City's answers was missing."""
        found: dict[tuple[str, str], list[Vehicle]] = {}
        failed = False
        for kind in sorted({TRAM if TRAM_LINE.fullmatch(line) else BUS for line in lines}):
            rows = await self._client.get_vehicles(kind)
            if rows is None:
                failed = True
                continue
            now = dt_util.utcnow()
            for vehicle in filter(None, (_vehicle_of(row, now) for row in rows)):
                if vehicle.line in lines:
                    found.setdefault((vehicle.line, vehicle.brigade), []).append(vehicle)
        return found, failed

    @callback
    def _notify(self) -> None:
        """Tell the followers that the positions (or the time) changed."""
        for changed in tuple(self._wants.values()):
            changed()

    def find(self, line: str, brigade: object) -> Vehicle | None:
        """The vehicle that works this brigade of this line, the one seen last when the City reports several; it may be an old
        position (see ``Vehicle.age``), which the caller decides on."""
        candidates = self._vehicles.get((str(line).upper(), brigade_key(brigade)))
        return max(candidates, key=lambda v: v.moment) if candidates else None


    def vehicles_of(self, line: str) -> list[Vehicle]:
        """The vehicles of this line seen within ``MAX_AGE``, one per vehicle number (its newest position): what is on the map now."""
        wanted = str(line).upper()
        newest: dict[str, Vehicle] = {}
        now = dt_util.utcnow()
        for (vehicle_line, _brigade), seen in self._vehicles.items():
            if vehicle_line != wanted:
                continue
            for vehicle in seen:
                if vehicle.age(now) <= MAX_AGE and (vehicle.number not in newest or vehicle.moment > newest[vehicle.number].moment):
                    newest[vehicle.number] = vehicle
        return list(newest.values())


def feed_for(hass: HomeAssistant, client: ZTMStopClient) -> VehicleFeed:
    """The one feed of the key this client uses (every entity with that key shares the positions and the polling)."""
    feeds: list[VehicleFeed] = hass.data.setdefault(f"{DOMAIN}_vehicles", [])
    for feed in feeds:
        if feed.uses_key_of(client):
            return feed
    feed = VehicleFeed(hass, client)
    feeds.append(feed)
    return feed
