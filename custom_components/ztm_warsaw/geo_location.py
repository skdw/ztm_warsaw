"""The map: one pin for every stop pole and one for every vehicle of the lines that show theirs.

Each thing on the map has exactly one owner, so nothing is drawn twice however many lines and stops are set up:

* **A stop pole** is one pin whatever number of the user's lines stop there (the lines are in its ``Lines`` attribute and in its
  name, which the map card writes under the pin). Poles belong to the whole integration, not to a line: ``MapLayers`` keeps one
  pin per pole and lets one of the loaded lines host it (the entity is added through that line's platform), and hands it over to
  another line when the host is unloaded.
* **A vehicle** is one pin, with the badge of its line, and belongs to its line (a line is one entry, so a vehicle cannot be drawn
  by two). A line shows its vehicles when its option ``show_vehicles`` is on (*Configure* on the line; a token is needed).

The pins of the poles are ``geo_location`` entities without a registry entry (they are shared by lines, and a registry entry belongs to
one). The pins of the vehicles have a unique ID and sit on a device of their line, as Home Assistant's documentation allows for
entities that come and go: they are removed, registry entry and device included, when the City stops reporting the vehicle, so they show
on the integration's page while they exist. A map card lists them all with ``geo_location_sources: [ztm_warsaw]``. The entity ID of
a vehicle is made from the name it has when it is first added ("Line 126 · 1722"); where it heads ("Line 126 → Rechniewskiego") goes
into the name only, because the timetable changes while an ID must not. The device is named like the line, so Home Assistant does not
put another name in front of the pin's.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_SHOW_VEHICLES, DOMAIN
from .coordinator import ZTMStopCoordinator
from .entity import stop_info_of, stop_place
from .entries import runtimes
from .runtime import ZtmConfigEntry
from .utils import get_line_badge, get_line_type, get_stop_badge
from .vehicles import Vehicle, VehicleFeed, bearing_deg, brigade_key, distance_m, feed_for

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # nothing is fetched here: the pins show what the coordinators and the feed already hold

LAYERS_KEY = f"{DOMAIN}_map"  # in hass.data: the MapLayers of the instance


def _line_order(line: str) -> tuple[int, int, str]:
    """The order lines are listed in: numbers first (126 before 176), then the others (N64, S3)."""
    return (0, int(line), line) if line.isdigit() else (1, 0, line)


HEADING_WITHIN = timedelta(minutes=40)  # how far from now a departure of the brigade may be to say where its vehicle is heading
MOVED_AT_LEAST = 25  # metres between two positions for a speed and a course to be worked out (a vehicle that stands still reports noise)
MAX_SPEED = 120  # km/h: more is a jump of the position, not a bus


@dataclass(frozen=True)
class Planned:
    """What the timetable says about the vehicle of a brigade: where it goes, by which route, with which notes, and at which of the
    user's stops and when it is due there."""

    direction: str
    route: str | None
    notes: str | None
    stop: str
    departure: str  # the local time, ISO 8601


def planned_of(entry: ZtmConfigEntry, brigade: str) -> Planned | None:
    """The departure of this brigade that is nearest to now, within ``HEADING_WITHIN``, among the stops of the line that are set up: its
    destination ("kierunek"), route ("trasa"), notes ("symbol_1/2"), the stop and the time. The City's positions say none of it, but the
    timetable of every stop names the brigade of each departure. None when no stop of the line has such a departure."""
    now = dt_util.utcnow()
    best: tuple[timedelta, Any, str] | None = None
    for runtime in runtimes(entry).values():
        coordinator = runtime["coordinator"]
        for reading in getattr(coordinator.data, "departures", None) or []:
            if reading.dt is None or reading.brygada is None or brigade_key(reading.brygada) != brigade:
                continue
            gap = abs(reading.dt - now)
            if gap <= HEADING_WITHIN and reading.kierunek not in ("", "unknown") and (best is None or gap < best[0]):
                name = stop_info_of(coordinator).get("nazwa_zespolu")
                best = (gap, reading, f"{name} {coordinator.stop_nr}" if name else f"{coordinator.stop_id}/{coordinator.stop_nr}")
    if best is None:
        return None
    reading = best[1]
    notes = ", ".join(str(n) for n in (reading.symbol_1, reading.symbol_2) if n)
    return Planned(reading.kierunek, reading.trasa or None, notes or None, best[2], dt_util.as_local(reading.dt).isoformat())


