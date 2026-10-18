import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import ZTMApiError, ZTMStopClient
from .models import ZTMDepartureData, ZTMDepartureDataReading, in_swap_window, next_flip_refresh, service_date_at

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
        # The answer before this one, kept while its late departures (the 27:xx of a night bus) are still ahead.
        self._previous: ZTMDepartureData | None = None
        self._flip_unsub = None
        # The last answer on disk, so a restart does not lose the night tail that the API no longer serves.
        self._store: Store[dict] = Store(hass, 1, f"ztm_warsaw.{self.name}")

        # Hourly timetable refresh handled by DataUpdateCoordinator
        self.update_interval = timedelta(hours=1)

    async def async_config_entry_first_refresh(self):
        """Perform first refresh and set up schedules."""
        if not self._initial_refresh_done:
            await self._restore()
            _LOGGER.debug("ZTM Coordinator [%s] — performing initial refresh", self.name)
            await self.async_refresh()
            self._initial_refresh_done = True

            # Ensure stop info is present once at startup (no repeated fetches later)
            try:
                if getattr(self.client, "_stop_name", None) is None:
                    await self.client.get_stop_name()
            except Exception:
                _LOGGER.debug("ZTM Coordinator [%s] — initial stop-info fetch skipped (non-fatal)", self.name)

        self._schedule_flip_refresh()
        _LOGGER.debug(
            "ZTM Coordinator [%s] — hourly timetable refresh enabled",
            self.name,
        )

    async def _restore(self):
        """Load the answers saved by the last run: a saved answer of this service day is used while the API is not asked,
        one of the previous day keeps its night tail."""
        today = service_date_at(dt_util.utcnow())
        for saved in (await self._store.async_load() or {}).get("answers", []):
            try:
                day = date.fromisoformat(saved["service_date"])
                answer = ZTMDepartureData(
                    [ZTMDepartureDataReading.from_dict(row, day) for row in saved["rows"]], saved.get("stop_info") or {}, day
                )
            except (TypeError, KeyError, ValueError, AttributeError):
                continue
            if day == today:
                self.data = answer
            elif day == today - timedelta(days=1):
                self._previous = answer

    def _save(self):
        self._store.async_delay_save(
            lambda: {
                "answers": [
                    {
                        "service_date": a.service_date.isoformat(),
                        "rows": [{k: v for k, v in asdict(r).items() if k != "dt"} for r in a.departures],
                        "stop_info": a.stop_info,
                    }
                    for a in (self._previous, self.data)
                    if a and a.service_date
                ]
            },
            30,
        )

    def _schedule_flip_refresh(self):
        """Ask again at 03:06 Warsaw time, when the update of the API is over."""
        self._flip_unsub = async_track_point_in_utc_time(self.hass, self._flip_refresh, next_flip_refresh(dt_util.utcnow()))

    @callback
    def _flip_refresh(self, _now):
        self._flip_unsub = None
        self._schedule_flip_refresh()
        self.hass.async_create_task(self.async_refresh())

    def is_fresh(self, now) -> bool:
        """Whether the cached timetable is the one of the service day that ``now`` is in."""
        return self.data is not None and self.data.service_date == service_date_at(now)

    def upcoming(self, now) -> list:
        """The departures at or after ``now`` from the current and the previous answer, in order."""
        known = [d for part in (self._previous, self.data) if part for d in part.departures]
        return sorted((d for d in known if d.dt and d.dt >= now), key=lambda d: d.dt)


    def _data_changed(self, new_data: ZTMDepartureData) -> bool:
        """Whether the timetable differs from the cached one; logs what changed."""
        if self.data is None:
            _LOGGER.info("ZTM Coordinator [%s] — first data load", self.name)
            return True
        if len(new_data.departures) != len(self.data.departures):
            _LOGGER.info(
                "ZTM Coordinator [%s] — departure count changed: %d → %d",
                self.name, len(self.data.departures), len(new_data.departures)
            )
            return True
        if [d.czas for d in self.data.departures] != [d.czas for d in new_data.departures]:
            _LOGGER.info("ZTM Coordinator [%s] — departure times changed", self.name)
            return True
        return False

    def _hold_during_swap(self) -> ZTMDepartureData:
        """The City is replacing its timetables, so an answer now may be either service day: keep the cached one.
        A failure is never hidden by it, and without a cached timetable there is nothing to keep."""
        if self.data is None or self._api_error:
            raise UpdateFailed("The City of Warsaw is updating its timetables; trying again after 03:05")
        return self.data

    def _accept(self, new_data: ZTMDepartureData) -> ZTMDepartureData:
        """Make a fresh answer the current one; the answer it replaces becomes the previous one on a new service day."""
        data_changed = self._data_changed(new_data)
        if self.data is not None and self.data.service_date != new_data.service_date:
            self._previous = self.data
        self.data = new_data
        self._save()
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

    async def _async_update_data(self) -> ZTMDepartureData:
        if in_swap_window(dt_util.utcnow()):
            return self._hold_during_swap()
        _LOGGER.debug("ZTM Coordinator [%s] — fetching new schedule data", self.name)
        try:
            new_data = await self.client.get()
            if in_swap_window(dt_util.utcnow()):  # the request began before the update did and ended inside it
                return self._hold_during_swap()
            if new_data is None:
                if self.data is not None and not self._api_error:
                    _LOGGER.warning(
                        "ZTM Coordinator [%s] — timetable fetch failed; keeping cached data",
                        self.name,
                    )
                    return self.data
                raise UpdateFailed("Timetable fetch failed and there is no usable cached timetable")
            return self._accept(new_data)

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
        self._previous = None
        if self._flip_unsub:
            self._flip_unsub()
            self._flip_unsub = None
        await super().async_shutdown()
        _LOGGER.info("ZTM Coordinator [%s] — shutdown complete", self.name)
