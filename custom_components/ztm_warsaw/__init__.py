from __future__ import annotations
# Import ZTMStopCoordinator which handles periodic fetching of departure data
from .coordinator import ZTMStopCoordinator

import logging
from datetime import timedelta

# Home Assistant core types and helpers
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

# Client that communicates with the ZTM API
from .client import ZTMStopClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZTM Warsaw from a config entry."""
    # Build a per-entry DataUpdateCoordinator that caches the full timetable for 24 h
    hass.data.setdefault(DOMAIN, {})

    # Prepare aiohttp session for the ZTM client
    session = async_get_clientsession(hass)

    # Extract necessary data from the config entry
    api_key = entry.data.get("api_key")
    stop_id = entry.data["busstop_id"]
    stop_nr = entry.data["busstop_nr"]
    line = entry.data.get("line")

    # Initialize the API client with credentials and stop details
    client = ZTMStopClient(session, api_key, stop_id, stop_nr, line)

    # Create the data coordinator, responsible for scheduling API updates
    coordinator = ZTMStopCoordinator(
        hass,
        client=client,
        stop_id=stop_id,
        stop_nr=stop_nr,
        line=line,
        update_interval=timedelta(hours=1)
    )

    # Trigger the first data fetch immediately
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Ensure the integration reloads when options are updated
    entry.async_on_unload(entry.add_update_listener(_update_listener))
    # Forward the setup to the sensor platform
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