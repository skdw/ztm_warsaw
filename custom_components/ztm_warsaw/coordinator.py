import asyncio
import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import ZTMApiError, ZTMStopClient
from .models import ZTMDepartureData, ZTMDepartureDataReading, in_swap_window, next_flip_refresh, service_date_at

_LOGGER = logging.getLogger(__name__)

SETUP_DEADLINE = 30  # seconds the first refresh of an entry may take before setup is retried
STOP_NAME_DEADLINE = 10  # and the stop's name after it

def store_key(entry_id: str) -> str:
    """One store per config entry: the saved failure marker belongs to the key of that entry."""
    return f"ztm_warsaw.{entry_id}"


class ZTMStopCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, stop_id: str, stop_nr: str, line: str, client: ZTMStopClient, entry_id: str):
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
        # True after the API answered with something that is not a timetable, until a timetable arrives. While it
        # is set a network error must not bring the cached timetable back: that would make the sensor look healthy.
        self._api_error = False
        # The answer before this one, kept while its late departures (the 27:xx of a night bus) are still ahead.
        self._previous: ZTMDepartureData | None = None
        self._flip_unsub = None
        self._refreshing = asyncio.Lock()
        self._started = False  # the first refresh is over: from then on a refresh may also ask for the stop's name
        self._ztm_shutdown_done = False
        self._refreshes = 0  # how many refreshes have finished
        # The last answer on disk, so a restart does not lose the night tail that the API no longer serves.
        self._store: Store[dict] = Store(hass, 1, store_key(entry_id))

        # Hourly timetable refresh handled by DataUpdateCoordinator
        self.update_interval = timedelta(hours=1)

    async def async_config_entry_first_refresh(self):
        """First refresh of the entry: a failure or a missing answer within the deadline makes Home Assistant retry the
        setup (ConfigEntryNotReady) instead of leaving an entity that waits for the next hourly refresh."""
        await self._restore()
        try:
            async with asyncio.timeout(SETUP_DEADLINE):
                await super().async_config_entry_first_refresh()
        except TimeoutError as err:
            if self.data is None:
                raise ConfigEntryNotReady("The City of Warsaw did not answer in time") from err
            _LOGGER.debug("ZTM Coordinator [%s] — no answer in time, starting from the stored timetable", self.name)
            self.last_update_success = True  # the cancelled refresh marked it failed; the stored timetable is what we hold
        except ConfigEntryNotReady as err:
            # Home Assistant raises it without a reason; the cause is a fixed text that never holds the key.
            raise ConfigEntryNotReady(str(err.__cause__ or err) or "The City of Warsaw did not answer properly") from err
        self._started = True
        await self._load_stop_name()
        self._schedule_flip_refresh()

    async def _load_stop_name(self):
        """The stop's name, once at startup (the client keeps it), on a short leash and never inside the City's update;
        a failure only means the sensors have no name for it."""
        if in_swap_window(dt_util.utcnow()):
            return
        try:
            async with asyncio.timeout(STOP_NAME_DEADLINE):
                info = await self.client.get_stop_name()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("ZTM Coordinator [%s] — stop-info fetch skipped (non-fatal)", self.name)
            return
        if info and self.data is not None:
            self.data.stop_info = info

    async def _restore(self):
        """Load the answers saved by the last run: a saved answer of this service day is used while the API is not asked,
        one of the previous day keeps its night tail."""
        today = service_date_at(dt_util.utcnow())
        try:
            stored = await self._store.async_load()
        except Exception:  # noqa: BLE001 - an unreadable store must never stop the first refresh
            _LOGGER.debug("ZTM Coordinator [%s] — stored answers could not be read", self.name, exc_info=True)
            return
        if not isinstance(stored, dict):
            return
        self._api_error = stored.get("api_error") is True  # a rejected key stays a failure across a restart
        answers = stored.get("answers")
        for saved in answers if isinstance(answers, list) else []:
            try:
                day = date.fromisoformat(saved["service_date"])
                stop_info = saved.get("stop_info")
                answer = ZTMDepartureData(
                    [ZTMDepartureDataReading.from_dict(row, day) for row in saved["rows"]],
                    stop_info if isinstance(stop_info, dict) else {},
                    day,
                )
            except (TypeError, KeyError, ValueError, AttributeError):
                continue
            if day == today:
                self.data = answer
            elif day == today - timedelta(days=1):
                self._previous = answer
        if self.data is None and self._previous is not None:
            # Only the night tail of yesterday is known: it is what to fall back on if the first request fails.
            self.data, self._previous = self._previous, None

    def _payload(self) -> dict:
        return {
            "answers": [
                {
                    "service_date": a.service_date.isoformat(),
                    "rows": [{k: v for k, v in asdict(r).items() if k != "dt"} for r in a.departures],
                    "stop_info": a.stop_info,
                }
                for a in (self._previous, self.data)
                if a and a.service_date
            ],
            "api_error": self._api_error,
        }

    def _save(self):
        # Built now, not when the delayed write runs: by then a shutdown may have cleared the answers.
        if self._ztm_shutdown_done:  # a refresh that was still running must not write the store of an unloaded entry
            return
        payload = self._payload()
        self._store.async_delay_save(lambda: payload, 30)

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
        self._api_error = False
        self._save()
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
        """One refresh at a time: a refresh that waited for another one (the 03:06 refresh and the hourly one can fire
        together) takes its answer instead of asking the City again, unless that answer was a failure."""
        seen = self._refreshes
        async with self._refreshing:
            if self._refreshes != seen and self.data is not None and not self._api_error:
                return self.data
            answer = await self._fetch()
            self._refreshes += 1  # only a finished refresh counts for a waiter
            return answer

    async def _fetch(self) -> ZTMDepartureData:
        if in_swap_window(dt_util.utcnow()):
            return self._hold_during_swap()
        _LOGGER.debug("ZTM Coordinator [%s] — fetching new schedule data", self.name)
        try:
            new_data = await self.client.get(fetch_stop_name=self._started)  # the name is not worth the setup's deadline
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
            if in_swap_window(dt_util.utcnow()):  # a request that straddles the start of the City's update
                return self._hold_during_swap()
            self._api_error = True
            self._save()
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
        if self._ztm_shutdown_done:
            return
        self._ztm_shutdown_done = True
        try:
            await self._store.async_save(self._payload())  # also cancels a delayed write that is still pending
        finally:  # a failing write must not leave the 03:06 callback or the coordinator running
            self.data = None
            self._previous = None
            if self._flip_unsub:
                self._flip_unsub()
                self._flip_unsub = None
            await super().async_shutdown()
        _LOGGER.info("ZTM Coordinator [%s] — shutdown complete", self.name)
