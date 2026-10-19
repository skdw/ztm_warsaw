"""What an entry holds: the stop units it runs, however they are stored.

A version 1 entry is one stop (the stop, the pole, the line and the key all in its data). A version 2 entry is a
line: the key and the line are in its data and every stop is a subentry. Both are read as a list of ``StopUnit``,
so the setup, the platforms and the diagnostics do not care which it is.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_WALKING_TIME, DOMAIN, MAX_WALKING_TIME

_LOGGER = logging.getLogger(__name__)

SUBENTRY_STOP = "stop"
LINE_ENTRY_VERSION = 2  # the first version whose stops are subentries


def _first_nonempty(merged: Mapping[str, Any], *keys: str) -> str | None:
    """The first of ``keys`` that holds a value, as a string without surrounding spaces."""
    for k in keys:
        v = merged.get(k)
        if v is None:
            continue
        text = str(v).strip()
        if text:
            return text
    return None


def _entry_values(entry: ConfigEntry, *, log: bool = True) -> tuple[str, str, str, str] | None:
    """The (api_key, stop_id, stop_nr, line) of the entry, or None when one is missing (logged, key never named)."""
    # Merge data and options (options override data) for robustness
    merged: dict[str, Any] = {}
    if isinstance(entry.data, Mapping):
        merged.update(entry.data)
    if isinstance(entry.options, Mapping):
        merged.update(entry.options)

    api_key = _first_nonempty(merged, "api_key", "apikey", "apiKey")
    stop_id = _first_nonempty(merged, "stop_id", "busstop_id", "busstopId", "busstopID", "stopId", "zespol")
    stop_nr = _first_nonempty(merged, "stop_nr", "busstop_nr", "busstopNr", "stopNr", "slupek")
    line = _first_nonempty(merged, "line", "linia")

    if api_key is None or stop_id is None or stop_nr is None or line is None:
        if not log:
            return None
        missing = [name for name, val in [("stop_id", stop_id), ("stop_nr", stop_nr), ("line", line)] if val is None]
        if api_key is not None:
            # No sensitive field missing: safe to list them
            _LOGGER.error("Missing required config: %s", ", ".join(missing))
        else:
            # The key is missing: keep ERROR generic and never name or print sensitive fields
            _LOGGER.error("Missing required configuration. Please reconfigure this integration.")
            _LOGGER.debug(
                "Some required fields are missing (at least one is sensitive). Provided non-sensitive keys: %s",
                ", ".join(sorted(k for k in merged if k not in ("api_key", "apikey", "apiKey"))),
            )
        return None
    return api_key, stop_id, stop_nr, line


def is_line_entry(entry: ConfigEntry) -> bool:
    """A version 2 entry: a line with its stops as subentries."""
    return entry.version >= LINE_ENTRY_VERSION


def _merged(entry: ConfigEntry) -> dict[str, Any]:
    """The data of the entry with its options on top (an option overrides the data), as the setup of 1.1.x read it."""
    merged: dict[str, Any] = {}
    if isinstance(entry.data, Mapping):
        merged.update(entry.data)
    if isinstance(entry.options, Mapping):
        merged.update(entry.options)
    return merged


@dataclass(frozen=True)
class StopUnit:
    """One line at one pole with the key that asks for it: what a coordinator and its sensors are made for."""

    entry_id: str
    subentry_id: str | None  # None for a version 1 entry, where the entry itself is the stop
    api_key: str
    stop_id: str
    stop_nr: str
    line: str
    walking_minutes: int = 0  # how long the way to the stop takes: a departure sooner than that cannot be caught

    @property
    def ref(self) -> str:
        """What names this unit's stored answers: the subentry, or the entry of a version 1 stop."""
        return self.subentry_id or self.entry_id


def walking_minutes_of(data: Mapping[str, Any]) -> int:
    """The walking time stored for a stop: a whole number of minutes from 0 to ``MAX_WALKING_TIME``, else 0 (none)."""
    value = data.get(CONF_WALKING_TIME)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
        return 0
    return int(value) if 0 <= value <= MAX_WALKING_TIME else 0


def stop_units(entry: ConfigEntry) -> list[StopUnit]:
    """The stops of the entry that can be run (an incomplete one is left out)."""
    if not is_line_entry(entry):
        values = _entry_values(entry, log=False)
        return [] if values is None else [StopUnit(entry.entry_id, None, *values)]
    merged = _merged(entry)
    api_key = _first_nonempty(merged, "api_key", "apikey", "apiKey")
    line = _first_nonempty(merged, "line", "linia")
    if api_key is None or line is None:
        return []
    units = []
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_STOP:
            continue
        stop_id = _first_nonempty(subentry.data, "busstop_id", "stop_id")
        stop_nr = _first_nonempty(subentry.data, "busstop_nr", "stop_nr")
        if stop_id is not None and stop_nr is not None:
            units.append(StopUnit(entry.entry_id, subentry_id, api_key, stop_id, stop_nr, line, walking_minutes_of(subentry.data)))
    return units


def stop_keys(entry: ConfigEntry) -> set[tuple[str, str, str]]:
    """What makes two stops the same sensor: the stop, the pole and the line, as the sensor's unique ID is built from them."""
    return {(unit.stop_id, unit.stop_nr, unit.line) for unit in stop_units(entry)}


def entry_api_key(entry: ConfigEntry) -> str | None:
    """The key or token of the entry, whichever way it is stored (a version 2 entry may have no stop yet)."""
    return _first_nonempty(_merged(entry), "api_key", "apikey", "apiKey")


def line_of(entry: ConfigEntry) -> str | None:
    """The line of a version 2 entry."""
    return _first_nonempty(_merged(entry), "line", "linia") if is_line_entry(entry) else None


def runtimes(hass: HomeAssistant, entry: ConfigEntry) -> dict[str | None, dict]:
    """The running coordinators of a loaded entry by subentry id (None for a version 1 entry)."""
    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not isinstance(stored, dict):
        return {}
    if "units" in stored:
        return dict(stored["units"])
    return {None: stored} if "coordinator" in stored else {}
