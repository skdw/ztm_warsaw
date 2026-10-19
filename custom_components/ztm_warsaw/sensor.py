"""The sensors of a stop: the next departures of the line at the pole, and a diagnostic sensor for the last refresh.

The state of ``ZTMSensor`` is the next departure (a timestamp), the attributes list the three after it and the stop
(its name, position, direction ...). A sensor wakes up at the next departure instead of polling, and writes its
state only when it changed. The names of the attributes are part of the public contract of the integration.
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from homeassistant.util import dt as dt_util
from homeassistant.util.dt import as_local

from .utils import get_line_badge, get_line_icon, get_line_type

from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.core import callback

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import NEXT_DEPARTURES, DOMAIN, CONF_ATTRIBUTION
from .coordinator import ZTMStopCoordinator
from .entries import runtimes
from .models import WARSAW, next_warsaw_midnight

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # the entities only read what their coordinator fetched: nothing to limit

def _friendly_day(dt, now):
    """Name the day of a departure relative to today in Warsaw: today, tomorrow, yesterday or the weekday."""
    if not dt:
        return NOT_AVAILABLE
    today = now.astimezone(WARSAW).date()
    day = dt.astimezone(WARSAW).date()
    if day == today:
        return "today"
    if day == today + timedelta(days=1):
        return "tomorrow"
    if day == today - timedelta(days=1):
        return "yesterday"
    return dt.astimezone(WARSAW).strftime("%a")  # Mon, Tue ...


NOT_AVAILABLE = "Not available"
TIMEZONE = "Europe/Warsaw"
# Attribute name -> key of the stop's record in the stops catalogue
_STOP_ATTRIBUTES = {
    "Stop, Name": "nazwa_zespolu",
    "Stop, Street ID": "id_ulicy",
    "Stop, Latitude": "szer_geo",
    "Stop, Longitude": "dlug_geo",
}


def _stop_info_of(coordinator):
    """The stop's record from the coordinator's data, or {}."""
    try:
        if coordinator and coordinator.data:
            return getattr(coordinator.data, "stop_info", {}) or {}
    except (AttributeError, TypeError):
        pass
    return {}


def _stop_attributes(stop_info):
    """The attributes that describe the stop; its position (``latitude`` and ``longitude``) only when it is a real place, so it can be a pin on the map."""
    attrs = {name: stop_info.get(key, NOT_AVAILABLE) for name, key in _STOP_ATTRIBUTES.items()}
    try:  # the standard names, so that the stop is a pin on Home Assistant's map card
        latitude, longitude = float(stop_info["szer_geo"]), float(stop_info["dlug_geo"])
    except (KeyError, TypeError, ValueError):
        return attrs
    if not (math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
        return attrs  # not a place ("nan" parses as a float, and a NaN would make every update look like a change)
    return {**attrs, "latitude": latitude, "longitude": longitude}


def _departure_attrs(label, dep, day, time_str=None):
    """The attributes of one departure under ``label`` ("Upcoming" or "Next 1" ...)."""
    attrs = {f"{label}, Headsign": getattr(dep, "kierunek", NOT_AVAILABLE), f"{label}, Departure Day": day}
    if time_str is not None:
        attrs[f"{label}, Departure Time"] = time_str
    attrs[f"{label}, Route ID"] = getattr(dep, "trasa", NOT_AVAILABLE)
    attrs[f"{label}, Brigade"] = getattr(dep, "brygada", NOT_AVAILABLE)
    return attrs


def _timetable_url(line):
    """The timetable page of the line for today."""
    try:
        today_str = datetime.now(tz=timezone.utc).astimezone(WARSAW).strftime("%Y-%m-%d")
        return f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt={today_str}&wtp_md=3&wtp_ln={quote(str(line))}"
    except Exception:
        return f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_md=3&wtp_ln={quote(str(line))}"


def _device_info(line, coordinator=None):
    """The device of a stop's entities. A stop of a 1.1.x entry (one entry per stop) is the line's device, shared by the
    entries of that line; the stops of a line entry each have their own device, because a device belongs to one subentry."""
    identifier, name = f"line_{line}", f"Line {line}"
    if getattr(coordinator, "device_per_stop", False):
        # Named like the line's device: Home Assistant 2026.10 puts the device's name in front of an entity's name (and
        # of its ID) unless the entity's name starts with it, and ours always start with "Line <line>". The devices of the
        # stops are told apart by the subentry they are listed under.
        identifier = f"line_{line}_{coordinator.stop_id}_{coordinator.stop_nr}"
    return {
        "identifiers": {(DOMAIN, identifier)},
        "name": name,
        "manufacturer": "Zarząd Transportu Miejskiego",
        "entry_type": "service",
        "model": get_line_type(line),
        "configuration_url": _timetable_url(line),
    }


class ZTMSensor(CoordinatorEntity, SensorEntity):
    """Sensor for tracking ZTM departures."""
    
    def __init__(self, coordinator, entry_id, stop_id, stop_number, line, max_departures):
        """Name the sensor after its line and pole (the stop's name replaces the numbers later, once the entity ID is fixed) and fix its unique ID."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._line = line
        self._stop_id = stop_id
        self._stop_number = stop_number
        self._max_departures = max_departures
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_number}"
        # Always use numeric name initially so HA registers entity_id without stop name.
        # Stop name is applied later in async_added_to_hass after entity_id is locked.
        self._attr_name = f"Line {line} from {stop_id}/{stop_number}"
        
        # Base attributes that don't change
        self._base_attrs = {
            "Line, Number": self._line,
            "Line, Type": get_line_type(self._line),
            "Line, Timezone": TIMEZONE,
            "Line, Full Timetable": f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_md=3&wtp_ln={quote(str(self._line))}",
            "Stop, ID": self._stop_id,
            "Stop, Number": self._stop_number,
        }
        
        # Attribute placeholders for no service
        self._no_service_attrs = {
            "Upcoming, Headsign": "No service",
            "Upcoming, Departure Day": NOT_AVAILABLE,
            "Upcoming, Route ID": NOT_AVAILABLE,
            "Upcoming, Brigade": NOT_AVAILABLE,
        }
        
        # Initialize attributes and state
        self._attributes = {}
        self._next_departure = None
        self._scheduled_unsub = None
        self._last_coordinator_update = None
        self._written_available: bool | None = None
        self._written_attributes: dict | None = None

    def _get_stop_info(self):
        """The stop's record from the coordinator (its name, position, street ...) for the attributes and the entity name; an empty dict until the City has given it."""
        return _stop_info_of(self.coordinator)

    @property
    def native_value(self):
        """Return the next departure as a timezone‑aware datetime (or None)."""
        return self._next_departure

    @property
    def icon(self):
        """Return appropriate icon based on transport type."""
        return get_line_icon(self._line)

    @property
    def entity_picture(self):
        """A badge with the line number: the map card draws it as the pin instead of the initials of the name."""
        return get_line_badge(self._line)

    @property
    def extra_state_attributes(self):
        """Return attributes, excluding any None values to satisfy recorder."""
        attributes = self._attributes or {}
        return {k: v for k, v in attributes.items() if v is not None}

    @property
    def device_info(self):
        """Return device info for this entity."""
        return _device_info(self._line, self.coordinator)

    def _cancel_scheduled_update(self):
        """Cancel any scheduled update."""
        if self._scheduled_unsub:
            self._scheduled_unsub()
            self._scheduled_unsub = None

    def _schedule_wakeup(self, departure_time, now):
        """Wake up at the next departure, or at midnight in Warsaw if that comes first: the labels 'today' and
        'tomorrow' change then, and nothing else would tell the sensor."""
        wake = min(departure_time, next_warsaw_midnight(now))
        try:
            self._cancel_scheduled_update()
            self._scheduled_unsub = async_track_point_in_time(self.hass, self._scheduled_update, wake)
            _LOGGER.debug("Scheduled update for %s at %s", self.entity_id, as_local(wake))
        except Exception:
            _LOGGER.exception("Failed to schedule update for %s", self.entity_id)

    def _update_from_coordinator(self):
        """Update state and attributes based on coordinator data, and write the state when something changed."""
        old_next_departure = self._next_departure
        has_new_data = (
            self.coordinator is not None
            and self.coordinator.last_update_success_time != self._last_coordinator_update
        )
        self._apply_coordinator_data(has_new_data)
        availability_changed = self.available != self._written_available
        attributes = self.extra_state_attributes
        if (
            self._next_departure != old_next_departure
            or has_new_data
            or availability_changed
            or attributes != self._written_attributes
        ):
            self._written_available = self.available
            self._written_attributes = attributes
            self.async_write_ha_state()

    def _apply_coordinator_data(self, has_new_data):
        """Show what the coordinator holds: the next departure and the ones after it, or the state of a line with no service.

        ``has_new_data`` is True when the coordinator got an answer since the last time, which restarts the wake-up of the sensor.
        """
        data = self.coordinator.data if self.coordinator else None
        if not data:
            _LOGGER.warning("No timetable data available from coordinator for %s", self.entity_id)
            self._set_no_departures()
            return

        # Update friendly name with stop name as early as possible (entity_id is already locked)
        self._update_stop_name()
        if has_new_data:
            _LOGGER.info("Coordinator has new data for %s, forcing full update", self.entity_id)
            self._last_coordinator_update = self.coordinator.last_update_success_time
            self._cancel_scheduled_update()

        now = dt_util.utcnow()
        walk = timedelta(minutes=self.coordinator.walking_minutes)
        future_departures = self.coordinator.upcoming(now + walk)  # the ones that can still be caught
        if not future_departures:
            _LOGGER.info("No future departures found for %s", self.entity_id)
            self._set_no_departures()
            return

        self._update_departure_info(future_departures, now)
        self._schedule_wakeup(future_departures[0].dt - walk, now)  # it cannot be caught any more `walk` before it leaves

    def _add_walking_time(self):
        """Show the walking time of the stop in the attributes, when one is set (a sensor without one has no such attribute)."""
        if self.coordinator.walking_minutes:
            self._attributes["Walking time, Minutes"] = self.coordinator.walking_minutes

    def _update_stop_name(self):
        """Update friendly name if stop info is now available."""
        stop_info = self._get_stop_info()
        stop_name = stop_info.get("nazwa_zespolu")
        if stop_name:
            new_name = f"Line {self._line} {stop_name} {self._stop_number}"
            if self._attr_name != new_name:
                _LOGGER.info("Updating friendly name for %s to: %s", self.entity_id, new_name)
                self._attr_name = new_name

    def _update_departure_info(self, future_departures, now):
        """Update departure information and attributes."""
        current = future_departures[0]
        self._next_departure = current.dt
        _LOGGER.info("Next departure for %s: %s → %s", self.entity_id, as_local(current.dt), current.kierunek)

        self._attributes = dict(self._base_attrs)
        self._attributes.update(_stop_attributes(self._get_stop_info()))
        self._attributes["Stop, Timezone"] = TIMEZONE
        self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        self._add_walking_time()
        self._attributes.update(_departure_attrs("Upcoming", current, _friendly_day(current.dt, now)))

        # Add information about next departures
        for seq, dep in enumerate(future_departures[1:self._max_departures + 1], start=1):
            try:
                local_dt = dep.dt.astimezone(WARSAW)
                self._attributes.update(
                    _departure_attrs(f"Next {seq}", dep, _friendly_day(dep.dt, now), local_dt.strftime("%H:%M"))
                )
            except Exception as e:
                _LOGGER.warning("Failed to process departure %d for %s: %s", seq, self.entity_id, e)

    @callback
    def _scheduled_update(self, now):
        """Callback triggered at scheduled departure time to refresh state."""
        _LOGGER.info("Scheduled update triggered for %s at departure time (%s)", self.entity_id, as_local(now))
        self._update_from_coordinator()

    def _set_no_departures(self):
        """Set attributes for no departures case."""
        self._cancel_scheduled_update()

        self._attributes = dict(self._base_attrs)
        self._attributes["Line, Full Timetable"] = _timetable_url(self._line)

        stop_info = self._get_stop_info()
        self._attributes.update(_stop_attributes(stop_info))
        if not stop_info:
            self._attributes["Stop, Direction"] = NOT_AVAILABLE
            self._attributes["Stop, Effective From"] = NOT_AVAILABLE
        self._attributes["Stop, Timezone"] = TIMEZONE

        # Only set no service attributes (do not set Upcoming..., Next..., etc.)
        self._attributes.update(self._no_service_attrs)
        self._attributes["Note"] = "No upcoming schedule available. Please verify on wtp.waw.pl or call 19115."
        self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        self._add_walking_time()  # also when every departure left is sooner than the walking time
        self._next_departure = None

    async def async_will_remove_from_hass(self):
        """Cancel any scheduled listener when removing."""
        self._cancel_scheduled_update()
        await super().async_will_remove_from_hass()
        
    async def async_added_to_hass(self):
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._update_from_coordinator()
        
    @property
    def available(self):
        """Return if entity is available."""
        return bool(self.coordinator) and self.coordinator.is_usable(dt_util.utcnow())

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Coordinator update received for %s", self.entity_id)
        self._update_from_coordinator()


