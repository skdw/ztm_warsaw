"""The sensors of a stop: the next departures of the line at the pole, and a diagnostic sensor for the last refresh.

The state of ``ZTMSensor`` is the next departure (a timestamp), the attributes list the three after it and the stop
(its name, position, direction ...). A sensor wakes up at the next departure instead of polling, and writes its
state only when it changed. The names of the attributes are part of the public contract of the integration.
"""

import logging
from typing import Any
from datetime import datetime, timedelta
from urllib.parse import quote
from homeassistant.util import dt as dt_util
from homeassistant.util.dt import as_local

from .utils import get_line_badge, get_line_icon, get_line_type

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.const import EntityCategory

from .const import CONF_ATTRIBUTION, CONF_SHOW_VEHICLES, DOMAIN, NEXT_DEPARTURES
from .coordinator import ZTMStopCoordinator
from .entries import runtimes
from .entity import ZtmStopEntity, timetable_url as _timetable_url
from .runtime import ZtmConfigEntry
from .vehicle_sensor import ZTMVehicleDistanceSensor
from .vehicles import feed_for
from .models import ZTMDepartureDataReading, WARSAW, in_swap_window, next_swap_boundary, next_warsaw_midnight

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # the entities only read what their coordinator fetched: nothing to limit

def _friendly_day(dt: datetime, now: datetime) -> str:
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


def _stop_attributes(stop_info: dict[str, Any]) -> dict[str, Any]:
    """The attributes that describe the stop. They carry no ``latitude`` and ``longitude`` on purpose: a sensor with a position is a pin on the map,
    and a stop pole served by several lines would then be drawn once for each (the pole is one pin of the map layer, ``geo_location.py``)."""
    return {name: stop_info.get(key, NOT_AVAILABLE) for name, key in _STOP_ATTRIBUTES.items()}


def _departure_attrs(label: str, dep: ZTMDepartureDataReading, day: str, time_str: str | None = None) -> dict[str, Any]:
    """The attributes of one departure under ``label`` ("Upcoming" or "Next 1" ...)."""
    attrs = {f"{label}, Headsign": getattr(dep, "kierunek", NOT_AVAILABLE), f"{label}, Departure Day": day}
    if time_str is not None:
        attrs[f"{label}, Departure Time"] = time_str
    attrs[f"{label}, Route ID"] = getattr(dep, "trasa", NOT_AVAILABLE)
    attrs[f"{label}, Brigade"] = getattr(dep, "brygada", NOT_AVAILABLE)
    return attrs


