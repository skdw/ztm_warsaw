"""The timetable as a calendar: every departure of the line at the pole is an event of one minute.

A calendar entity shows the whole day in Home Assistant's calendar view and works with its calendar trigger,
which starts an automation at an event or at an offset from it: "eight minutes before a departure" needs no
template. The events are the departures the coordinator already holds (the current service day and the late
departures of the previous one); nothing more is asked of the City.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entries import runtimes
from .coordinator import ZTMStopCoordinator
from .entity import ZtmStopEntity, stop_info_of as _stop_info_of
from .models import ZTMDepartureDataReading
from .runtime import ZtmConfigEntry

PARALLEL_UPDATES = 0  # the entity only reads what its coordinator fetched: nothing to limit


EVENT_LENGTH = timedelta(minutes=1)


# Home Assistant awaits the platform's setup function, so it has to be a coroutine function although it awaits nothing.
async def async_setup_entry(hass: HomeAssistant, config_entry: ZtmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:  # NOSONAR
    """Add the timetable calendar of every stop the entry runs (disabled by default, see the class)."""
    for subentry_id, runtime in runtimes(config_entry).items():
        async_add_entities([ZTMCalendar(runtime["coordinator"])], config_subentry_id=subentry_id)


class ZTMCalendar(ZtmStopEntity, CalendarEntity):
    """The departures of one line at one pole, as calendar events."""

    # Off by default: a calendar is a lot of events (every departure of the day), and it is for those who want them.
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ZTMStopCoordinator):
        """Name the calendar after its stop and put it on the device of that stop, as the sensors are."""
        line, stop_id, stop_nr = coordinator.line, coordinator.stop_id, coordinator.stop_nr
        super().__init__(coordinator, line, stop_nr)
        self._attr_unique_id = f"line_{line}_from_{stop_id}_{stop_nr}_calendar"
        self._attr_translation_key = "timetable"  # its icon is in icons.json

    def _event_of(self, departure: ZTMDepartureDataReading) -> CalendarEvent:
        """One departure as a calendar event of ``EVENT_LENGTH``: ``<line> → <headsign>``, the brigade as the description, the stop's name as the place."""
        headsign = departure.kierunek if departure.kierunek not in (None, "", "unknown") else None
        stop_name = _stop_info_of(self.coordinator).get("nazwa_zespolu")
        start = departure.dt
        if start is None:  # a reading without a moment is never an event (the callers have filtered those out)
            raise ValueError("a departure without a moment is not a calendar event")
        return CalendarEvent(
            start=start,
            end=start + EVENT_LENGTH,
            summary=f"{self.coordinator.line} → {headsign}" if headsign else f"{self.coordinator.line}",
            description=f"Brigade {departure.brygada}" if departure.brygada else None,
            location=str(stop_name) if stop_name else None,
        )

    @property
    def available(self) -> bool:
        """The calendar is available while the coordinator holds a timetable that may be shown (see ``is_usable``)."""
        return self.coordinator.is_usable(dt_util.utcnow())

    @property
    def event(self) -> CalendarEvent | None:
        """The next departure (or the one of this minute)."""
        now = dt_util.utcnow()
        if not self.coordinator.is_usable(now):
            return None
        upcoming = self.coordinator.upcoming(now - EVENT_LENGTH + timedelta(microseconds=1))
        return self._event_of(upcoming[0]) if upcoming else None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        """The departures of the held timetable (the current service day and the one before it) that fall between the
        two moments, past ones included. Nothing while the sensor is unavailable: the calendar trigger and the services
        call this directly, and a timetable the sensor refuses to vouch for must not start automations."""
        if not self.coordinator.is_usable(dt_util.utcnow()):
            return []
        seen: set[tuple[datetime | None, str, str | None]] = set()
        events = []
        for departure in self.coordinator.known():
            key = (departure.dt, departure.kierunek, departure.brygada)
            if departure.dt is None or key in seen or not (departure.dt < end_date and departure.dt + EVENT_LENGTH > start_date):
                continue
            seen.add(key)  # the same reading twice would start an automation twice
            events.append(self._event_of(departure))
        return events