class ZTMLastUpdateSensor(CoordinatorEntity, SensorEntity):
    """Sensor to expose the last successful update time from coordinator."""

    def __init__(self, coordinator, line, stop_id, stop_number):
        """The diagnostic sensor of a stop (disabled by default): when its timetable was last fetched."""
        super().__init__(coordinator)
        self._attr_entity_registry_enabled_default = False
        self._line = line
        self._stop_id = stop_id
        self._stop_number = stop_number
        
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_number}_last_update"
        self._attr_name = f"Line {line} from {stop_id}/{stop_number} Last update"
        self._attr_translation_key = "last_update"  # its icon is in icons.json

    def _get_stop_info(self):
        """The stop's record from the coordinator (its name, position, street ...) for the attributes and the entity name; an empty dict until the City has given it."""
        return _stop_info_of(self.coordinator)

    @property
    def native_value(self):
        """Return last update time."""
        if not self.coordinator:
            return None
        
        last_update = getattr(self.coordinator, "last_update_success_time", None)
        return last_update if isinstance(last_update, datetime) else None

    @property
    def device_info(self):
        """Return device info for this entity."""
        return _device_info(self._line, self.coordinator)

    @property
    def extra_state_attributes(self):
        """Return extra attributes for diagnostics."""
        if not self.coordinator:
            return {}

        departures_count = 0
        if self.coordinator.data and hasattr(self.coordinator.data, 'departures'):
            departures_count = len(self.coordinator.data.departures or [])

        return {
            "Last update successful": getattr(self.coordinator, 'last_update_success', False),
            "Number of fetched departures": departures_count,
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    @callback
    def _handle_coordinator_update(self):
        """Update friendly name with stop name when coordinator data arrives."""
        stop_info = self._get_stop_info()
        stop_name = stop_info.get("nazwa_zespolu")
        if stop_name:
            new_name = f"Line {self._line} {stop_name} {self._stop_number} Last update"
            if self._attr_name != new_name:
                self._attr_name = new_name
        self.async_write_ha_state()


class ZTMNextDepartureSensor(CoordinatorEntity, SensorEntity):
    """One of the departures after the next one (Next 1 to Next 3) as a sensor of its own, disabled by default.

    The main sensor of the stop lists them as attributes; as entities they have a history, a card and a trigger of their own
    without a template. Like the main sensor they count only the departures that can still be caught (the walking time of
    the stop is taken off), and they wake up when the first of those can no longer be caught, because every one moves up then.
    """

    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, line, stop_id, stop_number, position):
        """The ``position``-th departure after the next one (1 to 3) of a line at a pole, named and identified by the numbers."""
        super().__init__(coordinator)
        self._line = line
        self._stop_number = stop_number
        self._position = position
        self._departure = None
        self._scheduled_unsub = None
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_number}_next_{position}"
        self._attr_name = f"Line {line} from {stop_id}/{stop_number} Next {position}"
        self._attr_translation_key = f"next_{position}"  # its icon is in icons.json

    @property
    def native_value(self):
        """The moment this departure leaves, or None when there are not that many departures left to catch."""
        return self._departure.dt if self._departure else None

    @property
    def available(self):
        """Available as the main sensor of the stop is: while the coordinator holds a timetable that may be shown."""
        return bool(self.coordinator) and self.coordinator.is_usable(dt_util.utcnow())

    @property
    def device_info(self):
        """The device of the stop, as the other entities of the stop have it."""
        return _device_info(self._line, self.coordinator)

    @property
    def extra_state_attributes(self):
        """The headsign, the day, the route and the brigade of the departure (nothing without one)."""
        if self._departure is None:
            return {ATTR_ATTRIBUTION: CONF_ATTRIBUTION}
        attrs = _departure_attrs("", self._departure, _friendly_day(self._departure.dt, dt_util.utcnow()))
        attrs = {name.removeprefix(", "): value for name, value in attrs.items()}  # "Headsign", "Departure Day" ...
        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        return attrs

    def _refresh(self):
        """Pick this entity's departure among those that can be caught, and wake up when they move up."""
        now = dt_util.utcnow()
        walk = timedelta(minutes=self.coordinator.walking_minutes)
        catchable = self.coordinator.upcoming(now + walk)
        self._departure = catchable[self._position] if len(catchable) > self._position else None
        self._cancel_wakeup()
        if catchable:
            wake = min(catchable[0].dt - walk, next_warsaw_midnight(now))  # midnight changes the label of the day
            self._scheduled_unsub = async_track_point_in_time(self.hass, self._wake_up, wake)

    def _cancel_wakeup(self):
        """Forget the wake-up that is scheduled, if any."""
        if self._scheduled_unsub:
            self._scheduled_unsub()
            self._scheduled_unsub = None

    @callback
    def _wake_up(self, _now):
        """A departure can no longer be caught, or it is midnight: show what moved up."""
        self._scheduled_unsub = None
        self._refresh()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Pick the departure and take the stop's name when the sensor is added."""
        await super().async_added_to_hass()
        self._take_stop_name()
        self._refresh()

    async def async_will_remove_from_hass(self):
        """Cancel the wake-up when the sensor goes."""
        self._cancel_wakeup()
        await super().async_will_remove_from_hass()

    def _take_stop_name(self):
        """Put the stop's name into the entity's name once it is known (the entity ID was made from the numbers)."""
        stop_name = _stop_info_of(self.coordinator).get("nazwa_zespolu")
        if stop_name:
            self._attr_name = f"Line {self._line} {stop_name} {self._stop_number} Next {self._position}"

    @callback
    def _handle_coordinator_update(self):
        """A new answer: take the stop's name once it is known, pick the departure again and write the state."""
        self._take_stop_name()
        self._refresh()
        self.async_write_ha_state()