async def _retire(hass: HomeAssistant, pin: "_Pin") -> None:
    """Take a pin away for good: out of the state machine and, when it has a registry entry, out of the entity registry and, when
    nothing else is on its device, off the integration's page too (as the documentation asks for an entity created with a unique ID: a
    registry entry left behind would show as an unavailable entity for ever)."""
    entity_id = pin.entity_id
    if pin.hass is not None and entity_id:
        await pin.async_remove(force_remove=True)
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id) if entity_id else None
    if entry is None:
        return
    registry.async_remove(entity_id)
    if entry.device_id and not er.async_entries_for_device(registry, entry.device_id):
        dr.async_get(hass).async_remove_device(entry.device_id)


class _Pin(GeolocationEvent):
    """What the pins have in common: a source (what a map card lists), no polling, the distance from home as the state."""

    _attr_should_poll = False
    _attr_source = DOMAIN
    _full_name: str = ""  # what the pin says about itself; the entity ID is made from the shorter name it is added with

    async def async_added_to_hass(self) -> None:
        """Once added (and its ID made from the short name), say the full name."""
        if self._full_name:
            self._attr_name = self._full_name

    def _set_place(self, latitude: float, longitude: float) -> None:
        """Move the pin and work out how far it is from the home of the Home Assistant instance, which is the state. Home Assistant gives
        it in the length unit of the instance (kilometres, or miles for US customary units), and that is what is kept."""
        self._attr_latitude, self._attr_longitude = latitude, longitude
        home = self.hass.config.distance(latitude, longitude) if self.hass is not None else None
        self._attr_distance = round(home, 1) if home is not None else None

    def _publish(self) -> None:
        """Write the new state, when the pin is on the map already."""
        if self.hass is not None and self.entity_id:
            self.async_write_ha_state()


