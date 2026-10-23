"""The coordinator: one per stop, it asks the City for the timetable and holds the answer for the sensors and the calendar.

It is the one place that knows when to ask (hourly, again at 03:06 once the City's swap is over and the service day has
changed at 03:05, never while the City swaps
its data between 02:10 and 03:05), what to do when the City fails or rejects the key (keep the cached timetable,
but never make a rejected key look healthy; after three rejections the user is asked for a new key), and what to
keep on disk (the last two answers, so that a restart does not lose the night tail of a night line).
"""

import asyncio
import logging
from dataclasses import asdict
from typing import Any
from datetime import date, datetime, timedelta, timezone
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError

from .const import DOMAIN
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later, async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import ZTMApiError, ZTMAuthError, ZTMStopClient
from .models import ZTMDepartureData, ZTMDepartureDataReading, in_swap_window, next_flip_refresh, service_date_at

_LOGGER = logging.getLogger(__name__)

SETUP_DEADLINE = 30  # seconds the first refresh of an entry may take before setup is retried
STOP_NAME_DEADLINE = 10  # and the stop's name after it
FAILURES_BEFORE_NOTICE = 6  # failed refreshes in a row (about two and a half hours) before a token's silence is made a notice
REJECTIONS_BEFORE_REAUTH = 3  # consecutive refreshes that the City answers with 'rejected key' before the user is asked

def silent_issue_id(ref: str) -> str:
    """The ID of the Repairs notice that says the City has not answered a stop for hours (``ref`` is the stop's entry or subentry ID)."""
    return f"silent_{ref}"


def store_key(entry_id: str) -> str:
    """One store per config entry: the saved failure marker belongs to the key of that entry."""
    return f"ztm_warsaw.{entry_id}"


_EPOCH = datetime.min.replace(tzinfo=timezone.utc)
RETRY_AFTER = 300  # seconds to wait before asking again after a failed refresh was covered by the cached timetable
MAX_RETRY_AFTER = 3600  # the wait doubles with every failure in a row, up to the hourly refresh


def _reason(err: BaseException) -> str:
    """The cause of a Home Assistant error that was raised without a reason (its text is then empty or \"None\"), or a dash."""
    text = str(err.__cause__ or err)
    return text if text not in ("", "None") else "-"


