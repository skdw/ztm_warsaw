"""What the entities of a stop have in common: the device they are on, the stop's record, the timetable link, and the base class.

Every entity of a stop (the sensor, its status, its diagnostic sensor, the next departures and the calendar) is on the device of
that stop, reads the stop's record from the same coordinator and takes the stop's name into its own name once the City has given
it. Those are here, once, instead of in each platform.
"""

import math
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZTMStopCoordinator
from .models import WARSAW
from .utils import get_line_type


def stop_info_of(coordinator: ZTMStopCoordinator | None) -> dict[str, Any]:
    """The stop's record from the coordinator's data, or {}."""
    try:
        if coordinator and coordinator.data:
            return getattr(coordinator.data, "stop_info", {}) or {}
    except (AttributeError, TypeError):
        pass
    return {}


def stop_place(info: dict[str, Any]) -> tuple[float, float] | None:
    """The latitude and longitude in a stop's record, or None when it is not a real place (a NaN or a value out of range would
    make every update look like a change, or put a pin in the sea and a distance of nothing)."""
    try:
        latitude, longitude = float(info["szer_geo"]), float(info["dlug_geo"])
    except (KeyError, TypeError, ValueError):
        return None
    if math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180:
        return latitude, longitude
    return None


def timetable_url(line: str) -> str:
    """The timetable page of the line for today."""
    try:
        today_str = datetime.now(tz=timezone.utc).astimezone(WARSAW).strftime("%Y-%m-%d")
        return f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_dt={today_str}&wtp_md=3&wtp_ln={quote(str(line))}"
    except Exception:
        return f"https://www.wtp.waw.pl/rozklady-jazdy/?wtp_md=3&wtp_ln={quote(str(line))}"


def device_info(line: str, coordinator: ZTMStopCoordinator | None = None) -> DeviceInfo:
    """The device of a stop's entities. A stop of a 1.1.x entry (one entry per stop) is the line's device, shared by the
    entries of that line; the stops of a line entry each have their own device, because a device belongs to one subentry."""
    identifier, name = f"line_{line}", f"Line {line}"
    if coordinator is not None and coordinator.device_per_stop:
        # Named like the line's device: the entities' names ("from <stop>") follow the device's name, which gives the same
        # names and entity IDs as before. The devices of the stops are told apart by the subentry they are listed under.
        identifier = f"line_{line}_{coordinator.stop_id}_{coordinator.stop_nr}"
    return {
        "identifiers": {(DOMAIN, identifier)},
        "name": name,
        "manufacturer": "Zarząd Transportu Miejskiego",
        "entry_type": DeviceEntryType.SERVICE,
        "model": get_line_type(line),
        "configuration_url": timetable_url(line),
    }



class ZtmStopEntity(CoordinatorEntity[ZTMStopCoordinator]):
    """An entity of one stop (a line at a pole): it knows its line and pole, sits on the stop's device and can read the stop's record."""

    # The entity's name is a translation ("{stop}", "{stop} Status" ...) on the device of the line ("Line 176").
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZTMStopCoordinator, line: str, stop_number: str):
        """Remember the line and the pole of the stop the coordinator serves."""
        super().__init__(coordinator)
        self._line = line
        self._stop_number = stop_number
        self._attr_translation_placeholders = self._numbers_placeholders()

    @property
    def device_info(self) -> DeviceInfo:
        """The device of the stop, as every entity of the stop has it."""
        return device_info(self._line, self.coordinator)

    def _stop_info(self) -> dict[str, Any]:
        """The stop's record from the coordinator (its name, position, street ...); an empty dict until the City has given it."""
        return stop_info_of(self.coordinator)

    async def async_added_to_hass(self) -> None:
        """Follow the stop's name from now on: the entity ID is made, so the stop's name may stand in for the numbers in the
        entity's name (the listener is added first, so the name is renewed before the entity writes its state)."""
        self.async_on_remove(self.coordinator.async_add_listener(self._renew_name))
        self._renew_name()
        await super().async_added_to_hass()

    @callback
    def _renew_name(self) -> None:
        """Put the stop's name into the entity's name once the City has given it. Home Assistant keeps the name it worked out
        once, so the cached name is dropped when the placeholder changes (only the friendly name changes, the entity ID stays)."""
        stop_name = self._stop_info().get("nazwa_zespolu")
        if stop_name:
            placeholders = {"stop": f"{stop_name} {self._stop_number}"}
        else:
            placeholders = self._numbers_placeholders()
        if placeholders != self._attr_translation_placeholders:
            self._attr_translation_placeholders = placeholders
            self.__dict__.pop("name", None)

    def _numbers_placeholders(self) -> dict[str, str]:
        """``{stop}`` of the entity's name before the stop's name is known: "from" and the numbers ("from 7009/01"). The entity
        ID is made from this and the English name, so it is the same in every language and as it has always been."""
        return {"stop": f"from {self.coordinator.stop_id}/{self._stop_number}"}