class ZTMSensor(ZtmStopEntity, SensorEntity):
    """Sensor for tracking ZTM departures."""
    
    def __init__(self, coordinator: ZTMStopCoordinator, entry_id: str, stop_id: str, stop_number: str, line: str, max_departures: int) -> None:
        """Name the sensor after its line and pole (the stop's name replaces the numbers later, once the entity ID is fixed) and fix its unique ID."""
        super().__init__(coordinator, line, stop_number)
        self._entry_id = entry_id
        self._stop_id = stop_id
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
        self._attributes: dict[str, Any] = {}
        self._next_departure: datetime | None = None
        self._scheduled_unsub: CALLBACK_TYPE | None = None
        self._last_coordinator_update: datetime | None = None
        self._written_available: bool | None = None
        self._written_attributes: dict[str, Any] | None = None

    def _get_stop_info(self) -> dict[str, Any]:
        """The stop's record from the coordinator (see ``ZtmStopEntity``)."""
        return self._stop_info()

    @property
    def native_value(self) -> datetime | None:
        """Return the next departure as a timezone‑aware datetime (or None)."""
        return self._next_departure

    @property
    def icon(self) -> str:
        """Return appropriate icon based on transport type."""
        return get_line_icon(self._line)

    @property
    def entity_picture(self) -> str | None:
        """A badge with the line number: the map card draws it as the pin instead of the initials of the name."""
        return get_line_badge(self._line)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes, excluding any None values to satisfy recorder."""
        attributes = {**(self._attributes or {}), **self._timetable_span()}
        return {k: v for k, v in attributes.items() if v is not None}

    def _timetable_span(self) -> dict[str, str]:
        """The first and the last departure of the timetable the City gave (the whole service day, the past ones too), as Warsaw
        times (as the timetable and the other times of the sensor are, whatever zone Home Assistant has): with them a card can say "the last bus left at 23:41" when the sensor has no next departure. Nothing without a timetable."""
        data = self.coordinator.data if self.coordinator else None
        times = [d.dt for d in getattr(data, "departures", None) or [] if getattr(d, "dt", None)]
        if not times:
            return {}
        return {
            "Timetable, First Departure": min(times).astimezone(WARSAW).strftime("%H:%M"),
            "Timetable, Last Departure": max(times).astimezone(WARSAW).strftime("%H:%M"),
        }

    def _cancel_scheduled_update(self) -> None:
        """Cancel any scheduled update."""
        if self._scheduled_unsub:
            self._scheduled_unsub()
            self._scheduled_unsub = None

    def _schedule_wakeup(self, departure_time: datetime, now: datetime) -> None:
        """Wake up at the next departure, or at midnight in Warsaw if that comes first: the labels 'today' and
        'tomorrow' change then, and nothing else would tell the sensor."""
        wake = min(departure_time, next_warsaw_midnight(now))
        try:
            self._cancel_scheduled_update()
            self._scheduled_unsub = async_track_point_in_time(self.hass, self._scheduled_update, wake)
            _LOGGER.debug("Scheduled update for %s at %s", self.entity_id, as_local(wake))
        except Exception:
            _LOGGER.exception("Failed to schedule update for %s", self.entity_id)

    def _update_from_coordinator(self) -> None:
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

    def _apply_coordinator_data(self, has_new_data: bool) -> None:
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
        self._schedule_wakeup(future_departures[0].moment - walk, now)  # it cannot be caught any more `walk` before it leaves

    def _add_walking_time(self) -> None:
        """Show the walking time of the stop in the attributes, when one is set (a sensor without one has no such attribute)."""
        if self.coordinator.walking_minutes:
            self._attributes["Walking time, Minutes"] = self.coordinator.walking_minutes

    def _update_stop_name(self) -> None:
        """Update friendly name if stop info is now available."""
        stop_info = self._get_stop_info()
        stop_name = stop_info.get("nazwa_zespolu")
        if stop_name:
            new_name = f"Line {self._line} {stop_name} {self._stop_number}"
            if self._attr_name != new_name:
                _LOGGER.info("Updating friendly name for %s to: %s", self.entity_id, new_name)
                self._attr_name = new_name

    def _update_departure_info(self, future_departures: list[ZTMDepartureDataReading], now: datetime) -> None:
        """Update departure information and attributes."""
        current = future_departures[0]
        self._next_departure = current.moment
        _LOGGER.info("Next departure for %s: %s → %s", self.entity_id, as_local(current.moment), current.kierunek)

        self._attributes = dict(self._base_attrs)
        self._attributes.update(_stop_attributes(self._get_stop_info()))
        self._attributes["Stop, Timezone"] = TIMEZONE
        self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        self._add_walking_time()
        self._attributes.update(_departure_attrs("Upcoming", current, _friendly_day(current.moment, now)))

        # Add information about next departures
        for seq, dep in enumerate(future_departures[1:self._max_departures + 1], start=1):
            try:
                local_dt = dep.moment.astimezone(WARSAW)
                self._attributes.update(
                    _departure_attrs(f"Next {seq}", dep, _friendly_day(dep.moment, now), local_dt.strftime("%H:%M"))
                )
            except Exception as e:
                _LOGGER.warning("Failed to process departure %d for %s: %s", seq, self.entity_id, e)

    @callback
    def _scheduled_update(self, now: datetime) -> None:
        """Callback triggered at scheduled departure time to refresh state."""
        _LOGGER.info("Scheduled update triggered for %s at departure time (%s)", self.entity_id, as_local(now))
        self._update_from_coordinator()

    def _set_no_departures(self) -> None:
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

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any scheduled listener when removing."""
        self._cancel_scheduled_update()
        await super().async_will_remove_from_hass()
        
    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._update_from_coordinator()
        
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return bool(self.coordinator) and self.coordinator.is_usable(dt_util.utcnow())

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Coordinator update received for %s", self.entity_id)
        self._update_from_coordinator()


class ZTMLastUpdateSensor(ZtmStopEntity, SensorEntity):
    """Sensor to expose the last successful update time from coordinator."""

    def __init__(self, coordinator: ZTMStopCoordinator, line: str, stop_id: str, stop_number: str) -> None:
        """The diagnostic sensor of a stop (disabled by default): when its timetable was last fetched."""
        super().__init__(coordinator, line, stop_number)
        self._attr_entity_registry_enabled_default = False
        self._stop_id = stop_id
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_number}_last_update"
        self._attr_name = f"Line {line} from {stop_id}/{stop_number} Last update"
        self._attr_translation_key = "last_update"  # its icon is in icons.json

    @property
    def native_value(self) -> datetime | None:
        """Return last update time."""
        if not self.coordinator:
            return None
        
        last_update = getattr(self.coordinator, "last_update_success_time", None)
        return last_update if isinstance(last_update, datetime) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
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
    def _handle_coordinator_update(self) -> None:
        """Update friendly name with stop name when coordinator data arrives."""
        name = self._name_with_stop("Last update")
        if name:
            self._attr_name = name
        self.async_write_ha_state()


