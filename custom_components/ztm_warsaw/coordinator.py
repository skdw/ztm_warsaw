import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ZTMStopClient
from .models import ZTMDepartureData, ZTMDepartureDataReading


# Coordinator responsible for fetching and storing schedule data for a specific stop-line pair
class ZTMStopCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, stop_id: str, stop_nr: str, line: str, client: ZTMStopClient, update_interval: timedelta = timedelta(hours=1)):
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug("ZTMStopCoordinator __init__ called for %s/%s line %s", stop_id, stop_nr, line)
        # ID of the bus/train stop (e.g., '1097' = stop group 'Marcelin')
        self.stop_id = stop_id
        # Specific pole number at the stop (e.g., '01' = specific direction/platform)
        self.stop_nr = stop_nr
        # Line number (e.g., '126', 'N85', or SKM train line)
        self.line = line
        # Client used to fetch data from ZTM API
        self.client = client
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=f"ztm_{line}_{stop_id}_{stop_nr}",  # Unique name used by Home Assistant
            update_method=self._async_update_data,   # Async function to fetch updated schedule
            update_interval=update_interval,         # How often to fetch new data
        )
        # Stores the current state of fetched departure data
        self.data: ZTMDepartureData | None = None

    # Asynchronous method that fetches the latest data using the API client
    async def _async_update_data(self) -> ZTMDepartureData:
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug("ZTMStopCoordinator is refreshing data for %s/%s line %s", self.stop_id, self.stop_nr, self.line)
        try:
            data = await self.client.get()
            self.data = ZTMDepartureData(
                departures=data.departures,
                stop_info=data.stop_info
            )
            _LOGGER.debug("Fetched %d departures for %s/%s line %s", len(data.departures), self.stop_id, self.stop_nr, self.line)
            _LOGGER.debug("Stop info: %s", data.stop_info)
            _LOGGER.debug("Departure data object: %s", data)
            return data
        except Exception as err:
            _LOGGER.exception("Failed fetching schedule for %s/%s line %s: %s", self.stop_id, self.stop_nr, self.line, err)
            # Raise a Home Assistant-specific error if fetching fails
            raise UpdateFailed(f"Error fetching data: {err}") from err
