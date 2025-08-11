from datetime import timedelta
import random
import asyncio
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
from homeassistant.util import dt as dt_util

class ZTMStopCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, client, stop_id, stop_nr, line):
        super().__init__(
            hass,
            _LOGGER,
            name=f"ztm_warsaw_{stop_id}_{stop_nr}_{line}",
            update_interval=timedelta(hours=1),
        )
        self.hass = hass
        self.client = client
        self.stop_id = stop_id
        self.stop_nr = stop_nr
        self.line = line

        self._retry_unsub = None
        self._jitter_max_seconds = 45

        self._midnight_unsub = None
        self._daily_unsub = None  # keep alias for clarity if not present
        self._last_success_local_date = None  # date in Europe/Warsaw of last successful fetch

    def _next_local_time(self, hour: int, minute: int = 0, second: int = 0):
        """Return next datetime (tz-aware) at given local time (Europe/Warsaw)."""
        now = dt_util.now()
        target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    def _schedule_daily_jobs(self):
        # Cancel previous timers
        if getattr(self, "_daily_refresh_unsub", None):
            self._daily_refresh_unsub()
            self._daily_refresh_unsub = None
        if self._midnight_unsub:
            self._midnight_unsub()
            self._midnight_unsub = None

        # Schedule midnight+few minutes refresh (00:03 local)
        run_at_midnight = self._next_local_time(0, 3, 0)
        self._midnight_unsub = async_track_point_in_time(
            self.hass, self._midnight_refresh_callback, run_at_midnight
        )

        # Keep existing 02:30 refresh
        run_at_0230 = self._next_local_time(2, 30, 0)
        self._daily_refresh_unsub = async_track_point_in_time(
            self.hass, self._daily_refresh_callback, run_at_0230
        )

        _LOGGER.debug(
            "ZTM Coordinator [%s] — scheduled midnight refresh at %s and 02:30 refresh at %s",
            self.name,
            dt_util.as_local(run_at_midnight),
            dt_util.as_local(run_at_0230),
        )

    async def async_config_entry_first_refresh(self):
        try:
            await self.async_refresh()
        finally:
            # (Re)schedule our daily jobs (00:03 and 02:30)
            self._schedule_daily_jobs()

            # Day-change guard: if we started after midnight and last success was on a previous day, request a refresh soon.
            if self._last_success_local_date:
                today_local = dt_util.now().date()
                if self._last_success_local_date != today_local:
                    jitter = random.randint(0, getattr(self, "_jitter_max_seconds", 45))
                    _LOGGER.debug("ZTM Coordinator [%s] — day-change guard scheduling immediate refresh (jitter=%ss)", self.name, jitter)
                    async_call_later(self.hass, jitter, lambda _ts: self.hass.async_create_task(self.async_request_refresh()))

    async def _midnight_refresh_callback(self, now):
        warsaw_now = dt_util.as_local(now)
        jitter = random.randint(0, getattr(self, "_jitter_max_seconds", 45))
        _LOGGER.debug("ZTM Coordinator [%s] — midnight refresh triggered at %s; applying jitter=%ss", self.name, warsaw_now, jitter)
        await asyncio.sleep(jitter)

        await self.async_refresh()

        if not self.last_update_success:
            delay = getattr(self, "_retry_delay_seconds", 120)
            _LOGGER.warning("ZTM Coordinator [%s] — midnight refresh failed; scheduling retry in %ss", self.name, delay)
            if getattr(self, "_retry_unsub", None):
                self._retry_unsub()
                self._retry_unsub = None

            def _retry_cb(_ts):
                self._retry_unsub = None
                self.hass.async_create_task(self.async_request_refresh())

            self._retry_unsub = async_call_later(self.hass, delay, _retry_cb)
        else:
            if getattr(self, "_retry_unsub", None):
                self._retry_unsub()
                self._retry_unsub = None

    async def _async_update_data(self):
        new_data = await self.client.async_get_departures()
        if new_data is not None:
            _LOGGER.debug("ZTM Coordinator [%s] — fetched new data successfully", self.name)
            # Track last success date in local time (Europe/Warsaw)
            self._last_success_local_date = dt_util.now().date()
        return new_data

    async def async_shutdown(self):
        if self._midnight_unsub:
            self._midnight_unsub()
            self._midnight_unsub = None
        if getattr(self, "_daily_refresh_unsub", None):
            self._daily_refresh_unsub()
            self._daily_refresh_unsub = None
        if self._retry_unsub:
            self._retry_unsub()
            self._retry_unsub = None