class ZTMNextDepartureSensor(ZtmStopEntity, SensorEntity):
    """One of the departures after the next one (Next 1 to Next 3) as a sensor of its own, disabled by default.

    The main sensor of the stop lists them as attributes; as entities they have a history, a card and a trigger of their own
    without a template. Like the main sensor they count only the departures that can still be caught (the walking time of
    the stop is taken off), and they wake up when the first of those can no longer be caught, because every one moves up then.
    """

    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: ZTMStopCoordinator, line: str, stop_id: str, stop_number: str, position: int) -> None:
        """The ``position``-th departure after the next one (1 to 3) of a line at a pole, named and identified by the numbers."""
        super().__init__(coordinator, line, stop_number)
        self._position = position
        self._departure: ZTMDepartureDataReading | None = None
        self._scheduled_unsub: CALLBACK_TYPE | None = None
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_number}_next_{position}"
        self._attr_name = f"Line {line} from {stop_id}/{stop_number} Next {position}"
        self._attr_translation_key = f"next_{position}"  # its icon is in icons.json

    @property
    def native_value(self) -> datetime | None:
        """The moment this departure leaves, or None when there are not that many departures left to catch."""
        return self._departure.dt if self._departure else None

    @property
    def available(self) -> bool:
        """Available as the main sensor of the stop is: while the coordinator holds a timetable that may be shown."""
        return bool(self.coordinator) and self.coordinator.is_usable(dt_util.utcnow())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The headsign, the day, the route and the brigade of the departure (nothing without one)."""
        if self._departure is None:
            return {ATTR_ATTRIBUTION: CONF_ATTRIBUTION}
        attrs = _departure_attrs("", self._departure, _friendly_day(self._departure.moment, dt_util.utcnow()))
        attrs = {name.removeprefix(", "): value for name, value in attrs.items()}  # "Headsign", "Departure Day" ...
        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        return attrs

    def _refresh(self) -> None:
        """Pick this entity's departure among those that can be caught, and wake up when they move up."""
        now = dt_util.utcnow()
        walk = timedelta(minutes=self.coordinator.walking_minutes)
        catchable = self.coordinator.upcoming(now + walk)
        self._departure = catchable[self._position] if len(catchable) > self._position else None
        self._cancel_wakeup()
        if catchable:
            wake = min(catchable[0].moment - walk, next_warsaw_midnight(now))  # midnight changes the label of the day
            self._scheduled_unsub = async_track_point_in_time(self.hass, self._wake_up, wake)

    def _cancel_wakeup(self) -> None:
        """Forget the wake-up that is scheduled, if any."""
        if self._scheduled_unsub:
            self._scheduled_unsub()
            self._scheduled_unsub = None

    @callback
    def _wake_up(self, _now: datetime) -> None:
        """A departure can no longer be caught, or it is midnight: show what moved up."""
        self._scheduled_unsub = None
        self._refresh()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Pick the departure and take the stop's name when the sensor is added."""
        await super().async_added_to_hass()
        self._take_stop_name()
        self._refresh()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the wake-up when the sensor goes."""
        self._cancel_wakeup()
        await super().async_will_remove_from_hass()

    def _take_stop_name(self) -> None:
        """Put the stop's name into the entity's name once it is known (the entity ID was made from the numbers)."""
        name = self._name_with_stop(f"Next {self._position}")
        if name:
            self._attr_name = name

    @callback
    def _handle_coordinator_update(self) -> None:
        """A new answer: take the stop's name once it is known, pick the departure again and write the state."""
        self._take_stop_name()
        self._refresh()
        self.async_write_ha_state()


STATUSES = [
    "old_api",  # the key is one of the City's old API, which is gone: it has to be replaced with a token
    "running",  # there is a departure to catch
    "cannot_catch",  # departures are left, but all are sooner than the walking time
    "after_last_departure",  # the last departure of the day has gone
    "no_service_today",  # the City says the line does not run today
    "city_updating",  # the City swaps its timetables (about 02:10 to 03:05)
    "waiting",  # no timetable of today yet
    "city_error",  # the City answered, but not with a timetable (a rejected key, an unknown stop or line)
]


