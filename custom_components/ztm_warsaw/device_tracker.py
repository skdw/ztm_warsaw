"""The vehicle of the next departure, as a pin on the map.

A departure in the timetable names its brigade, and the City reports where every vehicle of a line and brigade is, so the
vehicle that will make the next departure can be found and followed (``vehicles.py``). The entity is off by default; it
asks the City for positions only once it is switched on and only while the next departure is near. When there is no
vehicle to show (it has not started yet, the City does not report it, or its position is old) the entity has no position
and its ``Status`` says why, instead of showing a place the vehicle is no longer at.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.device_tracker import TrackerEntity  # type: ignore[attr-defined]  # exported at runtime in every version, but not declared so by 2026.10
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import ZTMStopCoordinator
from .entity import ZtmStopEntity
from .entries import runtimes
from .runtime import ZtmConfigEntry
from .vehicles import MAX_AGE, WANTED_WITHIN, Vehicle, VehicleFeed, distance_m, feed_for

PARALLEL_UPDATES = 0  # the feed fetches the positions once for all the entities: nothing to limit per entity

# What ``Status`` can say (the attribute is for a card or a template, in English like the other attributes).
TRACKING = "tracking"
NO_BRIGADE = "no_brigade"  # the departure does not say which brigade makes it, so no vehicle can be found
NO_VEHICLE = "no_vehicle"  # the vehicle has not started the line yet, or the City does not report it
OLD_POSITION = "old_position"
TOO_EARLY = "too_early"  # the next departure is not near yet, so nothing is asked
CITY_UNAVAILABLE = "city_unavailable"
NO_TIMETABLE = "no_timetable"


# Home Assistant awaits the platform's setup function, so it has to be a coroutine function although it awaits nothing.
async def async_setup_entry(hass: HomeAssistant, config_entry: ZtmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:  # NOSONAR
    """Add the vehicle tracker of every stop whose key is a token (only the new host knows where the vehicles are)."""
    for subentry_id, runtime in runtimes(config_entry).items():
        client = runtime["client"]
        if client.uses_token:
            feed = feed_for(hass, client)
            async_add_entities([ZTMVehicleTracker(runtime["coordinator"], feed)], config_subentry_id=subentry_id)


class ZTMVehicleTracker(ZtmStopEntity, TrackerEntity):
    """The vehicle that will make the next departure of one line at one pole."""

    _attr_entity_registry_enabled_default = False  # it asks the City for positions: for those who want them

    def __init__(self, coordinator: ZTMStopCoordinator, feed: VehicleFeed):
        """Name the tracker after its stop and put it on the device of that stop."""
        line, stop_id, stop_nr = coordinator.line, coordinator.stop_id, coordinator.stop_nr
        super().__init__(coordinator, line, stop_nr)
        self._feed = feed
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_nr}_vehicle"
        self._attr_name = f"Line {line} from {stop_id}/{stop_nr} Vehicle"
        self._attr_translation_key = "vehicle"  # its icon is in icons.json

    async def async_added_to_hass(self) -> None:
        """Follow the feed while the entity is on: the feed polls for it when its next departure is near."""
        await super().async_added_to_hass()
        self._take_stop_name()  # now that the entity ID is made (from the numbers), the name may carry the stop's name
        self.async_on_remove(self._feed.subscribe(self._wanted_line, self._feed_changed))

    def _take_stop_name(self) -> None:
        """Put the stop's name into the entity's name once it is known (the entity ID was made from the numbers)."""
        name = self._name_with_stop("Vehicle")
        if name:
            self._attr_name = name

    @callback
    def _handle_coordinator_update(self) -> None:
        """A new timetable (or the stop's name arriving): take the name and show the state again."""
        self._take_stop_name()
        super()._handle_coordinator_update()

    @callback
    def _feed_changed(self) -> None:
        """The positions (or the time) changed: show them."""
        self.async_write_ha_state()

    def _next_departure(self) -> Any:
        """The departure the main sensor shows as the next one (the first that is not sooner than the walking time), or None
        (no timetable that may be shown, or none ahead)."""
        now = dt_util.utcnow()
        if not self.coordinator.is_usable(now):
            return None
        upcoming = self.coordinator.upcoming(now + self._walk())
        return upcoming[0] if upcoming else None

    def _walk(self) -> timedelta:
        """The time the user needs to walk to the stop (none when no walking time is set)."""
        return timedelta(minutes=self.coordinator.walking_minutes)

    def _wanted_line(self) -> str | None:
        """The line to look for while the next departure is near (counting from when the user has to leave), else None
        (then nothing is asked of the City)."""
        departure = self._next_departure()
        if departure is None or not departure.brygada or departure.moment - dt_util.utcnow() > WANTED_WITHIN + self._walk():
            return None
        return self.coordinator.line

    def _vehicle(self) -> Vehicle | None:
        """The vehicle of the next departure, as last seen (maybe long ago: see ``_status``)."""
        departure = self._next_departure()
        if departure is None or not departure.brygada:
            return None
        return self._feed.find(self.coordinator.line, departure.brygada)

    def _shown(self) -> Vehicle | None:
        """The vehicle only while its position is recent enough to be where it is."""
        vehicle = self._vehicle()
        return vehicle if vehicle is not None and vehicle.age(dt_util.utcnow()) <= MAX_AGE else None

    def _status(self) -> str:
        """Why the tracker shows what it shows."""
        departure = self._next_departure()
        if departure is None:
            return NO_TIMETABLE
        if not departure.brygada:
            return NO_BRIGADE
        if self._wanted_line() is None:
            return TOO_EARLY
        if self._shown() is not None:
            return TRACKING
        if self._feed.failed:
            return CITY_UNAVAILABLE
        return OLD_POSITION if self._vehicle() is not None else NO_VEHICLE

    @property
    def latitude(self) -> float | None:
        """Where the vehicle is, or None when there is none to show."""
        vehicle = self._shown()
        return vehicle.latitude if vehicle else None

    @property
    def longitude(self) -> float | None:
        """Where the vehicle is, or None when there is none to show."""
        vehicle = self._shown()
        return vehicle.longitude if vehicle else None

    @property
    def available(self) -> bool:
        """Available while the coordinator holds a timetable that may be shown (without a vehicle the state is unknown)."""
        return self.coordinator.is_usable(dt_util.utcnow())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The status, and for a vehicle that is shown its number, brigade, the time of the position and how far it is from the stop."""
        attrs: dict[str, Any] = {"Status": self._status(), "Line": self.coordinator.line}
        vehicle = self._shown()
        if vehicle is None:
            return attrs
        attrs.update({"Vehicle number": vehicle.number, "Brigade": vehicle.brigade, "Position time": vehicle.moment.isoformat()})
        info = self._stop_info()
        try:
            stop_lat, stop_lon = float(info["szer_geo"]), float(info["dlug_geo"])
        except (KeyError, TypeError, ValueError):
            return attrs
        attrs["Distance to stop"] = round(distance_m(vehicle.latitude, vehicle.longitude, stop_lat, stop_lon))
        return attrs
