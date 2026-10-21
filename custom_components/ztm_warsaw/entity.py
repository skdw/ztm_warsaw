"""What the entities of a stop have in common: the device they are on, the stop's record, the timetable link, and the base class.

Every entity of a stop (the sensor, its status, its diagnostic sensor, the next departures and the calendar) is on the device of
that stop, reads the stop's record from the same coordinator and takes the stop's name into its own name once the City has given
it. Those are here, once, instead of in each platform.
"""

from datetime import datetime, timezone
from urllib.parse import quote

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZTMStopCoordinator
from .models import WARSAW
from .utils import get_line_type


def stop_info_of(coordinator):
    """The stop's record from the coordinator's data, or {}."""
    try:
        if coordinator and coordinator.data:
            return getattr(coordinator.data, "stop_info", {}) or {}
    except (AttributeError, TypeError):
        pass
    return {}


def timetable_url(line):
    """The timetable page of the line for today."""
    try:
        today_str = datetime.now(tz=timezone.utc).astimezone(WARSAW).strftime("%Y-%m-%d")
        return f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt={today_str}&wtp_md=3&wtp_ln={quote(str(line))}"
    except Exception:
        return f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_md=3&wtp_ln={quote(str(line))}"


def device_info(line, coordinator=None):
    """The device of a stop's entities. A stop of a 1.1.x entry (one entry per stop) is the line's device, shared by the
    entries of that line; the stops of a line entry each have their own device, because a device belongs to one subentry."""
    identifier, name = f"line_{line}", f"Line {line}"
    if getattr(coordinator, "device_per_stop", False):
        # Named like the line's device: Home Assistant 2026.10 puts the device's name in front of an entity's name (and
        # of its ID) unless the entity's name starts with it, and ours always start with "Line <line>". The devices of the
        # stops are told apart by the subentry they are listed under.
        identifier = f"line_{line}_{coordinator.stop_id}_{coordinator.stop_nr}"
    return {
        "identifiers": {(DOMAIN, identifier)},
        "name": name,
        "manufacturer": "Zarząd Transportu Miejskiego",
        "entry_type": "service",
        "model": get_line_type(line),
        "configuration_url": timetable_url(line),
    }



class ZtmStopEntity(CoordinatorEntity[ZTMStopCoordinator]):
    """An entity of one stop (a line at a pole): it knows its line and pole, sits on the stop's device and can read the stop's record."""

    def __init__(self, coordinator: ZTMStopCoordinator, line: str, stop_number: str):
        """Remember the line and the pole of the stop the coordinator serves."""
        super().__init__(coordinator)
        self._line = line
        self._stop_number = stop_number

    @property
    def device_info(self):
        """The device of the stop, as every entity of the stop has it."""
        return device_info(self._line, self.coordinator)

    def _stop_info(self):
        """The stop's record from the coordinator (its name, position, street ...); an empty dict until the City has given it."""
        return stop_info_of(self.coordinator)

    def _name_with_stop(self, suffix):
        """The entity's name with the stop's name in it ("Line 176 Marcelin 01 Status"), or None until the name is known (the entity ID was made from the numbers)."""
        stop_name = self._stop_info().get("nazwa_zespolu")
        return f"Line {self._line} {stop_name} {self._stop_number} {suffix}" if stop_name else None