class ZTMStatusSensor(ZtmStopEntity, SensorEntity):
    """What is going on with a stop, in words (translated): the state of the main sensor says only "unknown" after the last
    departure, and a person needs to know whether the bus has gone, the line does not run today or the City did not answer.
    It is available also when the timetable is not, because explaining that is its job."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    def __init__(self, coordinator: ZTMStopCoordinator, line: str, stop_id: str, stop_number: str) -> None:
        """The status of a line at a pole, named and identified by the numbers like the other entities of the stop."""
        super().__init__(coordinator, line, stop_number)
        self._status = "waiting"
        self._scheduled_unsub: CALLBACK_TYPE | None = None
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_number}_status"
        self._attr_name = f"Line {line} from {stop_id}/{stop_number} Status"
        self._attr_translation_key = "status"  # its name, the texts of its states and its icons are in the translations

    @property
    def native_value(self) -> str:
        """One of ``STATUSES``."""
        return self._status

    @property
    def available(self) -> bool:
        """Always: it is the one entity that says why the others have nothing to show."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The attribution only."""
        return {ATTR_ATTRIBUTION: CONF_ATTRIBUTION}

    def _compute(self, now: datetime) -> str:
        """The status at ``now`` from what the coordinator holds."""
        coordinator = self.coordinator
        if coordinator.client.retired:
            return "old_api"
        if coordinator.api_error:
            return "city_error"
        walk = timedelta(minutes=coordinator.walking_minutes)
        if coordinator.upcoming(now + walk):
            return "running"
        if coordinator.upcoming(now):
            return "cannot_catch"
        if in_swap_window(now):
            return "city_updating"
        data = coordinator.data
        if data is None or not coordinator.is_fresh(now):
            return "waiting"
        if not [d for d in data.departures if d.dt]:
            return "no_service_today"
        return "after_last_departure"

    def _refresh(self) -> None:
        """Work out the status and wake up at the next moment it can change: a departure that can no longer be caught, or one that
        leaves, or the start or the end of the City's update of its timetables (when *the City is updating* is shown)."""
        now = dt_util.utcnow()
        self._status = self._compute(now)
        self._cancel_wakeup()
        walk = timedelta(minutes=self.coordinator.walking_minutes)
        moments = [d.moment - walk for d in self.coordinator.upcoming(now + walk)] + [d.moment for d in self.coordinator.upcoming(now)]
        moments = [m for m in moments if m > now] + [next_swap_boundary(now)]
        if moments:
            self._scheduled_unsub = async_track_point_in_time(self.hass, self._wake_up, min(moments))

    def _cancel_wakeup(self) -> None:
        """Forget the wake-up that is scheduled, if any."""
        if self._scheduled_unsub:
            self._scheduled_unsub()
            self._scheduled_unsub = None

    @callback
    def _wake_up(self, _now: datetime) -> None:
        """A departure can no longer be caught or has left: say what the status is now."""
        self._scheduled_unsub = None
        self._refresh()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Work out the status when the sensor is added."""
        await super().async_added_to_hass()
        self._take_stop_name()
        self._refresh()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the wake-up when the sensor goes."""
        self._cancel_wakeup()
        await super().async_will_remove_from_hass()

    def _take_stop_name(self) -> None:
        """Put the stop's name into the entity's name once it is known (the entity ID was made from the numbers)."""
        name = self._name_with_stop("Status")
        if name:
            self._attr_name = name

    @callback
    def _handle_coordinator_update(self) -> None:
        """A new answer: take the stop's name, work out the status again and write the state."""
        self._take_stop_name()
        self._refresh()
        self.async_write_ha_state()


# Home Assistant awaits this function with these three arguments, so it has to be a coroutine function that takes all three.
def _remove_distance_sensors(hass: HomeAssistant, config_entry: ZtmConfigEntry) -> None:
    """Take the distance sensors of the entry out of the registry: the line does not show its vehicles (any more)."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, config_entry.entry_id):
        if entity.domain == "sensor" and entity.platform == DOMAIN and entity.unique_id.endswith("_vehicle_distance"):
            registry.async_remove(entity.entity_id)


async def async_setup_entry(hass: HomeAssistant, config_entry: ZtmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:  # NOSONAR
    """Set up the ZTM sensors of a config entry: those of every stop it runs, and with a token and *Show the vehicles of this line on the
    map* ticked, the distance of the vehicle of the next departure of each stop (a line that does not show its vehicles has none)."""
    shows_vehicles = bool(config_entry.options.get(CONF_SHOW_VEHICLES, False))
    if not shows_vehicles:
        _remove_distance_sensors(hass, config_entry)
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
            status = ZTMStatusSensor(coordinator, line, stop_id, stop_number)
            client = runtime["client"]
            distance = [ZTMVehicleDistanceSensor(coordinator, feed_for(hass, client))] if client.uses_token and shows_vehicles else []
            async_add_entities([entity, status, diag_sensor, *following, *distance], config_subentry_id=subentry_id)

            _LOGGER.info("Successfully set up ZTM sensors for line %s at stop %s/%s", line, stop_id, stop_number)

    except Exception:
        _LOGGER.exception("Failed to set up ZTM sensor")
        raise
