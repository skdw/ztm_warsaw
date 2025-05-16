import logging
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from .utils import get_line_type, get_line_icon


from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.core import callback

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import EntityCategory

from .client import ZTMStopClient
from .const import CONF_DEPARTURES, DOMAIN, CONF_ATTRIBUTION
from .coordinator import ZTMStopCoordinator

_LOGGER = logging.getLogger(__name__)

def _friendly_day(dt):
    """Helper to show friendly day names relative to today."""
    today = datetime.now(tz=timezone.utc).astimezone().date()
    dt_date = dt.astimezone().date()
    
    if dt_date == today:
        return "today"
    if dt_date == (today + timedelta(days=1)):
        return "tomorrow"
    if dt_date == (today - timedelta(days=1)):
        return "yesterday"
    return dt.strftime("%a")  # Mon, Tue ...


class ZTMSensor(CoordinatorEntity, SensorEntity):
    """Sensor for tracking ZTM departures."""
    
    def __init__(self, coordinator, entry_id, stop_id, stop_number, line, max_departures):
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._line = line
        self._stop_id = stop_id
        self._stop_number = stop_number
        self._max_departures = max_departures
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_number}"
        
        # Get stop name from coordinator if available
        stop_info = getattr(coordinator.data, "stop_info", {}) or {}
        stop_name = stop_info.get("nazwa_zespolu") if stop_info else None
        if stop_name:
            self._attr_name = f"Line {line} {stop_name} {stop_number}"
        else:
            self._attr_name = f"Line {line} from {stop_id}/{stop_number}"
        
        # Set entity_id explicitly
        self.entity_id = f"sensor.line_{line}_from_{stop_id}_{stop_number}"
        
        # Base attributes that don't change
        self._base_attrs = {
            "Line, Number": self._line,
            "Line, Type": get_line_type(self._line),
            "Line, Timezone": "Europe/Warsaw",
            "Line, Full timetable": f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_md=3&wtp_ln={quote(str(self._line))}",
            "Stop, ID": self._stop_id,
            "Stop, Number": self._stop_number,
        }
        
        # Attribute placeholders for no service
        self._no_service_attrs = {
            "Upcoming, Headsign": "No service",
            "Upcoming, Departure day": "Not available",
            "Upcoming, Route ID": "Not available",
            "Upcoming, Brigade": "Not available",
        }
        
        # Initialize attributes
        self._attributes = {}
        self._next_departure = None
        # Store previous value to avoid duplicate state reports
        self._previous_departure = None
        self._scheduled_unsub = None

    def _timetable_url(self):
        today_str = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
        return f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt={today_str}&wtp_md=3&wtp_ln={quote(str(self._line))}"

    @property
    def native_value(self):
        """Return the next departure as a timezone‑aware datetime (or None)."""
        return self._next_departure

    @property
    def icon(self):
        """Return appropriate icon based on transport type."""
        return get_line_icon(self._line)

    @property
    def extra_state_attributes(self):
        """Return attributes, excluding any None values to satisfy recorder."""
        return {k: v for k, v in self._attributes.items() if v is not None}

    @property
    def device_info(self):
        """Return device info for this entity."""
        stop_info = getattr(self.coordinator.data, "stop_info", {}) or {}
        return {
            "identifiers": {(DOMAIN, f"line_{self._line}")},
            "name": f"Line {self._line}",
            "manufacturer": "Zarząd Transportu Miejskiego",
            "entry_type": "service",
            "model": get_line_type(self._line),
            "sw_version": stop_info.get("obowiazuje_od"),
            "configuration_url": self._timetable_url(),
        }

    def _update_from_coordinator(self):
        """Update state and attributes based on coordinator data."""
        from homeassistant.util.dt import now as ha_utcnow
        data = self.coordinator.data
        if data is None:
            _LOGGER.warning("No timetable data available from coordinator")
            self._set_no_departures()
            self.async_write_ha_state()
            return

        # Get stop information
        stop_info = getattr(data, "stop_info", {}) or {}

        # Start with base attributes
        self._attributes = dict(self._base_attrs)
        self._attributes["Stop, Name"] = stop_info.get("nazwa_zespolu", "Not available")
        self._attributes["Stop, Street ID"] = stop_info.get("id_ulicy", "Not available")
        self._attributes["Stop, Latitude"] = stop_info.get("szer_geo", "Not available")
        self._attributes["Stop, Longitude"] = stop_info.get("dlug_geo", "Not available")
        self._attributes["Stop, Direction"] = stop_info.get("kierunek", "Not available")
        self._attributes["Stop, Effective from"] = stop_info.get("obowiazuje_od", "Not available")
        self._attributes["Stop, Timezone"] = "Europe/Warsaw"
        self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION

        from homeassistant.util.dt import now as ha_utcnow
        now_warsaw = ha_utcnow().astimezone()
        departures = sorted(
            [d for d in data.departures if d.dt],
            key=lambda d: d.dt
        )

        # Find first future departure (dt >= now_warsaw)
        future_departures = [d for d in departures if d.dt and d.dt >= now_warsaw]

        if not future_departures:
            self._set_no_departures()
            self.async_write_ha_state()
            return
        
        new_departure = future_departures[0].dt

        # Always update _next_departure with the next scheduled departure
        self._previous_departure = self._next_departure
        self._next_departure = new_departure

        # Add information about current departure
        current = future_departures[0]
        self._attributes["Upcoming, Headsign"] = current.kierunek
        self._attributes["Upcoming, Departure day"] = _friendly_day(current.dt)
        self._attributes["Upcoming, Route ID"] = current.trasa
        self._attributes["Upcoming, Brigade"] = current.brygada

        # Add information about next departures
        for seq, dep in enumerate(future_departures[1:self._max_departures + 1], start=1):
            local_dt = dep.dt.astimezone(now_warsaw.tzinfo)
            time_str = local_dt.strftime("%H:%M")
            self._attributes[f"Next {seq}, Headsign"] = dep.kierunek
            self._attributes[f"Next {seq}, Departure day"] = _friendly_day(local_dt)
            self._attributes[f"Next {seq}, Departure time"] = time_str
            self._attributes[f"Next {seq}, Route ID"] = dep.trasa
            self._attributes[f"Next {seq}, Brigade"] = dep.brygada

        # Schedule update at the next departure time
        if self._scheduled_unsub:
            self._scheduled_unsub()
        self._scheduled_unsub = async_track_point_in_time(
            self.hass, self._scheduled_update, new_departure
        )
        # Notify Home Assistant of state change
        self.async_write_ha_state()

    @callback
    def _scheduled_update(self, now):
        """Callback triggered at scheduled departure time to refresh state."""
        self._update_from_coordinator()


    def _set_no_departures(self):
        """Set attributes for no departures case."""
        # Cancel any scheduled update
        if self._scheduled_unsub:
            self._scheduled_unsub()
            self._scheduled_unsub = None

        # Start with base attributes
        self._attributes = dict(self._base_attrs)
        
        # Use timetable url helper
        self._attributes["Line, Full timetable"] = self._timetable_url()
        
        # Add stop info if available
        stop_info = getattr(self.coordinator.data, "stop_info", {}) or {}
        if stop_info:
            self._attributes["Stop, Name"] = stop_info.get("nazwa_zespolu")
            self._attributes["Stop, Street ID"] = stop_info.get("id_ulicy")
            self._attributes["Stop, Latitude"] = stop_info.get("szer_geo")
            self._attributes["Stop, Longitude"] = stop_info.get("dlug_geo")
            self._attributes["Stop, Direction"] = stop_info.get("kierunek")
            self._attributes["Stop, Effective from"] = stop_info.get("obowiazuje_od")
        else:
            self._attributes["Stop, Name"] = "Not available"
            self._attributes["Stop, Street ID"] = "Not available"
            self._attributes["Stop, Latitude"] = "Not available"
            self._attributes["Stop, Longitude"] = "Not available"
            self._attributes["Stop, Direction"] = "Not available"
            self._attributes["Stop, Effective from"] = "Not available"
            
        # Set timezone and no service attributes
        self._attributes["Stop, Timezone"] = "Europe/Warsaw"
        self._attributes.update(self._no_service_attrs)
        
        # Set next departure attributes to no service
        for seq in range(1, self._max_departures + 1):
            self._attributes[f"Next {seq}, Headsign"] = "No service"
            self._attributes[f"Next {seq}, Departure day"] = "Not available"
            self._attributes[f"Next {seq}, Departure time"] = "Not available"
            self._attributes[f"Next {seq}, Route ID"] = "Not available"
            self._attributes[f"Next {seq}, Brigade"] = "Not available"
            
        # Set note and attribution
        self._attributes["note"] = "No upcoming schedule available. Please verify on wtp.waw.pl or call 19115."
        self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        
        # Check if state changed - only update if it did (from valid time to None)
        if self._next_departure is not None:
            self._previous_departure = None
            self._next_departure = None

    async def async_will_remove_from_hass(self):
        """Cancel any scheduled listener when removing."""
        if self._scheduled_unsub:
            self._scheduled_unsub()
            self._scheduled_unsub = None
        
    async def async_added_to_hass(self):
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._update_from_coordinator()
        
    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success
        
    async def async_update(self):
        """Update using coordinator data."""
        self._update_from_coordinator()


