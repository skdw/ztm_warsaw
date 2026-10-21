"""Diagnostics download: what a maintainer needs to understand a report, and never the API key or token."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .client import key_kind
from .coordinator import ZTMStopCoordinator
from .entries import entry_api_key, is_line_entry, runtimes
from .models import ZTMDepartureData
from .runtime import ZtmConfigEntry

# Every spelling of the key the setup accepts (see entries.py); the value of each is replaced.
TO_REDACT = {"api_key", "apikey", "apiKey"}
REDACTED = "**REDACTED**"


def _redact(data: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of the mapping with the value of every key spelling replaced (no import of the diagnostics component)."""
    return {k: REDACTED if k in TO_REDACT else v for k, v in dict(data).items()}


def _secrets(entry: ConfigEntry) -> set[str]:
    """The credentials of the entry, and the parts of a token, so that they can be removed wherever they appear."""
    found: set[str] = set()
    for source in (entry.data, entry.options):
        for name in TO_REDACT:
            value = str(source.get(name) or "").strip()
            if value:
                found.add(value)
                found.update(part for part in value.split(".") if len(part) >= 8)
    return found


def _scrub(value: Any, secrets: set[str]) -> Any:
    """The same structure with every credential removed from every string in it (a title a user has renamed, say)."""
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, REDACTED)
        return value
    if isinstance(value, dict):
        return {k: _scrub(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v, secrets) for v in value]
    return value


def _stop_name(info: object) -> str | None:
    """The name of a stop for the diagnostics: a string of at most 100 characters, or None."""
    name = info.get("nazwa_zespolu") if isinstance(info, dict) else None
    return str(name)[:100] if name else None


def _answer(data: ZTMDepartureData | None) -> dict[str, Any] | None:
    """The shape of a timetable answer: its service day, how many departures and the first few labels."""
    if data is None:
        return None
    return {
        "service_date": data.service_date.isoformat() if data.service_date else None,
        "departures": len(data.departures),
        "first_labels": [d.czas for d in data.departures[:3]],
        "stop_name": _stop_name(data.stop_info),
    }


def _coordinator_state(coordinator: ZTMStopCoordinator) -> dict[str, Any]:
    """The state of one coordinator as plain data: how its last refresh went (the class of an error, never its text), the failure marker and the answers it holds."""
    error = coordinator.last_exception
    return {
        "last_update_success": coordinator.last_update_success,
        "last_update_success_time": (
            coordinator.last_update_success_time.isoformat() if coordinator.last_update_success_time else None
        ),
        "last_exception": type(error).__name__ if error else None,  # the class only: a text could carry the URL
        "api_error": coordinator._api_error,
        "rejections_in_a_row": coordinator._rejections,
        "current": _answer(coordinator.data),
        "previous": _answer(coordinator._previous),
    }


# Home Assistant awaits this platform function, so it has to be a coroutine function although it only reads memory.
async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ZtmConfigEntry) -> dict[str, Any]:  # NOSONAR
    """The entry (key redacted) and the state of its coordinators, as plain data."""
    running = runtimes(entry)
    api_key = entry_api_key(entry)
    result: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "state": entry.state.value,
            "data": _redact(entry.data),
            "options": _redact(entry.options),
        },
        "key_kind": key_kind(api_key) if api_key else None,
    }
    if is_line_entry(entry):
        result["stops"] = [
            {
                "title": subentry.title,
                "data": dict(subentry.data),
                "coordinator": (
                    _coordinator_state(running[sid]["coordinator"]) if sid in running else None
                ),
            }
            for sid, subentry in entry.subentries.items()
        ]
    else:
        stop = running.get(None)
        result["coordinator"] = _coordinator_state(stop["coordinator"]) if stop is not None else None
    return cast("dict[str, Any]", _scrub(result, _secrets(entry)))
