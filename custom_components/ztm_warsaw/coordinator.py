import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import ZTMStopClient
from .models import ZTMDepartureData, ZTMDepartureDataReading

_LOGGER = logging.getLogger(__name__)

# Coordinator responsible for fetching and storing schedule data for a specific stop-line pair
class ZTMStopCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, stop_id: str, stop_nr: str, line: str, client: ZTMStopClient, update_interval=timedelta(hours=1)):
        super().__init__(
            hass,
            _LOGGER,
            name=f"line_{line}_from_{stop_id}_{stop_nr}",  # Unique name used by Home Assistant
            update_method=self._async_update_data,   # Async function to fetch updated schedule
            update_interval=update_interval,         # How often to fetch new data
        )
        self.stop_id = stop_id
        self.stop_nr = stop_nr
        self.line = line
        self.client = client
        self.data: ZTMDepartureData | None = None
        self.last_update_success_time: datetime | None = None

    # Asynchronous method that fetches the latest data using the API client
    async def _async_update_data(self) -> ZTMDepartureData:
        _LOGGER.debug("Refreshing schedule for %s/%s line %s...", self.stop_id, self.stop_nr, self.line)
        try:
            self.data = await self.client.get()
            self.last_update_success_time = dt_util.utcnow()
            return self.data
        except Exception as err:
            _LOGGER.exception("Failed fetching schedule for %s/%s line %s: %s", self.stop_id, self.stop_nr, self.line, err)
            # Raise a Home Assistant-specific error if fetching fails
            raise UpdateFailed(f"Error fetching data: {err}") from err