class ZTMLastUpdateSensor(CoordinatorEntity, SensorEntity):
    """Sensor to expose the last successful update time from coordinator."""

    def __init__(self, coordinator, line, stop_id, stop_number):
        super().__init__(coordinator)
        self._attr_entity_registry_enabled_default = False
        self._line = line
        self._stop_id = stop_id
        self._stop_number = stop_number
        
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_number}_last_update"
        
        # Set friendly name
        stop_info = getattr(coordinator.data, "stop_info", {}) or {}
        stop_name = stop_info.get('nazwa_zespolu') if stop_info else stop_id
        self._attr_name = f"Line {line} {stop_name} {stop_number} Last update"
        
        # Set entity_id
        self.entity_id = f"sensor.line_{line}_from_{stop_id}_{stop_number}_last_update"

    @property
    def native_value(self):
        """Return last update time."""
        return self.coordinator.last_update_success_time if isinstance(
            getattr(self.coordinator, "last_update_success_time", None), datetime
        ) else None

    def _timetable_url(self):
        today_str = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
        return f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt={today_str}&wtp_md=3&wtp_ln={quote(str(self._line))}"

    @property
    def device_info(self):
        """Return device info for this entity."""
        stop_info = getattr(self.coordinator.data, "stop_info", {}) or {}
        return {
            "identifiers": {(DOMAIN, f"line_{self._line}")},
            "name": f"Line {self._line}",
            "manufacturer": "Zarząd Transportu Miejskiego",
            "entry_type": "service",
            "model": get_line_type(self._line),
            "configuration_url": self._timetable_url(),
        }

    @property
    def extra_state_attributes(self):
        """Return extra attributes for diagnostics."""
        stop_info = getattr(self.coordinator.data, "stop_info", {}) or {}
        return {
            "Last update successful": self.coordinator.last_update_success,
            "Number of fetched departures": len(self.coordinator.data.departures) if self.coordinator.data and getattr(self.coordinator.data, "departures", None) else 0,
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up ZTM sensor from a config entry."""
    # Read configuration and options
    data = config_entry.data
    options = config_entry.options

    stop_id = str(data["busstop_id"])
    stop_number = str(data["busstop_nr"])
    line = data["line"]
    # Use departures option if set, else fallback to initial data
    departures = options.get(CONF_DEPARTURES, data.get(CONF_DEPARTURES, 1))

    # Create session and client
    session = async_get_clientsession(hass)
    client = ZTMStopClient(
        session=session,
        api_key=data["api_key"],
        stop_id=stop_id,
        stop_number=stop_number,
        line=line,
    )
    
    # Create coordinator
    coordinator = ZTMStopCoordinator(
        hass=hass,
        client=client,
        stop_id=stop_id,
        stop_nr=stop_number,
        line=line,
    )
    
    # Initialize coordinator
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    # Create entities
    entity = ZTMSensor(
        coordinator=coordinator,
        entry_id=config_entry.entry_id,
        stop_id=stop_id,
        stop_number=stop_number,
        line=line,
        max_departures=departures,
    )

    diag_sensor = ZTMLastUpdateSensor(
        coordinator=coordinator,
        line=line,
        stop_id=stop_id,
        stop_number=stop_number,
    )

    stop_info = coordinator.data.stop_info or {}
    entities = [entity, diag_sensor]

    # Add entities
    async_add_entities(entities)