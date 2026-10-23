"""Home Assistant setup for the Warsaw Public Transport custom integration."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, KEY_PORTAL_URL, PLATFORMS, legacy_api_retired
from .client import StopCatalogue, ZTMStopClient, key_kind, user_agent
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from .coordinator import ZTMStopCoordinator, silent_issue_id, store_key
from .migration import async_migrate_to_lines, merged_keys_issue_id
from .runtime import RuntimeData, StopRuntime, ZtmConfigEntry
from .entries import (  # noqa: F401 - _entry_values and stop_key are used by the config flow and the diagnostics
    StopUnit,
    _entry_values,
    _first_nonempty,
    entry_api_key,
    is_line_entry,
    line_of,
    runtimes,
    stop_keys,
    stop_units,
)

_LOGGER = logging.getLogger(__name__)
_NAME_LENGTH = 60

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


# Home Assistant awaits this function with these two arguments, so it has to be a coroutine function that takes both.
async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:  # NOSONAR
    """Before any entry is set up: the entries of 1.1.x (one stop each) become lines (see migration.py)."""
    await async_migrate_to_lines(hass)
    return True


# Home Assistant awaits this function with these two arguments, so it has to be a coroutine function that takes both.
async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # NOSONAR
    """A version 1 entry (one stop) that the conversion into a line left (it cannot be read, or its line could not be
    grouped) keeps working as it is; the line entry of version 2 is what the conversion and new setups make."""
    return entry.version <= 2


async def _first_refresh(coordinators: list[ZTMStopCoordinator]) -> None:
    """Raises ConfigEntryNotReady when the City answers for none of the stops: Home Assistant then retries the setup by
    itself and stops the coordinators of the entry (each one is registered for it). The stops of a line ask together;
    when only some answer, the line starts and the others catch up with their hourly refresh."""
    if len(coordinators) == 1:
        await coordinators[0].async_config_entry_first_refresh()
        return
    results = await asyncio.gather(*(c.async_config_entry_first_refresh() for c in coordinators), return_exceptions=True)
    failures = [r for r in results if isinstance(r, BaseException)]
    for failure in failures:  # the key is rejected, or the setup itself was cancelled: that is the entry's, not one stop's
        if isinstance(failure, (ConfigEntryAuthFailed, asyncio.CancelledError)):
            raise failure
    if failures and len(failures) == len(coordinators):
        raise failures[0]
    for coordinator, result in zip(coordinators, results):  # a stop the City does not answer for does not hold back the others
        if isinstance(result, BaseException):
            coordinator.start_without_timetable()


async def async_setup_entry(hass: HomeAssistant, entry: ZtmConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    if not is_line_entry(entry) and _entry_values(entry) is None:
        return False  # said in the log, without the key
    units = stop_units(entry)

    session = async_get_clientsession(hass)
    agent = await user_agent(hass)
    catalogue = hass.data.setdefault(f"{DOMAIN}_catalogue", StopCatalogue())  # one for all the entries

    built: dict[str | None, StopRuntime] = {}
    for unit in units:
        client = ZTMStopClient(
            session=session,
            user_agent=agent,
            catalogue=catalogue,
            api_key=unit.api_key,
            stop_id=unit.stop_id,
            stop_number=unit.stop_nr,
            line=unit.line,
        )
        coordinator = ZTMStopCoordinator(
            hass=hass,
            client=client,
            stop_id=unit.stop_id,
            stop_nr=unit.stop_nr,
            line=unit.line,
            entry_id=unit.ref,
        )
        coordinator.device_per_stop = unit.subentry_id is not None  # a line's stops are devices of their own
        coordinator.walking_minutes = unit.walking_minutes
        built[unit.subentry_id] = {"coordinator": coordinator, "client": client}

    if any(rt["client"].retired for rt in built.values()) and not catalogue.old_api_said:
        catalogue.old_api_said = True  # once for all the lines of this instance
        _LOGGER.warning(
            "A key for the City of Warsaw's old API is in use, and that API has stopped working: the line gets no new timetable "
            "until the key is replaced with a token (see the notices in Settings > Repairs)"
        )
    if any(rt["client"].retired for rt in built.values()):
        _title_line_plainly(hass, entry)  # the reauth notice is named after the title: "Line 151", not the stops
        entry.async_start_reauth(hass)  # the line says on the integration page that its key has to be replaced (a flow already open is not doubled)
    _update_legacy_issue(hass, entry)  # before the first load: an entry that fails to load needs the hint most
    await _first_refresh([rt["coordinator"] for rt in built.values()])

    # A version 1 entry keeps the shape it always had; a line has its stops by subentry.
    runtime: RuntimeData = {"units": built} if is_line_entry(entry) else built[None]
    entry.runtime_data = runtime

    def _show_stop_names() -> None:
        """Show everything that depends on a stop's name: the notices, and the titles of the entry and of its stops.

        Called once after the setup, and again when a name arrives later (the catalogue failed once and a later refresh got it).
        """
        _update_duplicate_issue(hass, entry)
        _update_legacy_issue(hass, entry)  # again, now that the stop's name is known
        _use_stop_name_in_title(hass, entry)

    _show_stop_names()
    waiting = {sid for sid in built if _stop_name_of(entry, sid) is None}

    def _on_update() -> None:
        """A name can arrive after the setup (the catalogue failed once and a later refresh got it): show it then."""
        arrived = {sid for sid in waiting if _stop_name_of(entry, sid) is not None}
        if arrived:
            waiting.difference_update(arrived)
            _show_stop_names()

    for sid in waiting:
        entry.async_on_unload(built[sid]["coordinator"].async_add_listener(_on_update))
    _forget_the_trackers_of_b6(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    seen = _snapshot(entry)
    seen_refs = {unit.ref for unit in units}

    async def _reload_if_changed(hass: HomeAssistant, changed: ConfigEntry) -> None:
        """Reload when the data, the options or the stops differ from the ones this setup used (a rename or such does not)."""
        if _snapshot(changed) != seen:
            await hass.config_entries.async_reload(changed.entry_id)
            # After the reload: the unload of the old coordinators saves their answers once more.
            for gone in seen_refs - {unit.ref for unit in stop_units(changed)}:  # a stop that was removed
                await Store(hass, 1, store_key(gone)).async_remove()

    entry.async_on_unload(entry.add_update_listener(_reload_if_changed))
    return True


def _snapshot(entry: ConfigEntry) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    """What a setup depends on: the data, the options and the data of every stop (not any title)."""
    options = {k: v for k, v in entry.options.items() if k != _GENERATED_TITLE}  # a title is not what a setup depends on
    return dict(entry.data), options, {sid: dict(sub.data) for sid, sub in entry.subentries.items()}


def _stop_name_of(entry: ConfigEntry, subentry_id: str | None = None) -> str | None:
    """The stop's name, once the entry has loaded and the City has given it (the coordinator holds it)."""
    stop = runtimes(entry).get(subentry_id)
    info = getattr(getattr(stop["coordinator"] if stop else None, "data", None), "stop_info", None)
    name = info.get("nazwa_zespolu") if isinstance(info, dict) else None
    if not isinstance(name, str):
        return None
    tidy = " ".join(name.split())[:_NAME_LENGTH]  # one line, not longer than a stop's name can sensibly be
    return tidy or None


