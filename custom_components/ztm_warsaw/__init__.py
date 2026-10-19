"""Home Assistant setup for the Warsaw Public Transport custom integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from collections.abc import Mapping

from .const import DOMAIN, PLATFORMS
from .client import StopCatalogue, ZTMStopClient, key_kind, user_agent
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from .coordinator import ZTMStopCoordinator, store_key

_LOGGER = logging.getLogger(__name__)
_NAME_LENGTH = 60
KEY_PORTAL_URL = "https://dane.um.warszawa.pl/pl/key-api"


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
        catalogue=hass.data.setdefault(f"{DOMAIN}_catalogue", StopCatalogue()),  # one for all the entries
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

    _update_legacy_issue(hass, entry)  # before the first load: an entry that fails to load needs the hint most
    # Raises ConfigEntryNotReady when the City does not answer: Home Assistant then retries the setup by itself.
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    def _show_stop_name() -> None:
        _update_duplicate_issue(hass, entry)
        _update_legacy_issue(hass, entry)  # again, now that the stop's name is known
        _use_stop_name_in_title(hass, entry, values)

    _show_stop_name()
    named = _stop_name_of(hass, entry) is not None

    def _on_update() -> None:
        """The name can arrive after the setup (the catalogue failed once and a later refresh got it): show it then."""
        nonlocal named
        if not named and _stop_name_of(hass, entry) is not None:
            named = True
            _show_stop_name()

    if not named:
        entry.async_on_unload(coordinator.async_add_listener(_on_update))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    seen = (dict(entry.data), dict(entry.options))

    async def _reload_if_changed(hass: HomeAssistant, changed: ConfigEntry) -> None:
        """Reload when the data or the options differ from the ones this setup used (a rename or such does not)."""
        if (dict(changed.data), dict(changed.options)) != seen:
            await hass.config_entries.async_reload(changed.entry_id)

    entry.async_on_unload(entry.add_update_listener(_reload_if_changed))
    return True


def _stop_name_of(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """The stop's name, once the entry has loaded and the City has given it (the coordinator holds it)."""
    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    coordinator = stored.get("coordinator") if isinstance(stored, dict) else None
    info = getattr(getattr(coordinator, "data", None), "stop_info", None)
    name = info.get("nazwa_zespolu") if isinstance(info, dict) else None
    if not isinstance(name, str):
        return None
    tidy = " ".join(name.split())[:_NAME_LENGTH]  # one line, not longer than a stop's name can sensibly be
    return tidy or None


def _stop_text(stop_id: str, pole: str, name: str | None) -> str:
    """How a notice names the stop: "Marcelin 15 (1085/15)", or just the numbers while the name is not known."""
    if not name:
        return f"{stop_id}/{pole}"
    # The name comes from the City and goes into a Markdown text: keep letters, digits, spaces, hyphens, commas and
    # apostrophes, and a dot only before a space, so nothing in it can format a line or become a link.
    plain = re.sub(r"\.(?=\S)", "", re.sub(r"[^\w\s.,'-]", "", " ".join(name.split()).replace("_", ""))).strip()
    return f"{plain} {pole} ({stop_id}/{pole})" if plain else f"{stop_id}/{pole}"


def _use_stop_name_in_title(hass: HomeAssistant, entry: ConfigEntry, values: tuple[str, str, str, str]) -> None:
    """Title an entry "Line 176 from Marcelin 15" instead of "Line 176 from 1085/15", unless the user gave it their own."""
    _, stop_id, pole, line = values
    name = _stop_name_of(hass, entry)
    if name and entry.title == f"Line {line} from {stop_id}/{pole}":
        hass.config_entries.async_update_entry(entry, title=f"Line {line} from {name} {pole}")


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
            translation_placeholders={"line": key[2], "stop": _stop_text(key[0], key[1], _stop_name_of(hass, entry))},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, _duplicate_issue_id(entry))


def _update_legacy_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """A notice (Repairs, can be dismissed) for an entry that still uses a key of the City's old API: it works, but the
    City publishes no date for its end and the token of the new API is its current service. Configure changes the key."""
    values = _entry_values(entry, log=False)
    issue_id = f"legacy_key_{entry.entry_id}"
    if values is not None and key_kind(values[0]) == "legacy":
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="legacy_key",
            translation_placeholders={
                "line": values[3],
                "stop": _stop_text(values[1], values[2], _stop_name_of(hass, entry)),
                "portal": KEY_PORTAL_URL,  # hassfest wants no URL inside a translated text
            },
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


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
    ir.async_delete_issue(hass, DOMAIN, f"legacy_key_{entry.entry_id}")
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id != entry.entry_id:
            _update_duplicate_issue(hass, other, removed=entry.entry_id)
