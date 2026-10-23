"""How far the vehicle of the next departure is from the stop, in metres: a sensor, for automations ("the bus is 500 m away").

A departure in the timetable names its brigade, and the City reports where every vehicle of a line and brigade is, so the
vehicle that will make the next departure can be found (``vehicles.py``). The sensor exists only for a line that shows its vehicles (the option of the line, with a token); it asks the City
for positions only while the next departure is near. It has no coordinates on purpose: the pins of
the vehicles on the map are the business of the line (``geo_location.py``), and a position here would put the same vehicle on the
map once more for every stop of the line. When there is no vehicle to measure (it has not started yet, the City does not report it,
or its position is old) the sensor has no value and its ``Status`` says why.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfLength
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .coordinator import ZTMStopCoordinator
from .entity import ZtmStopEntity, stop_place
from .vehicles import MAX_AGE, WANTED_WITHIN, Vehicle, VehicleFeed, distance_m

# What ``Status`` can say (the attribute is for a card or a template, in English like the other attributes).
TRACKING = "tracking"
NO_BRIGADE = "no_brigade"  # the departure does not say which brigade makes it, so no vehicle can be found
NO_VEHICLE = "no_vehicle"  # the vehicle has not started the line yet, or the City does not report it
OLD_POSITION = "old_position"
TOO_EARLY = "too_early"  # the next departure is not near yet, so nothing is asked
CITY_UNAVAILABLE = "city_unavailable"
NO_TIMETABLE = "no_timetable"


class ZTMVehicleDistanceSensor(ZtmStopEntity, SensorEntity):
    """The distance in metres between the stop and the vehicle that will make the next departure of its line."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    # No state class on purpose: the distance of a bus is not something to add up over hours, and a state class would make Home Assistant
    # keep long-term statistics for it (and list them under Statistics when the sensor is removed or excluded from the recorder).
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: ZTMStopCoordinator, feed: VehicleFeed):
        """Name the sensor after its stop and put it on the device of that stop."""
        line, stop_id, stop_nr = coordinator.line, coordinator.stop_id, coordinator.stop_nr
        super().__init__(coordinator, line, stop_nr)
        self._feed = feed
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_nr}_vehicle_distance"
        self._attr_name = f"Line {line} from {stop_id}/{stop_nr} Vehicle distance"
        self._attr_translation_key = "vehicle_distance"  # its icon is in icons.json

    async def async_added_to_hass(self) -> None:
        """Follow the feed while the entity is on: the feed polls for it when its next departure is near."""
        await super().async_added_to_hass()
        self._take_stop_name()  # now that the entity ID is made (from the numbers), the name may carry the stop's name
        self.async_on_remove(self._feed.subscribe(self._wanted_line, self._feed_changed))

    def _take_stop_name(self) -> None:
        """Put the stop's name into the entity's name once it is known (the entity ID was made from the numbers)."""
        name = self._name_with_stop("Vehicle distance")
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

    def _walk(self) -> timedelta:
        """The time the user needs to walk to the stop (none when no walking time is set)."""
        return timedelta(minutes=self.coordinator.walking_minutes)

    def _next_departure(self) -> Any:
        """The departure the main sensor shows as the next one (the first that is not sooner than the walking time), or None
        (no timetable that may be shown, or none ahead)."""
        now = dt_util.utcnow()
        if not self.coordinator.is_usable(now):
            return None
        upcoming = self.coordinator.upcoming(now + self._walk())
        return upcoming[0] if upcoming else None

    def _wanted_line(self) -> str | None:
        """The line to look for while the next departure is near (counted from when the user has to leave), else None
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
        """Why the sensor shows what it shows."""
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
    def available(self) -> bool:
        """Available while the coordinator holds a timetable that may be shown (without a vehicle the state is unknown)."""
        return self.coordinator.is_usable(dt_util.utcnow())

    @property
    def native_value(self) -> int | None:
        """The distance in metres from the stop to the vehicle, or None when there is no vehicle to measure."""
        if self._wanted_line() is None:  # not yet: another follower of the line may have made the feed hold a vehicle, but this departure is far
            return None
        vehicle = self._shown()
        place = stop_place(self._stop_info())
        return round(distance_m(vehicle.latitude, vehicle.longitude, *place)) if vehicle and place else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The status, and for a vehicle that is shown its number, brigade and the time of its position."""
        attrs: dict[str, Any] = {"Status": self._status(), "Line": self.coordinator.line}
        vehicle = self._shown()
        if vehicle is not None:
            attrs.update({"Vehicle number": vehicle.number, "Brigade": vehicle.brigade, "Position time": vehicle.moment.isoformat()})
        return attrs
