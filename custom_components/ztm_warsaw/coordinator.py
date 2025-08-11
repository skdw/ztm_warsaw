import logging
from datetime import datetime, timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
import asyncio
import random
from homeassistant.helpers.event import async_call_later, async_track_time_change

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
        self._retry_unsub = None
        self._retry_delay_seconds = 120  # seconds; coordinator-level retry after a failed 02:30 refresh
        self._jitter_max_seconds = 45    # spread refresh calls to avoid thundering herd
        self._midnight_refresh_unsub = None
        self._last_success_local_date = None  # Europe/Warsaw date of last successful fetch
        self._last_stopinfo_refresh_date = None  # Europe/Warsaw date of last stop-info refresh

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
                    self._last_stopinfo_refresh_date = dt_util.now().date()
            except Exception:
                _LOGGER.debug("ZTM Coordinator [%s] — initial stop-info fetch skipped (non-fatal)", self.name)

        # Anuluj istniejące harmonogramy
        if self._daily_refresh_unsub:
            self._daily_refresh_unsub()
            self._daily_refresh_unsub = None
        if self._retry_unsub:
            self._retry_unsub()
            self._retry_unsub = None

        # Harmonogramy dzienne: 00:03 i 02:30 (z jitterem w callbackach)
        # 02:30 — bufor po nocnej aktualizacji rozkładu po stronie ZTM
        self._daily_refresh_unsub = async_track_time_change(
            self.hass,
            self._daily_refresh_callback,
            hour=2,
            minute=30,
            second=0,
        )

        # 00:03 — szybkie przeładowanie po zmianie dnia, aby uciec od wczorajszego rozkładu
        self._midnight_refresh_unsub = async_track_time_change(
            self.hass,
            self._midnight_refresh_callback,
            hour=0,
            minute=3,
            second=0,
        )

        _LOGGER.debug(
            "ZTM Coordinator [%s] — refresh scheduled daily at 00:03 and 02:30",
            self.name,
        )

    async def _daily_refresh_callback(self, now):
        warsaw_now = dt_util.as_local(now)
        # Add a small random jitter so multiple entities don't hammer the API at the exact same second.
        jitter = random.randint(0, self._jitter_max_seconds)
        _LOGGER.debug("ZTM Coordinator [%s] — daily refresh triggered at %s; applying jitter=%ss", self.name, warsaw_now, jitter)
        await asyncio.sleep(jitter)

        # Perform the refresh
        await self.async_refresh()

        # Fallback daily stop-info refresh
        await self._maybe_refresh_stop_info()

        # If refresh failed, schedule a one-off retry after a short delay
        if not self.last_update_success:
            delay = self._retry_delay_seconds
            _LOGGER.warning("ZTM Coordinator [%s] — daily refresh failed; scheduling retry in %ss", self.name, delay)
            if self._retry_unsub:
                self._retry_unsub()
                self._retry_unsub = None

            def _retry_cb(_ts):
                self._retry_unsub = None
                self.hass.async_create_task(self.async_request_refresh())

            self._retry_unsub = async_call_later(self.hass, delay, _retry_cb)
        else:
            # Clear any pending retry if we succeeded today
            if self._retry_unsub:
                self._retry_unsub()
                self._retry_unsub = None

    async def _midnight_refresh_callback(self, now):
        warsaw_now = dt_util.as_local(now)
        jitter = random.randint(0, self._jitter_max_seconds)
        _LOGGER.debug("ZTM Coordinator [%s] — midnight stop-info refresh triggered at %s; applying jitter=%ss", self.name, warsaw_now, jitter)
        await asyncio.sleep(jitter)

        # Only refresh stop metadata around midnight; do NOT touch timetable here
        await self._maybe_refresh_stop_info()

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
            
        except Exception as err:
            _LOGGER.error("ZTM Coordinator [%s] — failed fetching schedule: %s", self.name, err)
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def _maybe_refresh_stop_info(self):
        """Refresh stop metadata at most once per day."""
        today = dt_util.now().date()
        if self._last_stopinfo_refresh_date == today:
            return
        try:
            await self.client.get_stop_name()
            self._last_stopinfo_refresh_date = today
            _LOGGER.debug("ZTM Coordinator [%s] — stop-info refreshed", self.name)
        except Exception as err:
            _LOGGER.debug("ZTM Coordinator [%s] — stop-info refresh failed (non-fatal): %s", self.name, err)

    async def async_shutdown(self):
        """Clean up when coordinator is being shut down."""
        if self._daily_refresh_unsub:
            self._daily_refresh_unsub()
            self._daily_refresh_unsub = None
        if self._retry_unsub:
            self._retry_unsub()
            self._retry_unsub = None
        if self._midnight_refresh_unsub:
            self._midnight_refresh_unsub()
            self._midnight_refresh_unsub = None
        self.data = None
        _LOGGER.info("ZTM Coordinator [%s] — shutdown complete", self.name)
