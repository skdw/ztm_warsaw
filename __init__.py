"""ZTM Warsaw integration."""
from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZTM Warsaw from a config entry."""
    entry.async_on_unload(entry.add_update_listener(_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ZTM Warsaw config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")

@callback
async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)