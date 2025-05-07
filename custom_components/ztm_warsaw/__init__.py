"""ZTM Warsaw integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ZTMStopClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZTM Warsaw from a config entry."""
    # Build a per-entry DataUpdateCoordinator that caches the full timetable for 24 h
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)

    api_key = entry.data.get("api_key")
    stop_id = entry.data["busstop_id"]
    stop_nr = entry.data["busstop_nr"]
    line = entry.data.get("line")

    client = ZTMStopClient(session, api_key, stop_id, stop_nr, line)

    async def _async_update_data():
        """Fetch full timetable once a day and cache it."""
        try:
            return await client.get()  # returns list[ZTMDepartureDataReading]
        except Exception as err:
            raise UpdateFailed(err) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"ztm_{stop_id}_{line}",
        update_method=_async_update_data,
        update_interval=timedelta(hours=1),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ZTM Warsaw config entry."""
    result = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return result

@callback
async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)