def _stop_text(stop_id: str, pole: str, name: str | None) -> str:
    """How a notice names the stop: "Rondo Daszyńskiego 15 (1085/15)", or just the numbers while the name is not known."""
    if not name:
        return f"{stop_id}/{pole}"
    # The name comes from the City and goes into a Markdown text: keep letters, digits, spaces, hyphens, commas and
    # apostrophes, and a dot only before a space, so nothing in it can format a line or become a link.
    plain = re.sub(r"\.(?=\S)", "", re.sub(r"[^\w\s.,'-]", "", " ".join(name.split()).replace("_", ""))).strip()
    return f"{plain} {pole} ({stop_id}/{pole})" if plain else f"{stop_id}/{pole}"


def _use_stop_name_in_title(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Title a stop "Line 176 from Rondo Daszyńskiego 15" instead of "Line 176 from 1085/15" (a version 1 entry), or "Rondo Daszyńskiego 15"
    instead of "1085/15" (the subentry of a line), unless the user gave it their own."""
    for unit in stop_units(entry):
        name = _stop_name_of(entry, unit.subentry_id)
        if not name:
            continue
        if unit.subentry_id is None:
            if entry.title == f"Line {unit.line} from {unit.stop_id}/{unit.stop_nr}":
                hass.config_entries.async_update_entry(entry, title=f"Line {unit.line} from {name} {unit.stop_nr}")
            continue
        subentry = entry.subentries[unit.subentry_id]
        if subentry.title == f"{unit.stop_id}/{unit.stop_nr}":
            hass.config_entries.async_update_subentry(entry, subentry, title=f"{name} {unit.stop_nr}")
    _title_line_plainly(hass, entry)


_GENERATED_TITLE = "generated_title"  # an option of 1.2.0b5 and b6: the title they made for a line (with its stops); only recognised now, to be replaced


def _title_line_plainly(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Title a line "Line 176", whatever stops it has (they are listed under it, and the list would grow with them). 1.2.0b5 and
    b6 titled a line with its stops and remembered that title in the ``generated_title`` option: such a title goes back to the plain
    one and the option is dropped. A title the user chose stays."""
    line = line_of(entry)
    made = entry.options.get(_GENERATED_TITLE)
    if not is_line_entry(entry) or not line or made is None:
        return
    options = {k: v for k, v in entry.options.items() if k != _GENERATED_TITLE}
    hass.config_entries.async_update_entry(entry, title=f"Line {line}" if entry.title == made else entry.title, options=options)


def stop_key(entry: ConfigEntry) -> tuple[str, str, str] | None:
    """The stop, the pole and the line of a version 1 entry (see ``stop_keys`` for any entry)."""
    keys = stop_keys(entry)
    return next(iter(keys)) if len(keys) == 1 and not is_line_entry(entry) else None


def _duplicate_issue_id(entry: ConfigEntry) -> str:
    """The ID of the Repairs notice that says an entry is the second one of a pair for the same stop, pole and line."""
    return f"duplicate_{entry.entry_id}"


def _update_duplicate_issue(hass: HomeAssistant, entry: ConfigEntry, removed: str | None = None) -> None:
    """Tell the user (Repairs) when another entry already covers the same stop, pole and line; the second sensor of
    such a pair cannot exist, and removing one of the entries is the user's call. Only a version 1 entry can be that
    second one: a line refuses the same stop twice when it is added."""
    key = stop_key(entry)
    earlier = []  # the entries added before this one: the first of a pair keeps its sensor, the later one has none
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id == entry.entry_id:
            break
        if other.entry_id != removed:  # Home Assistant before 2026.10 still lists an entry while it is being removed
            earlier.append(other)
    twin = key is not None and any(key in stop_keys(other) for other in earlier)
    if key is not None and twin:
        ir.async_create_issue(
            hass,
            DOMAIN,
            _duplicate_issue_id(entry),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="duplicate_entry",
            translation_placeholders={"line": key[2], "stop": _stop_text(key[0], key[1], _stop_name_of(entry))},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, _duplicate_issue_id(entry))


def _forget_the_trackers_of_b6(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """1.2.0b6 had a device tracker of the next vehicle at every stop; the pins of the vehicles are the line's now, and the distance is a sensor.
    The registry entries of those trackers would stay behind as entities that nothing provides: they are removed."""
    registry = er.async_get(hass)
    for tracker in er.async_entries_for_config_entry(registry, entry.entry_id):
        if tracker.domain == "device_tracker" and tracker.platform == DOMAIN:
            registry.async_remove(tracker.entity_id)


def _legacy_severity() -> ir.IssueSeverity:
    """An error while the City's old API is gone (the line gets no timetable), a warning if it is ever brought back."""
    return ir.IssueSeverity.ERROR if legacy_api_retired() else ir.IssueSeverity.WARNING


def _update_legacy_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """A notice (Repairs, can be dismissed) for an entry that still uses a key of the City's old API: it works, but the
    City publishes no date for its end and the token of the new API is its current service. Configure changes the key."""
    api_key = entry_api_key(entry)
    issue_id = f"legacy_key_{entry.entry_id}"
    units = stop_units(entry)
    if api_key is None or key_kind(api_key) != "legacy" or (not units and not is_line_entry(entry)) or legacy_api_retired():
        # while the old API is gone, Home Assistant's own reauth notice (one per entry) offers the same choices
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    if is_line_entry(entry):  # the key is the line's, whether it has stops left or not
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,  # the token can be pasted in the notice itself (repairs.py)
            data={"entry_id": entry.entry_id},
            severity=_legacy_severity(),
            translation_key="legacy_key_line",
            translation_placeholders={"line": line_of(entry) or "", "portal": KEY_PORTAL_URL},
        )
        return
    unit = units[0]
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,  # the token can be pasted in the notice itself (repairs.py)
        data={"entry_id": entry.entry_id},
        severity=_legacy_severity(),
        translation_key="legacy_key",
        translation_placeholders={
            "line": unit.line,
            "stop": _stop_text(unit.stop_id, unit.stop_nr, _stop_name_of(entry)),
            "portal": KEY_PORTAL_URL,  # hassfest wants no URL inside a translated text
        },
    )


