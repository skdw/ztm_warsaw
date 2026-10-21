"""One-time conversion of the entries of 1.1.x (one stop each) into lines (one entry per line, its stops as subentries).

It runs before any entry is set up, so no entity is loaded and the registry can still be told that an entity belongs to
another entry. Nothing a user set is lost: the entities keep their unique IDs and entity IDs (so their names, areas,
icons and whether they are disabled stay), and the devices of the stops carry over the area, the name and the labels of
the device they replace. Every step looks at what is there already, so a run that was cut short is finished by the next.
"""
from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from .client import key_kind
from .const import CONF_API_KEY, CONF_DEPARTURES, CONF_LINE, DOMAIN, NEXT_DEPARTURES
from .coordinator import store_key
from .entries import LINE_ENTRY_VERSION, SUBENTRY_STOP, StopUnit, entry_api_key, is_line_entry, line_of, stop_units

_LOGGER = logging.getLogger(__name__)

# Every spelling the setup of 1.1.x read for what moves out of the entry's own data: an option with one of them is dropped.
_MOVED_FIELDS = frozenset(
    {"api_key", "apikey", "apiKey", "line", "linia", "departures"}
    | {"stop_id", "busstop_id", "busstopId", "busstopID", "stopId", "zespol"}
    | {"stop_nr", "busstop_nr", "busstopNr", "stopNr", "slupek"}
)


def merged_keys_issue_id(entry_id: str) -> str:
    """The ID of the Repairs notice that says the stops of a line had different keys when they were grouped."""
    return f"merged_keys_{entry_id}"


async def async_migrate_to_lines(hass: HomeAssistant) -> None:
    """Group the readable entries of one stop by their line. An entry that cannot be read is left as it is."""
    entries = hass.config_entries.async_entries(DOMAIN)
    groups: dict[str, list[ConfigEntry]] = {}
    for entry in entries:
        if is_line_entry(entry) or entry.disabled_by is not None:
            continue  # a line is there already, or the user switched this entry off: that choice is theirs, not ours
        units = stop_units(entry)
        if units:
            groups.setdefault(units[0].line, []).append(entry)
    for line, members in groups.items():
        try:
            await _merge_line(hass, line, members, entries)
        except Exception:  # noqa: BLE001
            # One line that cannot be grouped must not stop the others, or the setup.
            _LOGGER.exception("The entries of line %s could not be grouped; they keep working as they are", line)
    # A line whose last 1.1.x entry was converted by an earlier run that was cut short before its clean-up: nothing is left
    # to group, so the clean-up is done here, for every line that is there (it does nothing when there is nothing to clean).
    for entry in hass.config_entries.async_entries(DOMAIN):
        if is_line_entry(entry) and (converted_line := line_of(entry)):
            await _clean_up(hass, entry, converted_line, [], set())


def _stop_title(entry: ConfigEntry, unit: StopUnit) -> str:
    """The title of a stop's subentry: its name when the entry was titled with it ("Line 176 from Marcelin 15")."""
    numbers = f"{unit.stop_id}/{unit.stop_nr}"
    prefix = f"Line {unit.line} from "
    title = entry.title.strip()
    if title.startswith(prefix) and title != f"{prefix}{numbers}" and title[len(prefix):].strip():
        return title[len(prefix):].strip()
    if title and not title.startswith(prefix) and title != f"Line {unit.line}":
        return title  # a title the user gave the entry is the name of its stop
    return numbers


def _chosen_key(candidates: list[str]) -> str:
    """The key of the line: a token wins over an old key, otherwise the first one (the parent's)."""
    return next((key for key in candidates if key_kind(key) == "token"), candidates[0])