class ZTMStopCoordinator(DataUpdateCoordinator[ZTMDepartureData | None]):
    """Holds the timetable of one line at one pole and refreshes it; the sensors and the calendar read it from here."""

    def __init__(self, hass: HomeAssistant, stop_id: str, stop_nr: str, line: str, client: ZTMStopClient, entry_id: str):
        """Set up the refresh of the stop (hourly); ``entry_id`` names the answers kept on disk, which the first refresh loads."""
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
        self.walking_minutes = 0  # set for a stop with a walking time: the sensor skips the departures sooner than that
        self.device_per_stop = False  # set for the stops of a line entry: each is a device of its own
        self.data = None
        self.last_update_success_time: datetime | None = None
        # True after the API answered with something that is not a timetable, until a timetable arrives. While it
        # is set a network error must not bring the cached timetable back: that would make the sensor look healthy.
        self._api_error = False
        # The answer before this one, kept while its late departures (the 27:xx of a night bus) are still ahead.
        self._previous: ZTMDepartureData | None = None
        self._flip_unsub: CALLBACK_TYPE | None = None
        self._retry_unsub: CALLBACK_TYPE | None = None
        self._ref = entry_id
        self._silent_said = False  # the notice about the City's silence is up
        self._failures = 0  # refreshes in a row that the cached timetable had to cover (the log says it once, the wait grows)
        self._refreshing = asyncio.Lock()
        self._rejections = 0  # consecutive answers of the City that reject the key
        self._started = False  # the first refresh is over: from then on a refresh may also ask for the stop's name
        self._ztm_shutdown_done = False
        self._refreshes = 0  # how many refreshes have finished
        # The last answer on disk, so a restart does not lose the night tail that the API no longer serves.
        self._store: Store[dict[str, Any]] = Store(hass, 1, store_key(entry_id))

        # Hourly timetable refresh handled by DataUpdateCoordinator; none for a key of the City's old API, which is gone
        self.update_interval = None if client.retired else timedelta(hours=1)

    async def async_config_entry_first_refresh(self) -> None:
        """First refresh of the entry: a failure or a missing answer within the deadline makes Home Assistant retry the
        setup (ConfigEntryNotReady) instead of leaving an entity that waits for the next hourly refresh."""
        await self._restore()
        if self.client.retired:  # nothing to fetch from the City's old API: hold what was saved, entities say why there is no timetable
            self.start_without_timetable()
            return
        try:
            async with asyncio.timeout(SETUP_DEADLINE):
                await super().async_config_entry_first_refresh()
        except TimeoutError as err:
            if self.data is None:
                raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="city_timeout") from err
            _LOGGER.debug("ZTM Coordinator [%s] — no answer in time, starting from the stored timetable", self.name)
            self.last_update_success = True  # the cancelled refresh marked it failed; the stored timetable is what we hold
        except ConfigEntryNotReady as err:
            # Home Assistant raises it without a reason; the cause is a fixed text that never holds the key.
            cause = err.__cause__
            if isinstance(cause, HomeAssistantError) and cause.translation_key:  # the specific reason, already translated
                raise ConfigEntryNotReady(
                    translation_domain=cause.translation_domain,
                    translation_key=cause.translation_key,
                    translation_placeholders=cause.translation_placeholders,
                ) from err
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="city_not_ready",
                translation_placeholders={"error": _reason(err)},
            ) from err
        self._started = True
        await self._load_stop_name()
        self._schedule_flip_refresh()

    def start_without_timetable(self) -> None:
        """The first refresh of this stop failed while the other stops of its line answered: the stop starts anyway, its
        entities are unavailable, and the hourly refresh (and the one after the service day changes) brings the timetable."""
        self._started = True
        self._schedule_flip_refresh()

    async def _load_stop_name(self) -> None:
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

    async def _restore(self) -> None:
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
        rejections = stored.get("rejections")
        self._rejections = rejections if isinstance(rejections, int) and not isinstance(rejections, bool) and 0 <= rejections < REJECTIONS_BEFORE_REAUTH else 0
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

    def _payload(self) -> dict[str, Any]:
        """What is saved on disk: the last two answers (the earlier day's keeps its night tail), the failure marker and the count of rejections."""
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
            "rejections": self._rejections,
        }

    def _save(self) -> None:
        """Write the payload to disk a little later (30 s, one write for a burst of changes), unless the coordinator has been shut down."""
        # Built now, not when the delayed write runs: by then a shutdown may have cleared the answers.
        if self._ztm_shutdown_done:  # a refresh that was still running must not write the store of an unloaded entry
            return
        payload = self._payload()
        self._store.async_delay_save(lambda: payload, 30)

    def _schedule_flip_refresh(self) -> None:
        """Ask again at 03:06 Warsaw time, when the update of the API is over (never for the City's old API, which is gone)."""
        if self.client.retired:
            return
        self._flip_unsub = async_track_point_in_utc_time(self.hass, self._flip_refresh, next_flip_refresh(dt_util.utcnow()))

    @callback
    def _flip_refresh(self, _now: datetime) -> None:
        """Ask again after the City's update is over, and arrange the next one (the timer of 03:06 repeats itself every day)."""
        self._flip_unsub = None
        self._schedule_flip_refresh()
        self.hass.async_create_task(self.async_refresh())

    @property
    def api_error(self) -> bool:
        """Whether the City's last answer was not a timetable (a rejected key, an unknown stop or line, an unknown format)."""
        return self._api_error

    def _say_kept(self) -> None:
        """Log that a failed refresh was covered by the cached timetable: said once when an outage starts, not again at every try
        (and not at all here for the City's old API, whose outage the client says once for every stop)."""
        warn = self._failures == 0 and self.client.uses_token
        _LOGGER.log(logging.WARNING if warn else logging.DEBUG, "ZTM Coordinator [%s] — timetable fetch failed; keeping cached data", self.name)

    def _note_silence(self) -> None:
        """A token's refreshes failed many times in a row: tell the user (Repairs). The City answers every rejected request like an
        outage, so a revoked token cannot be told from a City that is down; the notice says both, and goes when an answer comes."""
        if self._silent_said or not self.client.uses_token or self._failures < FAILURES_BEFORE_NOTICE:
            return
        self._silent_said = True
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            silent_issue_id(self._ref),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="silent_city",
            translation_placeholders={"line": self.line, "stop": f"{self.stop_id}/{self.stop_nr}"},  # numbers only: a name from the City would go into Markdown
        )

    def _retry_soon(self) -> None:
        """A refresh failed and the cached timetable was served instead: ask again in a few minutes, not only at the hourly tick
        (a City that was unreachable for a moment, for example right after Home Assistant started, would otherwise be left alone for an hour)."""
        if self._retry_unsub is None and not self._ztm_shutdown_done:
            self._retry_unsub = async_call_later(self.hass, min(RETRY_AFTER * 2**self._failures, MAX_RETRY_AFTER), self._retry_now)
            self._failures += 1  # an outage of hours is asked less and less often, not every five minutes

    @callback
    def _retry_now(self, _now: datetime) -> None:
        """The wait after a failed refresh is over: refresh once more (a failure schedules the next try)."""
        self._retry_unsub = None
        self.hass.async_create_task(self.async_refresh())

    def is_fresh(self, now: datetime) -> bool:
        """Whether the cached timetable is the one of the service day that ``now`` is in."""
        return self.data is not None and self.data.service_date == service_date_at(now)

    def known(self) -> list[ZTMDepartureDataReading]:
        """Every departure of the current and the previous answer (the past ones too), in order."""
        known = [d for part in (self._previous, self.data) if part for d in part.departures if d.dt]
        return sorted(known, key=lambda d: d.dt or _EPOCH)  # every one has a moment: the filter above

    def upcoming(self, now: datetime) -> list[ZTMDepartureDataReading]:
        """The departures at or after ``now`` from the current and the previous answer, in order."""
        return [d for d in self.known() if d.dt and d.dt >= now]

    def is_usable(self, now: datetime) -> bool:
        """Whether what the coordinator holds may be shown: the last refresh worked, and the timetable is today's or has
        late departures (27:xx) still ahead (an answer of an earlier service day is not today's timetable)."""
        return bool(self.last_update_success) and (self.is_fresh(now) or bool(self.upcoming(now)))


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
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="city_swapping")
        return self.data

    def _accept(self, new_data: ZTMDepartureData) -> ZTMDepartureData:
        """Make a fresh answer the current one; the answer it replaces becomes the previous one on a new service day."""
        data_changed = self._data_changed(new_data)
        if self.data is not None and self.data.service_date != new_data.service_date:
            self._previous = self.data
        self.data = new_data
        self._api_error = False
        self._rejections = 0
        self._failures = 0
        if self._silent_said:
            self._silent_said = False
            ir.async_delete_issue(self.hass, DOMAIN, silent_issue_id(self._ref))
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

    def _api_rejected(self, err: ZTMApiError) -> ZTMDepartureData:
        """The city answered but not with a timetable (a rejected key, an unknown stop or line, an answer in an unknown
        format). Unlike a network error this is not "try again later with the cached timetable": the entity becomes
        unavailable instead of pretending nothing runs. Home Assistant logs this once, when the state changes, and
        again when it recovers. Three rejected keys in a row ask the user for a new one."""
        if in_swap_window(dt_util.utcnow()):  # a request that straddles the start of the City's update
            return self._hold_during_swap()
        self._api_error = True
        self._rejections = self._rejections + 1 if isinstance(err, ZTMAuthError) else 0
        self._save()
        if self._rejections >= REJECTIONS_BEFORE_REAUTH:
            # Counted in the store, so the retries of a setup (a new coordinator each) add up.
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="city_rejected", translation_placeholders={"error": str(err)}
            ) from err
        raise UpdateFailed(
            translation_domain=DOMAIN, translation_key="city_rejected", translation_placeholders={"error": str(err)}
        ) from err

    def _outage(self) -> None:
        """A network error or an answer that is not the City's breaks a run of rejected keys; the store must know."""
        if self._rejections:
            self._rejections = 0
            self._save()

    async def _fetch(self) -> ZTMDepartureData:
        """One refresh: the City's answer, or the cached timetable while the City swaps its data (02:10-03:05) or when the request failed and no API error is pending.

        A rejected key and an answer that is not a timetable are kept apart from a network error: they raise ``ConfigEntryAuthFailed`` or ``UpdateFailed`` instead of bringing the cached timetable back, so that a failure is never shown as an empty or healthy timetable.
        """
        if in_swap_window(dt_util.utcnow()):
            return self._hold_during_swap()
        _LOGGER.debug("ZTM Coordinator [%s] — fetching new schedule data", self.name)
        try:
            new_data = await self.client.get(fetch_stop_name=self._started)  # the name is not worth the setup's deadline
            if in_swap_window(dt_util.utcnow()):  # the request began before the update did and ended inside it
                return self._hold_during_swap()
            if new_data is None:
                self._outage()
                self._note_silence()
                if self.data is not None and not self._api_error:
                    self._say_kept()
                    self._retry_soon()
                    return self.data
                raise UpdateFailed(translation_domain=DOMAIN, translation_key="no_cached_timetable")
            return self._accept(new_data)

        except (UpdateFailed, ConfigEntryAuthFailed):
            raise
        except ZTMApiError as err:
            return self._api_rejected(err)
        except Exception as err:
            if self.data is not None and not self._api_error:
                # Keep entity available with last known data; try again on next hourly tick
                _LOGGER.warning(
                    "ZTM Coordinator [%s] — fetch failed (%s); keeping last known timetable and retrying in a few minutes",
                    self.name,
                    err,
                )
                self._retry_soon()
                return self.data
            _LOGGER.error("ZTM Coordinator [%s] — failed fetching schedule and no cached data", self.name)
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="fetch_failed", translation_placeholders={"error": str(err)}
            ) from err

    async def async_shutdown(self) -> None:
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
            if self._retry_unsub:
                self._retry_unsub()
                self._retry_unsub = None
            await super().async_shutdown()
        _LOGGER.info("ZTM Coordinator [%s] — shutdown complete", self.name)