# Home Assistant awaits this function with these three arguments, so it has to be a coroutine function that takes all three.
async def async_setup_entry(hass, config_entry, async_add_entities):  # NOSONAR
    """Set up the ZTM sensors of a config entry: two for every stop it runs."""
    try:
        for subentry_id, runtime in runtimes(config_entry).items():
            coordinator: ZTMStopCoordinator = runtime["coordinator"]
            stop_id, stop_number, line = coordinator.stop_id, coordinator.stop_nr, coordinator.line

            entity = ZTMSensor(
                coordinator=coordinator,
                entry_id=subentry_id or config_entry.entry_id,
                stop_id=stop_id,
                stop_number=stop_number,
                line=line,
                max_departures=NEXT_DEPARTURES,
            )
            diag_sensor = ZTMLastUpdateSensor(
                coordinator=coordinator,
                line=line,
                stop_id=stop_id,
                stop_number=stop_number,
            )
            following = [
                ZTMNextDepartureSensor(coordinator, line, stop_id, stop_number, position)
                for position in range(1, NEXT_DEPARTURES + 1)
            ]
            async_add_entities([entity, diag_sensor, *following], config_subentry_id=subentry_id)

            _LOGGER.info("Successfully set up ZTM sensors for line %s at stop %s/%s", line, stop_id, stop_number)

    except Exception:
        _LOGGER.exception("Failed to set up ZTM sensor")
        raise
