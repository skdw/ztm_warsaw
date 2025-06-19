import logging
from datetime import timedelta, datetime
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.helpers.event import async_track_time_change

from .client import ZTMStopClient
from .models import ZTMDepartureData, ZTMDepartureDataReading

_LOGGER = logging.getLogger(__name__)

class ZTMStopCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, stop_id: str, stop_nr: str, line: str, client: ZTMStopClient):
        super().__init__(
            hass,
            _LOGGER,
            name=f"line_{line}_from_{stop_id}_{stop_nr}",
            update_method=self._async_update_data,
        )
        self.stop_id = stop_id
        self.stop_nr = stop_nr
        self.line = line
        self.client = client
        self.data: ZTMDepartureData | None = None
        self.last_update_success_time: datetime | None = None
        self._initial_refresh_done = False
        self._daily_refresh_unsub = None

    async def async_config_entry_first_refresh(self):
        """Perform first refresh and set up schedules."""
        if not self._initial_refresh_done:
            _LOGGER.debug("ZTM Coordinator [%s] — performing initial refresh", self.name)
            await self.async_refresh()
            self._initial_refresh_done = True

        # Anuluj istniejące harmonogramy
        if self._daily_refresh_unsub:
            self._daily_refresh_unsub()
            self._daily_refresh_unsub = None

        # Harmonogram o 2:30 czasu lokalnego (jedyny harmonogram działa o 2:30 jako bufor po aktualizacji rozkładu o 2:10)
        self._daily_refresh_unsub = async_track_time_change(
            self.hass,
            self._daily_refresh_callback,
            hour=2,
            minute=30,
            second=0,
        )

        _LOGGER.debug(
            "ZTM Coordinator [%s] — refresh scheduled daily at 02:30",
            self.name
        )

    async def _daily_refresh_callback(self, now):
        warsaw_now = dt_util.as_local(now)
        _LOGGER.debug("ZTM Coordinator [%s] — refresh triggered at %s", self.name, warsaw_now)
        await self.async_request_refresh()

    async def _async_update_data(self) -> ZTMDepartureData:
        _LOGGER.debug("ZTM Coordinator [%s] — fetching new schedule data", self.name)
        try:
            new_data = await self.client.get()
            
            data_changed = False
            if self.data is None:
                data_changed = True
                _LOGGER.info("ZTM Coordinator [%s] — first data load", self.name)
            elif len(new_data.departures) != len(self.data.departures):
                data_changed = True
                _LOGGER.info(
                    "ZTM Coordinator [%s] — departure count changed: %d → %d", 
                    self.name, len(self.data.departures), len(new_data.departures)
                )
            else:
                old_times = [d.czas for d in self.data.departures]
                new_times = [d.czas for d in new_data.departures]
                if old_times != new_times:
                    data_changed = True
                    _LOGGER.info("ZTM Coordinator [%s] — departure times changed", self.name)
            
            self.data = new_data
            self.last_update_success_time = dt_util.utcnow()
            
            if data_changed:
                _LOGGER.info("ZTM Coordinator [%s] — new schedule data available, notifying sensors", self.name)
            
            _LOGGER.debug(
                "ZTM Coordinator [%s] — successfully fetched %d departures", 
                self.name, len(new_data.departures)
            )
            return new_data
            
        except Exception as err:
            _LOGGER.error("ZTM Coordinator [%s] — failed fetching schedule: %s", self.name, err)
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def async_shutdown(self):
        """Clean up when coordinator is being shut down."""
        if self._daily_refresh_unsub:
            self._daily_refresh_unsub()
            self._daily_refresh_unsub = None
        self.data = None
        _LOGGER.info("ZTM Coordinator [%s] — shutdown complete", self.name)
