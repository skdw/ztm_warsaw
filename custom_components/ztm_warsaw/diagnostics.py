"""Diagnostics download: what a maintainer needs to understand a report, and never the API key or token."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .client import key_kind
from .const import DOMAIN
from . import _entry_values

# Every spelling of the key the setup accepts (see _entry_values); the value of each is replaced.
TO_REDACT = {"api_key", "apikey", "apiKey"}
REDACTED = "**REDACTED**"


def _redact(data) -> dict[str, Any]:
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


def _stop_name(info) -> str | None:
    name = info.get("nazwa_zespolu") if isinstance(info, dict) else None
    return str(name)[:100] if name else None


def _answer(data) -> dict[str, Any] | None:
    """The shape of a timetable answer: its service day, how many departures and the first few labels."""
    if data is None:
        return None
    return {
        "service_date": data.service_date.isoformat() if data.service_date else None,
        "departures": len(data.departures),
        "first_labels": [d.czas for d in data.departures[:3]],
        "stop_name": _stop_name(data.stop_info),
    }


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """The entry (key redacted) and the state of its coordinator, as plain data."""
    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    coordinator = stored.get("coordinator") if isinstance(stored, dict) else None
    values = _entry_values(entry, log=False)
    state: dict[str, Any] | None = None
    if coordinator is not None:
        error = coordinator.last_exception
        state = {
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
    result = {
        "entry": {
            "title": entry.title,
            "state": entry.state.value,
            "data": _redact(entry.data),
            "options": _redact(entry.options),
        },
        "key_kind": key_kind(values[0]) if values else None,
        "coordinator": state,
    }
    return _scrub(result, _secrets(entry))
