import logging
import re
import string
from datetime import datetime, timezone, timedelta

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.dt import utcnow as ha_utcnow

from .client import ZTMStopClient
from .const import CONF_DEPARTURES, DOMAIN, CONF_ATTRIBUTION
from .models import ZTMDepartureDataReading
from .coordinator import ZTMStopCoordinator

_LOGGER = logging.getLogger(__name__)

LINE_TYPE_MAP = {
    # Buses - types based on Warsaw public transport conventions
    "1": "Normal bus",
    "2": "Normal bus",
    "3": "Normal periodic bus",
    "4": "Fast periodic bus",
    "5": "Fast bus",
    "6": "Unknown bus",
    "7": "Zone normal bus",
    "8": "Zone periodic bus",
    "9": "Special bus",
    "C": "Cemetery bus",  # Bus serving cemetery routes
    "E": "Express periodic bus",
    "L": "Local suburban bus",
    "N": "Night bus",
    "Z": "Replacement line",  # Temporary replacement line
    "T": "Tram line",
    "M": "Metro line",
    "S": "Urban rail",  # SKM urban rail lines
}

def _line_type(line: str) -> str:
    """Return human‑friendly type of a Warsaw transport line."""
    # Tram: purely numeric 1‑ or 2‑digit (1‑99)
    if re.fullmatch(r"[1-9]\d?", line):
        return "Tram line"
    # Metro: letter M + single digit (M1, M2 …)
    if re.fullmatch(r"M\d", line, re.IGNORECASE):
        return "Metro line"
    # Urban rail (SKM): S followed by 1‑2 digits (S1 … S20)
    if re.fullmatch(r"S\d{1,2}", line, re.IGNORECASE):
        return "Urban rail"
    # Otherwise treat as bus type based on first character
    first = line[0].upper()
    return LINE_TYPE_MAP.get(first, "unknown")