async def _merge_line(hass: HomeAssistant, line: str, members: list[ConfigEntry], entries: list[ConfigEntry]) -> None:
    """Group the entries of one line into the line: its stops, the entities, devices and stored answers of the stops, then the entry itself.

    The steps run in an order that is safe to interrupt (what can fail on disk comes first), and each looks at what is
    there, so a run that was cut short is finished by the next one.
    """
    existing = next((e for e in entries if is_line_entry(e) and line_of(e) == line), None)
    if existing is not None and existing.disabled_by is not None:
        return  # its entities would be switched off with it: the stops stay as they are until the user switches it on
    parent = existing or members[0]
    siblings = [m for m in members if m is not parent]

    keys = [k for k in ([entry_api_key(existing)] if existing else []) + [entry_api_key(m) for m in members] if k]
    chosen = _chosen_key(keys)

    # 1. a subentry for every stop (the same stop twice, a duplicate of 1.1.x, is one)
    stops, units = _add_stops(hass, parent, members)

    # 2. the stored answers of every stop, copied under the name of its subentry first: the step that can fail on disk
    #    comes before the registries are touched, and the old ones are removed only at the end
    for member in members:
        await _copy_store(hass, member.entry_id, stops[member.entry_id], reset_flags=entry_api_key(member) != chosen)

    # 3. the entities and the devices of the stops
    old_devices = _move_entities_and_devices(hass, parent, line, members, stops, units)

    # 4. the entry of the line
    _convert_parent(hass, parent, line, chosen, differing_keys=len(set(keys)) > 1)

    # 5. the entries that were stops of the line are gone, with their notices
    for sibling in siblings:
        await hass.config_entries.async_remove(sibling.entry_id)

    # 6. what the old entries left behind (also the parent's own, when an earlier run was cut short after step 4)
    await _clean_up(hass, parent, line, members, old_devices)


def _add_stops(hass: HomeAssistant, parent: ConfigEntry, members: list[ConfigEntry]) -> tuple[dict[str, str], dict[str, StopUnit]]:
    """A subentry for the stop of every member, reusing the ones the line has already; returns the subentry of each member and its stop."""
    stops: dict[str, str] = {}  # the entry id of a member -> the id of the subentry of its stop
    units: dict[str, StopUnit] = {}
    for member in members:
        unit = stop_units(member)[0]
        units[member.entry_id] = unit
        unique_id = f"{unit.stop_id}_{unit.stop_nr}"
        subentry_id = next((sid for sid, sub in parent.subentries.items() if sub.unique_id == unique_id), None)
        if subentry_id is None:
            subentry = ConfigSubentry(
                subentry_type=SUBENTRY_STOP,
                title=_stop_title(member, unit),
                data=MappingProxyType({"busstop_id": _int_if_number(unit.stop_id), "busstop_nr": unit.stop_nr}),
                unique_id=unique_id,
            )
            hass.config_entries.async_add_subentry(parent, subentry)
            subentry_id = subentry.subentry_id
        stops[member.entry_id] = subentry_id
    return stops, units


def _convert_parent(hass: HomeAssistant, parent: ConfigEntry, line: str, chosen: str, *, differing_keys: bool) -> None:
    """The entry becomes the line: its key and line only, the stops being subentries (a title the user gave it stays)."""
    title = parent.title
    if not is_line_entry(parent) and parent.title.startswith(f"Line {line} from "):
        title = f"Line {line}"
    hass.config_entries.async_update_entry(
        parent,
        title=title,
        data={CONF_API_KEY: chosen, CONF_LINE: line, CONF_DEPARTURES: NEXT_DEPARTURES},
        options={k: v for k, v in parent.options.items() if k not in _MOVED_FIELDS},
        version=LINE_ENTRY_VERSION,
    )
    if differing_keys:
        ir.async_create_issue(
            hass,
            DOMAIN,
            merged_keys_issue_id(parent.entry_id),
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="merged_keys",
            translation_placeholders={"line": line},
        )
    ir.async_delete_issue(hass, DOMAIN, f"legacy_key_{parent.entry_id}")  # the notice of the line replaces it
    ir.async_delete_issue(hass, DOMAIN, f"duplicate_{parent.entry_id}")


