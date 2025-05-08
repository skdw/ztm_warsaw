import logging
import re
from datetime import datetime, timezone, timedelta

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow as ha_utcnow

from .const import CONF_DEPARTURES, DOMAIN, CONF_ATTRIBUTION

from .models import ZTMDepartureDataReading

_LOGGER = logging.getLogger(__name__)

LINE_TYPE_MAP = {
    # Buses
    "1": "Normal bus",
    "2": "Normal bus",
    "3": "Normal periodic bus",
    "4": "Fast periodic bus",
    "5": "Fast bus",
    "6": "Unknown bus",
    "7": "Zone normal bus",
    "8": "Zone periodic bus",
    "9": "Special bus",
    "C": "Cemetery bus",
    "E": "Express periodic bus",
    "L": "Local suburban bus",
    "N": "Night bus",
    "Z": "Replacement line",
    "T": "Tram line",
    "M": "Metro line",
    "S": "Urban rail",
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
    def __init__(self, hass, entry_id, stop_id, stop_number, line, name, max_departures):
        self._hass = hass
        self._entry_id = entry_id
        self._line = line
        self._stop_id = stop_id
        self._stop_number = stop_number
        self._name = name
        self._attributes = {}
        self._max_departures = max_departures
        # expose as timestamp sensor
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._next_departure = None
        self._attr_unique_id = f"ztm_{line}_{stop_id}_{stop_number}"

        # static line-level attributes
        self._attributes["Line, Stop ID"] = self._stop_id
        self._attributes["Line, Stop number"] = self._stop_number
        self._attributes["Line, Timezone"] = "Europe/Warsaw"
        self._attributes["Line, Type"] = _line_type(self._line)

    @property
    def name(self):
        return self._name

    @property
    def native_value(self):
        """Return the next departure as a timezone‑aware datetime (or None)."""
        return self._next_departure

    @property
    def icon(self):
        # Tram 1–99
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
        coordinator: DataUpdateCoordinator = self._hass.data[DOMAIN][self._entry_id]
        data = coordinator.data
        _LOGGER.debug("Data from coordinator: %s", data)
        if data is None:
            _LOGGER.warning("No timetable data available from coordinator")
            self._next_departure = None
            self._attributes.clear()
            self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
            return

        all_departures = data.departures  # full day timetable

        departures = all_departures

        # Keep only future departures (>= now)
        now_utc = ha_utcnow()
        departures = [d for d in departures if d.dt >= now_utc]

        departures = [d for d in departures if d.dt is not None]

        # Find the soonest departure (if any) and expose it as timestamp
        if departures:
            _LOGGER.debug("Next departure time for %s: %s", self._attr_unique_id, departures[0].dt)
        else:
            _LOGGER.debug("No departures found for %s", self._attr_unique_id)
        self._next_departure = departures[0].dt if departures else None

        # 2) No departures at all
        if not departures:
            self._next_departure = None
            # Do not clear all attributes to preserve structure for templates/helpers
            static_attrs = {
                k: self._attributes[k]
                for k in list(self._attributes)
                if k.startswith("Line, ")
            }
            self._attributes.clear()
            self._attributes.update(static_attrs)
            self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION

            today_str = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
            self._attributes["Line, Full timetable"] = f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt={today_str}&wtp_md=3&wtp_ln={self._line}"
            self._attributes["note"] = "No upcoming schedule available. Please verify on wtp.waw.pl or call 19115."

            # Preserve empty values for expected attributes
            self._attributes["Upcoming, Headsign"] = "No service"
            self._attributes["Upcoming, Departure day"] = "Unknown"
            for seq in range(1, self._max_departures + 1):
                self._attributes[f"Next {seq}, Headsign"] = "No service"
                self._attributes[f"Next {seq}, Departure day"] = "Unknown"
                self._attributes[f"Next {seq}, Departure time"] = "Unknown"
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
        # Add link to full timetable on WTP site for today's date
        today_str = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
        self._attributes["Line, Full timetable"] = f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt={today_str}&wtp_md=3&wtp_ln={self._line}"

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
        self._attributes["Upcoming, Headsign"] = current.kierunek
        self._attributes["Upcoming, Departure day"] = friendly_day(local_current)

        for seq, dep in enumerate(departures[1 : self._max_departures + 1], start=1):
            local_dt = dep.dt.astimezone()  # convert to system's local tz (Europe/Warsaw)
            time_str = local_dt.strftime("%H:%M")
            self._attributes[f"Next {seq}, Headsign"] = dep.kierunek
            self._attributes[f"Next {seq}, Departure day"] = friendly_day(local_dt)
            self._attributes[f"Next {seq}, Departure time"] = time_str

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

    identifier = f"Line {line} from {stop_id}/{stop_number}"

    entity = ZTMSensor(
        hass=hass,
        entry_id=config_entry.entry_id,
        stop_id=stop_id,
        stop_number=stop_number,
        line=line,
        name=identifier,
        max_departures=departures,
    )

    await entity.async_update()
    async_add_entities([entity])