class ZTMSensor(SensorEntity):
    def __init__(self, hass, entry_id, stop_id, stop_number, line, name, max_departures, coordinator):
        self._entry_id = entry_id
        self._line = line
        self._stop_id = stop_id
        self._stop_number = stop_number
        self._name = name
        self._attributes = {}
        self._max_departures = max_departures
        self._coordinator = coordinator
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._next_departure = None
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_number}"

        # Explicitly set friendly name
        stop_name = coordinator.data.stop_info.get("nazwa_zespolu") if coordinator.data and coordinator.data.stop_info else None
        if stop_name:
            self._attr_name = f"Line {line} {stop_name} {stop_number}"
        else:
            self._attr_name = f"Line {line} from {stop_id}/{stop_number}"

        # Force entity_id only if entity does not already exist in registry
        if not hasattr(self, 'entity_id') or not self.entity_id:
            self.entity_id = f"sensor.line_{line}_from_{stop_id}_{stop_number}"

        # static line-level and stop-level attributes
        self._attributes["Line, Number"] = self._line
        self._attributes["Line, Timezone"] = "Europe/Warsaw"  # Warsaw timezone
        self._attributes["Line, Type"] = _line_type(self._line)
        self._attributes["Stop, ID"] = self._stop_id
        self._attributes["Stop, Number"] = self._stop_number

    @property
    def native_value(self):
        """Return the next departure as a timezone‑aware datetime (or None)."""
        return self._next_departure

    @property
    def icon(self):
        # Icon selection based on line format and type
        # Tram lines: numeric 1-99
        if re.fullmatch(r"[1-9]\d?", self._line):
            return "mdi:tram"
        elif re.match(r"^\d{3}$", self._line):
            return "mdi:bus"
        elif re.match(r"^N\d{2}$", self._line):
            return "mdi:bus"
        elif re.match(r"^L-?\d{1,2}$", self._line):
            return "mdi:bus"
        elif re.match(r"^S\d{1,2}$", self._line):
            return "mdi:train"
        elif re.match(r"^M\d$", self._line):
            return "mdi:train-variant"
        return "mdi:bus"

    @property
    def extra_state_attributes(self):
        """Return attributes, excluding any None values to satisfy recorder."""
        return {k: v for k, v in self._attributes.items() if v is not None}

    async def async_update(self):
        """Fetch new data from coordinator and update state + attributes."""
        _LOGGER.debug("Running async_update for %s", self._attr_unique_id)
        coordinator: ZTMStopCoordinator = self._coordinator
        data = coordinator.data
        _LOGGER.debug("Data from coordinator: %s", data)
        if data is None:
            _LOGGER.warning("No timetable data available from coordinator")
            self._next_departure = None
            self._attributes.clear()
            self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
            return

        all_departures = data.departures  # full day timetable

        departure_times = [d.dt for d in all_departures if d.dt]
        _LOGGER.debug(
            "Total valid departures for %s: %d -> %s",
            self._attr_unique_id,
            len(departure_times),
            ", ".join(dt.strftime("%H:%M") for dt in departure_times)
        )

        now = datetime.now(tz=timezone.utc)
        departures = sorted(
            [d for d in all_departures if d.dt and d.dt >= now],
            key=lambda d: d.dt
        )

        # Find the soonest departure (if any) and expose it as timestamp
        if departures:
            _LOGGER.debug("Next departure time for %s: %s", self._attr_unique_id, departures[0].dt)
        else:
            _LOGGER.debug("No departures found for %s", self._attr_unique_id)
        self._next_departure = departures[0].dt if departures else None

        # 2) No departures at all
        if not departures:
            _LOGGER.debug("Now = %s (UTC), no valid upcoming departures found", now.isoformat())
            _LOGGER.debug("All departures (pre-filter): %s", all_departures)
            self._next_departure = None
            self._attributes.clear()
            # Set attributes in specified order
            self._attributes["Line, Number"] = self._line
            self._attributes["Line, Type"] = _line_type(self._line)
            today_str = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
            self._attributes["Line, Full timetable"] = f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt={today_str}&wtp_md=3&wtp_ln={self._line}"
            if data.stop_info:
                self._attributes["Stop, Name"] = data.stop_info.get("nazwa_zespolu")  # Official stop name
            else:
                self._attributes["Stop, Name"] = None
            self._attributes["Stop, ID"] = self._stop_id
            self._attributes["Stop, Number"] = self._stop_number
            if data.stop_info:
                self._attributes["Stop, Street ID"] = data.stop_info.get("id_ulicy")  # Street ID code
                self._attributes["Stop, Latitude"] = data.stop_info.get("szer_geo")  # Latitude coordinate
                self._attributes["Stop, Longitude"] = data.stop_info.get("dlug_geo")  # Longitude coordinate
                self._attributes["Stop, Direction"] = data.stop_info.get("kierunek")  # Direction of the stop
                self._attributes["Stop, Effective from"] = data.stop_info.get("obowiazuje_od")  # Date from which info is valid
            else:
                self._attributes["Stop, Street ID"] = None
                self._attributes["Stop, Latitude"] = None
                self._attributes["Stop, Longitude"] = None
                self._attributes["Stop, Direction"] = None
                self._attributes["Stop, Effective from"] = None
            self._attributes["Stop, Timezone"] = "Europe/Warsaw"
            self._attributes["Upcoming, Headsign"] = "No service"
            self._attributes["Upcoming, Departure day"] = "Not available"
            self._attributes["Upcoming, Route ID"] = "Not available"
            self._attributes["Upcoming, Brigade"] = "Not available"
            for seq in range(1, self._max_departures + 1):
                self._attributes[f"Next {seq}, Headsign"] = "No service"
                self._attributes[f"Next {seq}, Departure day"] = "Not available"
                self._attributes[f"Next {seq}, Departure time"] = "Not available"
                self._attributes[f"Next {seq}, Route ID"] = "Not available"
                self._attributes[f"Next {seq}, Brigade"] = "Not available"
            self._attributes["note"] = "No upcoming schedule available. Please verify on wtp.waw.pl or call 19115."
            self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
            return

        # Preserve static attributes
        static_attrs = {
            k: self._attributes[k]
            for k in list(self._attributes)
            if k.startswith("Line, ")
        }
        self._attributes.clear()
        self._attributes.update(static_attrs)
        self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        # Add stop_info attributes from API if present, with specific mapping and order
        if not data.stop_info:
            _LOGGER.warning("Missing stop_info for %s. Attributes will be incomplete", self._attr_unique_id)
        # Set attributes in specified order
        self._attributes["Line, Number"] = self._line
        self._attributes["Line, Type"] = _line_type(self._line)
        today_str = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
        self._attributes["Line, Full timetable"] = f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt={today_str}&wtp_md=3&wtp_ln={self._line}"
        if data.stop_info:
            self._attributes["Stop, Name"] = data.stop_info.get("nazwa_zespolu")  # Official stop name
        else:
            self._attributes["Stop, Name"] = None
        self._attributes["Stop, ID"] = self._stop_id
        self._attributes["Stop, Number"] = self._stop_number
        if data.stop_info:
            self._attributes["Stop, Street ID"] = data.stop_info.get("id_ulicy")  # Street ID code
            self._attributes["Stop, Latitude"] = data.stop_info.get("szer_geo")  # Latitude coordinate
            self._attributes["Stop, Longitude"] = data.stop_info.get("dlug_geo")  # Longitude coordinate
            self._attributes["Stop, Direction"] = data.stop_info.get("kierunek")  # Direction of the stop
            self._attributes["Stop, Effective from"] = data.stop_info.get("obowiazuje_od")  # Date from which info is valid
        else:
            self._attributes["Stop, Street ID"] = None
            self._attributes["Stop, Latitude"] = None
            self._attributes["Stop, Longitude"] = None
            self._attributes["Stop, Direction"] = None
            self._attributes["Stop, Effective from"] = None
        self._attributes["Stop, Timezone"] = "Europe/Warsaw"

        # helper to friendly day
        today = datetime.now(tz=timezone.utc).astimezone().date()
        def friendly_day(local_dt):
            if local_dt.date() == today:
                return "today"
            if local_dt.date() == (today + timedelta(days=1)):
                return "tomorrow"
            if local_dt.date() == (today - timedelta(days=1)):
                return "yesterday"
            return local_dt.strftime("%a")  # Mon, Tue ...

        # Upcoming (current)
        current = departures[0]
        local_current = current.dt.astimezone()
        self._attributes["Upcoming, Headsign"] = current.kierunek  # Destination name
        self._attributes["Upcoming, Departure day"] = friendly_day(local_current)
        self._attributes["Upcoming, Route ID"] = current.trasa
        self._attributes["Upcoming, Brigade"] = current.brygada

        _LOGGER.debug(
            "Selected next departure for %s: %s -> %s (%s)",
            self._attr_unique_id,
            current.kierunek,
            current.dt,
            friendly_day(current.dt.astimezone())
        )

        for seq, dep in enumerate(departures[1 : self._max_departures + 1], start=1):
            local_dt = dep.dt.astimezone()  # convert to system's local tz (Europe/Warsaw)
            time_str = local_dt.strftime("%H:%M")
            self._attributes[f"Next {seq}, Headsign"] = dep.kierunek  # Destination name
            self._attributes[f"Next {seq}, Departure day"] = friendly_day(local_dt)
            self._attributes[f"Next {seq}, Departure time"] = time_str
            self._attributes[f"Next {seq}, Route ID"] = dep.trasa
            self._attributes[f"Next {seq}, Brigade"] = dep.brygada

        _LOGGER.debug(
            "Updated %s: next = %s, %d more departures stored as attributes",
            self._attr_unique_id,
            self._next_departure,
            self._max_departures
        )

    @property
    def device_info(self):
        stop_info = self._coordinator.data.stop_info if self._coordinator.data else {}
        today_str = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
        timetable_url = f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt={today_str}&wtp_md=3&wtp_ln={self._line}"

        return {
            "identifiers": {(DOMAIN, f"line_{self._line}")},
            "name": f"Line {self._line}",
            "manufacturer": "Zarząd Transportu Miejskiego",
            "entry_type": "service",
            "model": _line_type(self._line),
            "sw_version": stop_info.get("obowiazuje_od"),
            "configuration_url": timetable_url,
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

    session = async_get_clientsession(hass)
    client = ZTMStopClient(
        session=session,
        api_key=data["api_key"],
        stop_id=stop_id,
        stop_number=stop_number,
        line=line,
    )
    coordinator = ZTMStopCoordinator(
        hass=hass,
        client=client,
        stop_id=stop_id,
        stop_nr=stop_number,
        line=line,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    identifier = f"Line {line} from {stop_id}/{stop_number}"

    entity = ZTMSensor(
        hass=hass,
        entry_id=config_entry.entry_id,
        stop_id=stop_id,
        stop_number=stop_number,
        line=line,
        name=identifier,
        max_departures=departures,
        coordinator=coordinator,
    )

    await entity.async_update()
    async_add_entities([entity])