async def _clean_up(hass: HomeAssistant, parent: ConfigEntry, line: str, members: list[ConfigEntry], old_devices: set[str]) -> None:
    """The answers saved under the old names, and the devices that nothing uses any more."""
    for entry_id in {parent.entry_id, *(m.entry_id for m in members)}:
        await Store(hass, 1, store_key(entry_id)).async_remove()
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    line_device = (DOMAIN, f"line_{line}")  # the device a 1.1.x entry had, which a cut-short run may have left on the parent
    candidates = set(old_devices) | {
        d.id for d in dr.async_entries_for_config_entry(device_registry, parent.entry_id) if line_device in d.identifiers
    }
    for device_id in candidates:
        if device_registry.async_get(device_id) and not er.async_entries_for_device(
            entity_registry, device_id, include_disabled_entities=True
        ):
            device_registry.async_remove_device(device_id)


def _int_if_number(value: str) -> Any:
    """The stop id as the setup of 1.1.x stored it (it asked for a number): a number when it is exactly one."""
    return int(value) if value.isascii() and value.isdigit() and str(int(value)) == value else value


def _move_entities_and_devices(
    hass: HomeAssistant, parent: ConfigEntry, line: str, members: list[ConfigEntry], stops: dict[str, str], units: dict[str, StopUnit]
) -> set[str]:
    """Move the entities of the members to the line and to the device of their stop, creating that device and carrying over what the user set on the old one.

    Returns the old devices, for the clean-up once nothing uses them.
    """
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    new_devices: dict[str, str] = {}  # the subentry id -> the id of the device of its stop
    old_devices: set[str] = set()
    for member in members:
        subentry_id = stops[member.entry_id]
        unit = units[member.entry_id]
        for entity in er.async_entries_for_config_entry(entity_registry, member.entry_id):
            device_id = new_devices.get(subentry_id)
            if device_id is None:
                device = device_registry.async_get_or_create(
                    config_entry_id=parent.entry_id,
                    config_subentry_id=subentry_id,
                    identifiers={(DOMAIN, f"line_{line}_{unit.stop_id}_{unit.stop_nr}")},
                    name=f"Line {line}",
                    entry_type=dr.DeviceEntryType.SERVICE,
                )
                device_id = new_devices[subentry_id] = device.id
            if entity.device_id and entity.device_id != device_id:
                old_devices.add(entity.device_id)
                _carry_over(device_registry, entity.device_id, device_id)
            entity_registry.async_update_entity(
                entity.entity_id,
                config_entry_id=parent.entry_id,
                config_subentry_id=subentry_id,
                device_id=device_id,
            )
    return old_devices


def _carry_over(device_registry: dr.DeviceRegistry, old_id: str, new_id: str) -> None:
    """What the user set on a device (its area, its own name, its labels, that it is off) goes to the device that replaces it."""
    old = device_registry.async_get(old_id)
    new = device_registry.async_get(new_id)
    if old is None or new is None:
        return
    changes: dict[str, Any] = {}
    if old.area_id and not new.area_id:
        changes["area_id"] = old.area_id
    if old.name_by_user and not new.name_by_user:
        changes["name_by_user"] = old.name_by_user
    if old.labels and not new.labels:
        changes["labels"] = set(old.labels)
    if old.disabled_by is dr.DeviceEntryDisabler.USER and new.disabled_by is None:
        changes["disabled_by"] = dr.DeviceEntryDisabler.USER
    if changes:
        device_registry.async_update_device(new_id, **changes)


async def _copy_store(hass: HomeAssistant, entry_id: str, subentry_id: str, *, reset_flags: bool) -> None:
    """The answers saved for the stop of a 1.1.x entry are kept for its stop of the line. A rejection of the old key is
    not carried over to a stop that now uses another one."""
    old: Store[dict[str, Any]] = Store(hass, 1, store_key(entry_id))
    stored = await old.async_load()
    if stored is None:
        return
    new: Store[dict[str, Any]] = Store(hass, 1, store_key(subentry_id))
    if await new.async_load() is None:
        if reset_flags:
            stored = {**stored, "api_error": False, "rejections": 0}
        await new.async_save(stored)
