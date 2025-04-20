from datetime import timedelta, datetime, timezone
import logging
import re

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity

from .client import ZTMStopClient
from .models import ZTMDepartureDataReading
from .const import CONF_DEPARTURES

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by the City of Warsaw (api.um.warszawa.pl)"
SCAN_INTERVAL = timedelta(minutes=1)


class ZTMSensor(SensorEntity):
    def __init__(
        self, hass, api_key, stop_id, stop_number, line, name, max_departures, return_type
    ):
        self._line = line
        self._stop_id = stop_id
        self._stop_number = stop_number
        self._name = name
        self._state = None
        self._attributes = {}
        self._max_departures = max_departures
        self._return_type = return_type
        self._timetable = []
        self.client = ZTMStopClient(
            async_get_clientsession(hass), api_key, stop_id, stop_number, line
        )
        self._attr_unique_id = f"ztm_{line}_{stop_id}_{stop_number}"

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        if re.match(r"^\d{1,2}$", self._line):
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
    def unit_of_measurement(self):
        """Return 'min' only when we have real departures; hide unit on errors/no data."""
        if self._state in ("No data available", "No departures available"):
            return None
        return "min" if self._return_type == "TIME_TO_DEPART" else None

    @property
    def extra_state_attributes(self):
        return self._attributes

    async def async_update(self):
        """Fetch new data from ZTM API and update state + attributes."""
        try:
            data = await self.client.get()
        except Exception as e:
            _LOGGER.warning("Exception while fetching data: %s", e)
            self._state = "No data available"
            self._attributes.clear()
            self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
            return

        departures = data.departures

        # 2) No departures at all
        if not departures:
            self._state = "60+"
            self._attributes.clear()
            self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
            self._attributes["note"] = "No upcoming schedule available. Please verify on wtp.waw.pl or call 19115 for more information."
            return

        # 3) Filter to next 60 minutes
        valid = [d for d in departures if d.time_to_depart <= 60]

        # Set state: minutes until next departure or '60+'
        if valid:
            self._state = f"{valid[0].time_to_depart}"
        else:
            self._state = "60+"

        # 4) Build attributes: [1] Time, [1] Departure, [1] Direction, ...
        to_show = departures[: self._max_departures]
        self._attributes.clear()
        self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION

        for idx, dep in enumerate(to_show, start=1):
            time_str = dep.dt.astimezone().strftime("%H:%M")
            self._attributes[f"[{idx}] Time"] = time_str
            self._attributes[f"[{idx}] Departure"] = f"{dep.time_to_depart} min"
            self._attributes[f"[{idx}] Direction"] = dep.kierunek

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up ZTM sensor from a config entry."""
    # Read configuration and options
    data = config_entry.data
    options = config_entry.options

    api_key = data["api_key"]
    stop_id = str(data["busstop_id"])
    stop_nr = str(data["busstop_nr"])
    line = data["line"]
    # Use departures option if set, else fallback to initial data
    departures = options.get(CONF_DEPARTURES, data.get(CONF_DEPARTURES, 1))

    identifier = f"Line {line} from {stop_id}/{stop_nr}"

    entity = ZTMSensor(
        hass=hass,
        api_key=api_key,
        stop_id=stop_id,
        stop_number=stop_nr,
        line=line,
        name=identifier,
        max_departures=departures,
        return_type="TIME_TO_DEPART"
    )

    await entity.async_update()
    async_add_entities([entity])