class PoleMarker(_Pin):
    """The pin of one stop pole: the sign with its number, named after the stop and the lines that stop there."""

    def __init__(self, hass: HomeAssistant, stop_id: str, stop_nr: str) -> None:
        """A pin for a pole; ``update`` gives it a name, a place and its lines."""
        self.hass = hass
        self._stop_id, self._stop_nr = stop_id, stop_nr
        self._attr_entity_picture = get_stop_badge(stop_nr)
        self._lines: list[str] = []

    def update(self, name: str | None, latitude: float, longitude: float, lines: list[str]) -> None:
        """Take the stop's name, its place and the lines that stop at it (in order), and show them."""
        self._lines = lines
        label = f"{name} {self._stop_nr}" if name else f"{self._stop_id}/{self._stop_nr}"
        self._attr_name = f"{label} · {', '.join(lines)}"
        self._set_place(latitude, longitude)
        self._publish()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The stop and the lines that stop at it."""
        return {"Stop, ID": self._stop_id, "Stop, Number": self._stop_nr, "Lines": ", ".join(self._lines)}


class VehiclePin(_Pin):
    """The pin of one vehicle: the badge of its line, named after where it goes (or the line and its number while that is not known)."""

    def __init__(self, hass: HomeAssistant, line: str, vehicle: Vehicle, planned: Planned | None = None, details: dict[str, Any] | None = None) -> None:
        """A pin for a vehicle of ``line`` at the place the City last reported it, with what the timetable and the City's fleet say about it."""
        self.hass = hass
        self._line = line
        self._speed: int | None = None
        self._course: int | None = None
        self._attr_unique_id = f"vehicle_{line}_{vehicle.number}"
        self._attr_entity_picture = get_line_badge(line)
        self._attr_name = f"Line {line} · {vehicle.number}"  # what its entity ID is made from
        self._vehicle: Vehicle | None = None
        self.move(vehicle, planned, details)

    def move(self, vehicle: Vehicle, planned: Planned | None = None, details: dict[str, Any] | None = None) -> None:
        """Put the pin where the vehicle is now, with the name that tells where it goes: "Line 126 → Rechniewskiego", or the
        vehicle's number while the timetable does not say. The timetable can change, so this is the name, not the ID. The speed and the
        course come from the last two positions, when the vehicle has moved between them."""
        before, self._vehicle = self._vehicle, vehicle
        self._planned, self._details = planned, details or {}
        self._full_name = f"Line {self._line} → {planned.direction}" if planned else f"Line {self._line} · {vehicle.number}"
        if before is not None and before.moment != vehicle.moment:
            self._take_motion(before, vehicle)
        if self.entity_id:
            self._attr_name = self._full_name
        self._set_place(vehicle.latitude, vehicle.longitude)
        self._publish()

    def _take_motion(self, before: Vehicle, now: Vehicle) -> None:
        """The speed (km/h) and the course (degrees) between two positions; a vehicle that has hardly moved keeps what it had, and a speed
        no bus reaches (a jump of the position) is not taken."""
        metres = distance_m(before.latitude, before.longitude, now.latitude, now.longitude)
        seconds = (now.moment - before.moment).total_seconds()
        if metres < MOVED_AT_LEAST or seconds <= 0:
            return
        speed = metres / seconds * 3.6
        if speed <= MAX_SPEED:
            self._speed = round(speed)
            self._course = bearing_deg(before.latitude, before.longitude, now.latitude, now.longitude)

    @property
    def device_info(self) -> DeviceInfo:
        """The device of the vehicles of the line, so that they are listed under it on the integration's page."""
        return {
            "identifiers": {(DOMAIN, f"vehicles_{self._line}")},
            "name": f"Line {self._line}",
            "manufacturer": "Zarząd Transportu Miejskiego",
            "entry_type": DeviceEntryType.SERVICE,
            "model": f"Vehicles on the map ({get_line_type(self._line)})",
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """What the City says: the line, the brigade, the vehicle's number and when it was seen there; from the timetable where it goes
        (the planned destination, not a live one), the route, notes, and the stop and time it is due; from the fleet the operator, depot,
        registration, year and type; and the speed and course worked out from the last two positions."""
        vehicle = self._vehicle
        assert vehicle is not None, "a pin always has a position"
        planned = self._planned
        return {
            "Line": self._line,
            **({"Direction": planned.direction} if planned else {}),
            **({"Route": planned.route} if planned and planned.route else {}),
            **({"Notes": planned.notes} if planned and planned.notes else {}),
            **({"Scheduled at": planned.stop, "Scheduled departure": planned.departure} if planned else {}),
            "Brigade": vehicle.brigade,
            "Vehicle number": vehicle.number,
            **self._details,
            **({"Speed, km/h": self._speed, "Course, degrees": self._course} if self._speed is not None and self._course is not None else {}),
            "Position time": vehicle.moment.isoformat(),
        }


class MapLayers:
    """The poles on the map of one Home Assistant instance: one pin for each, hosted by one of the loaded lines (see the module)."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Nothing is loaded yet."""
        self._hass = hass
        self._entries: dict[str, ZtmConfigEntry] = {}  # the loaded lines, in the order they came
        self._adders: dict[str, AddConfigEntryEntitiesCallback] = {}
        self._unsubs: dict[str, list[CALLBACK_TYPE]] = {}
        self._markers: dict[tuple[str, str], tuple[str, PoleMarker]] = {}  # pole -> (the line entry that hosts it, its pin)

    def add_entry(self, entry: ZtmConfigEntry, adder: AddConfigEntryEntitiesCallback) -> None:
        """A line has loaded: its poles are on the map (if they are not already), and the map follows what its coordinators learn."""
        self._entries[entry.entry_id] = entry
        self._adders[entry.entry_id] = adder
        self._unsubs[entry.entry_id] = [r["coordinator"].async_add_listener(self.refresh) for r in runtimes(entry).values()]
        self.refresh()

    def drop_entry(self, entry_id: str) -> None:
        """A line is unloaded: its pins are taken away (also here, so that none is left on the map whatever the platform did); the poles another line also serves move to that line."""
        for unsub in self._unsubs.pop(entry_id, []):
            unsub()
        self._entries.pop(entry_id, None)
        self._adders.pop(entry_id, None)
        for pole in [p for p, (host, _pin) in self._markers.items() if host == entry_id]:
            _host, pin = self._markers.pop(pole)
            if pin.hass is not None:  # Home Assistant takes it away with the platform; this makes sure, so that no pin is left behind
                self._hass.async_create_task(pin.async_remove())  # when a new one is made for the pole by the refresh below
        self.refresh()

    @callback
    def refresh(self) -> None:
        """Make the pins what the loaded lines say: one for each pole with a place, named for the lines that stop there."""
        wanted: dict[tuple[str, str], tuple[str | None, float, float, set[str]]] = {}
        order: dict[tuple[str, str], str] = {}  # the first loaded line that serves a pole hosts it
        for entry_id, entry in self._entries.items():
            for runtime in runtimes(entry).values():
                coordinator: ZTMStopCoordinator = runtime["coordinator"]
                info = stop_info_of(coordinator)
                place = stop_place(info)
                if place is None:
                    continue
                pole = (str(coordinator.stop_id), str(coordinator.stop_nr))
                name = info.get("nazwa_zespolu")
                lines = wanted.setdefault(pole, (name if isinstance(name, str) else None, place[0], place[1], set()))[3]
                lines.add(str(coordinator.line))
                order.setdefault(pole, entry_id)
        for pole in [p for p in self._markers if p not in wanted]:
            _host, pin = self._markers.pop(pole)
            self._hass.async_create_task(pin.async_remove())
        for pole, (name, latitude, longitude, lines) in wanted.items():
            ordered = sorted(lines, key=_line_order)
            if pole in self._markers:
                self._markers[pole][1].update(name, latitude, longitude, ordered)
                continue
            host = order[pole]
            pin = PoleMarker(self._hass, *pole)
            pin.update(name, latitude, longitude, ordered)
            self._markers[pole] = (host, pin)
            self._adders[host]([pin])


class LineVehicles:
    """The vehicles of one line on the map (a line with ``show_vehicles`` on): a pin for each, added when it appears, moved when the City
    reports it again, and taken away when it is not reported any more or its position is too old."""

    def __init__(
        self, hass: HomeAssistant, line: str, feed: VehicleFeed, adder: AddConfigEntryEntitiesCallback, planned: Callable[[str], Planned | None] | None = None
    ) -> None:
        """Follow ``feed`` for the vehicles of ``line``; the pins are added through ``adder``, each with what the timetable says about its
        brigade (``planned``) and what the City's fleet says about the vehicle."""
        self._hass, self._line, self._feed, self._adder = hass, line, feed, adder
        self._planned = planned or (lambda _brigade: None)
        self._pins: dict[str, VehiclePin] = {}
        self._unsub: Callable[[], None] | None = None

    def start(self) -> None:
        """Ask the feed for this line (it polls while any line wants vehicles) and show what it has."""
        self._unsub = self._feed.subscribe(lambda: self._line, self._update)
        self._update()
        self._hass.async_create_background_task(self._read_fleet(), f"{DOMAIN} fleet")  # the facts about the vehicles come when they come

    async def _read_fleet(self) -> None:
        """Read the City's fleet (when it is not read, or is a day old) and show what it says on the pins."""
        if await self._feed.ensure_fleet() and self._unsub is not None:
            self._update()

    def stop(self) -> None:
        """Stop following; Home Assistant takes the pins away with the platform."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        self._pins.clear()

    @callback
    def _update(self) -> None:
        """Bring the pins in line with the vehicles the feed holds for this line."""
        now = {vehicle.number: vehicle for vehicle in self._feed.vehicles_of(self._line)}
        for number in [n for n in self._pins if n not in now]:
            self._hass.async_create_task(_retire(self._hass, self._pins.pop(number)))
        fresh = []
        for number, vehicle in now.items():
            planned, details = self._planned(vehicle.brigade), self._feed.details_of(number)
            if number in self._pins:
                self._pins[number].move(vehicle, planned, details)
            else:
                pin = self._pins[number] = VehiclePin(self._hass, self._line, vehicle, planned, details)
                fresh.append(pin)
        if fresh:
            self._adder(fresh)


def _forget_vehicles(hass: HomeAssistant, config_entry: ZtmConfigEntry) -> None:
    """Take the registry entries of vehicle pins of this line out: a vehicle is only an entity while the City reports it."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, config_entry.entry_id):
        if entity.platform == DOMAIN and entity.domain == "geo_location" and entity.unique_id.startswith("vehicle_"):
            registry.async_remove(entity.entity_id)


def shows_vehicles(entry: ZtmConfigEntry) -> bool:
    """Whether the line shows its vehicles on the map (its option; off by default)."""
    return bool(entry.options.get(CONF_SHOW_VEHICLES, False))


# Home Assistant awaits the platform's setup function, so it has to be a coroutine function although it awaits nothing.
async def async_setup_entry(hass: HomeAssistant, config_entry: ZtmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:  # NOSONAR
    """Put the poles of the line on the map, and its vehicles when the line shows them and has a token."""
    _forget_vehicles(hass, config_entry)  # after a restart these entries have no entity behind them: the pins are made again below
    layers: MapLayers = hass.data.setdefault(LAYERS_KEY, MapLayers(hass))
    layers.add_entry(config_entry, async_add_entities)
    config_entry.async_on_unload(lambda: layers.drop_entry(config_entry.entry_id))
    stops = [r for r in runtimes(config_entry).values() if r["client"].uses_token]
    if not shows_vehicles(config_entry) or not stops:
        return  # the vehicles are off, or need a token
    pins = LineVehicles(
        hass, stops[0]["coordinator"].line, feed_for(hass, stops[0]["client"]), async_add_entities, lambda brigade: planned_of(config_entry, brigade)
    )
    pins.start()
    config_entry.async_on_unload(pins.stop)