async def async_unload_entry(hass: HomeAssistant, entry: ZtmConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    running = runtimes(entry)
    for runtime in running.values():
        try:
            await runtime["coordinator"].async_shutdown()
        except Exception:  # noqa: BLE001 - shutdown should not crash unload
            _LOGGER.debug("Coordinator shutdown raised; ignoring", exc_info=True)

    return unload_ok

# Home Assistant awaits this function with these three arguments, so it has to be a coroutine function that takes all three.
async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry) -> bool:  # NOSONAR
    """Let the user delete a device of a stop that the entry no longer has; refuse one that is still in use.

    A device of a line entry belongs to one of its stops (``line_<line>_<id>_<nr>``), the device of a 1.1.x entry to its line
    (``line_<line>``). Home Assistant calls this from the *Delete* button of the device page.
    """
    live = {f"line_{unit.line}_{unit.stop_id}_{unit.stop_nr}" if is_line_entry(entry) else f"line_{unit.line}" for unit in stop_units(entry)}
    return not any(domain == DOMAIN and identifier in live for domain, identifier in device_entry.identifiers)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the answers stored for a removed entry, and the notice about it or about its twin."""
    for ref in (entry.entry_id, *entry.subentries):
        await Store(hass, 1, store_key(ref)).async_remove()
        ir.async_delete_issue(hass, DOMAIN, silent_issue_id(ref))
    ir.async_delete_issue(hass, DOMAIN, _duplicate_issue_id(entry))
    ir.async_delete_issue(hass, DOMAIN, f"legacy_key_{entry.entry_id}")
    ir.async_delete_issue(hass, DOMAIN, merged_keys_issue_id(entry.entry_id))
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id != entry.entry_id:
            _update_duplicate_issue(hass, other, removed=entry.entry_id)
