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
from .coordinator import ZTMStopCoordinator

_LOGGER = logging.getLogger(__name__)


def _entry_values(entry: ConfigEntry) -> tuple[str, str, str, str] | None:
    """The (api_key, stop_id, stop_nr, line) of the entry, or None when one is missing (logged, key never named)."""
    # Merge data and options (options override data) for robustness
    merged: dict[str, Any] = {}
    if isinstance(entry.data, Mapping):
        merged.update(entry.data)
    if isinstance(entry.options, Mapping):
        merged.update(entry.options)

    def _first_nonempty(*keys: str) -> str | None:
        for k in keys:
            v = merged.get(k)
            if v is None:
                continue
            # Normalize to string, strip spaces
            s = str(v).strip()
            if s:
                return s
        return None

    api_key = _first_nonempty("api_key", "apikey", "apiKey")
    stop_id = _first_nonempty("stop_id", "busstop_id", "busstopId", "busstopID", "stopId", "zespol")
    stop_nr = _first_nonempty("stop_nr", "busstop_nr", "busstopNr", "stopNr", "slupek")
    line = _first_nonempty("line", "linia")

    if api_key is None or stop_id is None or stop_nr is None or line is None:
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
    )

    # Do not block setup on a transient API failure
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # noqa: BLE001 - surface initial error but continue
        _LOGGER.warning(
            "Initial fetch failed for %s/%s line %s: %s", stop_id, stop_nr, line, err
        )

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options_change))
    return True


async def _async_reload_on_options_change(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


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