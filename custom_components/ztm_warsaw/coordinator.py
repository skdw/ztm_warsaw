import logging
from datetime import datetime, timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import ZTMApiError, ZTMStopClient
from .models import ZTMDepartureData

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
        # True after the API answered with something that is not a timetable, until a timetable arrives. While it
        # is set a network error must not bring the cached timetable back: that would make the sensor look healthy.
        self._api_error = False

        # Hourly timetable refresh handled by DataUpdateCoordinator
        self.update_interval = timedelta(hours=1)

    async def async_config_entry_first_refresh(self):
        """Perform first refresh and set up schedules."""
        if not self._initial_refresh_done:
            _LOGGER.debug("ZTM Coordinator [%s] — performing initial refresh", self.name)
            await self.async_refresh()
            self._initial_refresh_done = True

            # Ensure stop info is present once at startup (no repeated fetches later)
            try:
                if getattr(self.client, "_stop_name", None) is None:
                    await self.client.get_stop_name()
            except Exception:
                _LOGGER.debug("ZTM Coordinator [%s] — initial stop-info fetch skipped (non-fatal)", self.name)

        _LOGGER.debug(
            "ZTM Coordinator [%s] — hourly timetable refresh enabled",
            self.name,
        )


    async def _async_update_data(self) -> ZTMDepartureData:
        _LOGGER.debug("ZTM Coordinator [%s] — fetching new schedule data", self.name)
        try:
            new_data = await self.client.get()
            if new_data is None:
                if self.data is not None and not self._api_error:
                    _LOGGER.warning(
                        "ZTM Coordinator [%s] — timetable fetch failed; keeping cached data",
                        self.name,
                    )
                    return self.data
                raise UpdateFailed("Timetable fetch failed and there is no usable cached timetable")
            
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
            self._api_error = False
            self.last_update_success_time = dt_util.utcnow()
            # Track last success date in local time (Europe/Warsaw)
            self._last_success_local_date = dt_util.now().date()
            
            if data_changed:
                _LOGGER.info("ZTM Coordinator [%s] — new schedule data available, notifying sensors", self.name)
            count = len(new_data.departures)
            _LOGGER.debug(
                "ZTM Coordinator [%s] — successfully fetched %d departures%s",
                self.name,
                count,
                " (empty set)" if count == 0 else "",
            )
            return new_data
            
        except UpdateFailed:
            raise
        except ZTMApiError as err:
            # The city answered but not with a timetable (a rejected key, an unknown stop or line, an answer in an
            # unknown format). Unlike a network error this is not "try again later with the cached timetable":
            # the entity becomes unavailable instead of pretending nothing runs. Home Assistant logs this once,
            # when the state changes, and again when it recovers.
            self._api_error = True
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            if self.data is not None and not self._api_error:
                # Keep entity available with last known data; try again on next hourly tick
                _LOGGER.warning(
                    "ZTM Coordinator [%s] — fetch failed (%s); keeping last known timetable and retrying next hour",
                    self.name,
                    err,
                )
                return self.data
            _LOGGER.error("ZTM Coordinator [%s] — failed fetching schedule and no cached data", self.name)
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def async_shutdown(self):
        """Clean up when coordinator is being shut down."""
        if getattr(self, "_ztm_shutdown_done", False):
            return
        self._ztm_shutdown_done = True
        self.data = None
        await super().async_shutdown()
        _LOGGER.info("ZTM Coordinator [%s] — shutdown complete", self.name)
