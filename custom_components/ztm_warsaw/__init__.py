"""Home Assistant setup for the Warsaw Public Transport custom integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from collections.abc import Mapping

from .const import DOMAIN, PLATFORMS
from .client import ZTMStopClient, user_agent
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from .coordinator import ZTMStopCoordinator, store_key

_LOGGER = logging.getLogger(__name__)


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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    values = _entry_values(entry)
    if values is None:
        return False
    api_key, stop_id, stop_nr, line = values

    session = async_get_clientsession(hass)

    client = ZTMStopClient(
        session=session,
        user_agent=await user_agent(hass),
        api_key=api_key,
        stop_id=stop_id,
        stop_number=stop_nr,
        line=line,
    )

    coordinator = ZTMStopCoordinator(
        hass=hass,
        client=client,
        stop_id=stop_id,
        stop_nr=stop_nr,
        line=line,
        entry_id=entry.entry_id,
    )

    # Raises ConfigEntryNotReady when the City does not answer: Home Assistant then retries the setup by itself.
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    _update_duplicate_issue(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    seen = (dict(entry.data), dict(entry.options))

    async def _reload_if_changed(hass: HomeAssistant, changed: ConfigEntry) -> None:
        """Reload when the data or the options differ from the ones this setup used (a rename or such does not)."""
        if (dict(changed.data), dict(changed.options)) != seen:
            await hass.config_entries.async_reload(changed.entry_id)

    entry.async_on_unload(entry.add_update_listener(_reload_if_changed))
    return True


def stop_key(entry: ConfigEntry) -> tuple[str, str, str] | None:
    """What makes two entries the same sensor: the stop, the pole and the line, as the sensor's unique ID is built from them."""
    values = _entry_values(entry, log=False)
    return None if values is None else (values[1], values[2], values[3])


def _duplicate_issue_id(entry: ConfigEntry) -> str:
    return f"duplicate_{entry.entry_id}"


def _update_duplicate_issue(hass: HomeAssistant, entry: ConfigEntry, removed: str | None = None) -> None:
    """Tell the user (Repairs) when another entry already covers the same stop, pole and line; the second sensor of
    such a pair cannot exist, and removing one of the entries is the user's call."""
    key = stop_key(entry)
    earlier = []  # the entries added before this one: the first of a pair keeps its sensor, the later one has none
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id == entry.entry_id:
            break
        if other.entry_id != removed:  # Home Assistant before 2026.10 still lists an entry while it is being removed
            earlier.append(other)
    twin = key is not None and any(stop_key(other) == key for other in earlier)
    if key is not None and twin:
        ir.async_create_issue(
            hass,
            DOMAIN,
            _duplicate_issue_id(entry),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="duplicate_entry",
            translation_placeholders={"line": key[2], "stop": f"{key[0]}/{key[1]}"},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, _duplicate_issue_id(entry))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    stored = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if isinstance(stored, dict):
        coord = stored.get("coordinator")
    elif isinstance(stored, ZTMStopCoordinator):
        coord = stored
    else:
        coord = None
    if coord:
        try:
            await coord.async_shutdown()
        except Exception:  # noqa: BLE001 - shutdown should not crash unload
            _LOGGER.debug("Coordinator shutdown raised; ignoring", exc_info=True)

    if not hass.data.get(DOMAIN):
        hass.data.pop(DOMAIN, None)

    return unload_ok

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the answers stored for a removed entry, and the notice about it or about its twin."""
    await Store(hass, 1, store_key(entry.entry_id)).async_remove()
    ir.async_delete_issue(hass, DOMAIN, _duplicate_issue_id(entry))
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id != entry.entry_id:
            _update_duplicate_issue(hass, other, removed=entry.entry_id)
