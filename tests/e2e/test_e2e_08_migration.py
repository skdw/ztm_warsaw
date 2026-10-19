"""E2E-33: the entries of 1.1.x (one stop each) become lines at startup, and nothing a user set is lost."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ztm_warsaw.const import DOMAIN
from custom_components.ztm_warsaw.coordinator import store_key
from custom_components.ztm_warsaw.migration import async_migrate_to_lines

from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN
from .helpers import find_devices, subentry_of

pytestmark = [pytest.mark.e2e, pytest.mark.migrate]

OTHER_KEY = "22222222-3333-4444-8555-666666666666"  # gitleaks:allow  (synthetic)
NO_MIGRATION = "custom_components.ztm_warsaw.async_migrate_to_lines"


async def _as_1_1_x_left_them(env, *specs, **single):
    """The entries as a 1.1.x installation leaves them: set up once, then Home Assistant stopped."""
    specs = specs or (single,)
    with patch(NO_MIGRATION, AsyncMock()):
        entries = [await env.add_entry(**spec) for spec in specs]
        for entry in entries:
            await env.hass.config_entries.async_unload(entry.entry_id)
    return entries


async def _restart(env):
    """What the next start does: the conversion, then every entry is set up."""
    await async_migrate_to_lines(env.hass)
    for entry in env.hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.NOT_LOADED:
            await env.hass.config_entries.async_setup(entry.entry_id)
    await env.settle()


def _lines(env):
    return {e.data["line"]: e for e in env.hass.config_entries.async_entries(DOMAIN) if e.version == 2}


async def test_e2e_33_an_entry_of_one_stop_becomes_a_line_with_that_stop(env):
    (old,) = await _as_1_1_x_left_them(env, line="151")
    before = {e.unique_id: e.entity_id for e in er.async_entries_for_config_entry(env.entity_registry, old.entry_id)}
    await _restart(env)

    assert env.hass.config_entries.async_entries(DOMAIN) == [old]  # the same entry, converted
    assert old.version == 2
    assert old.title == "Line 151"
    assert dict(old.data) == {"api_key": DEFAULT_KEY, "line": "151", "departures": 3}
    (stop,) = old.subentries.values()
    assert (stop.subentry_type, stop.unique_id, dict(stop.data)) == (
        "stop",
        "7009_01",
        {"busstop_id": 7009, "busstop_nr": "01"},
    )
    after = {e.unique_id: e.entity_id for e in er.async_entries_for_config_entry(env.entity_registry, old.entry_id)}
    assert after == before, "the unique IDs and the entity IDs are the ones the user already uses"
    assert all(
        e.config_subentry_id == stop.subentry_id for e in er.async_entries_for_config_entry(env.entity_registry, old.entry_id)
    )
    assert env.state().state not in ("unknown", "unavailable")
    (device,) = dr.async_entries_for_config_entry(env.device_registry, old.entry_id)
    assert device.identifiers == {(DOMAIN, "line_151_7009_01")}
    assert subentry_of(device, old.entry_id) == stop.subentry_id


async def test_e2e_33_the_stops_of_one_line_become_one_entry_and_other_lines_stay_apart(env):
    entries = await _as_1_1_x_left_them(
        env,
        {"line": "525", "stop_id": 7009, "stop_nr": "01"},
        {"line": "151", "stop_id": 7009, "stop_nr": "01"},
        {"line": "525", "stop_id": 7009, "stop_nr": "02"},
        {"line": "525", "stop_id": 7013, "stop_nr": "01"},
    )
    await _restart(env)

    lines = _lines(env)
    assert sorted(lines) == ["151", "525"]
    assert lines["525"] is entries[0]  # the oldest entry of the line keeps its ID
    assert [e.entry_id for e in env.hass.config_entries.async_entries(DOMAIN)] == [entries[0].entry_id, entries[1].entry_id]
    assert sorted((s.data["busstop_id"], s.data["busstop_nr"]) for s in lines["525"].subentries.values()) == [
        (7009, "01"),
        (7009, "02"),
        (7013, "01"),
    ]
    for stop_id, stop_nr in (("7009", "01"), ("7009", "02"), ("7013", "01")):
        assert env.state("525", stop_id, stop_nr).state not in ("unknown", "unavailable"), (stop_id, stop_nr)
    assert env.state("151").state not in ("unknown", "unavailable")
    devices = dr.async_entries_for_config_entry(env.device_registry, lines["525"].entry_id)
    assert sorted(next(iter(d.identifiers))[1] for d in devices) == [
        "line_525_7009_01",
        "line_525_7009_02",
        "line_525_7013_01",
    ]
    assert not [e for e in er.async_entries_for_config_entry(env.entity_registry, lines["525"].entry_id) if not e.config_subentry_id]


async def test_e2e_33_what_the_user_set_survives(env):
    old, second = await _as_1_1_x_left_them(
        env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02"}
    )
    entities = env.entity_registry
    sensor = "sensor.line_525_from_7009_01"
    entities.async_update_entity(sensor, name="My bus", icon="mdi:star")
    diagnostic = entities.async_get("sensor.line_525_from_7009_01_last_update")
    entities.async_update_entity(diagnostic.entity_id, disabled_by=None)  # the user switched it on
    area = ar.async_get(env.hass).async_create("Kitchen")
    devices = find_devices(env.device_registry, {(DOMAIN, "line_525")})
    assert devices, "the device of the line (one for both stops, or one per entry on Home Assistant 2026.10)"
    for device in devices:
        env.device_registry.async_update_device(device.id, area_id=area.id, name_by_user="Bus to work")
    env.hass.config_entries.async_update_entry(old, title="Work line")

    await _restart(env)

    assert entities.async_get(sensor).name == "My bus"
    assert entities.async_get(sensor).icon == "mdi:star"
    assert entities.async_get(diagnostic.entity_id).disabled_by is None
    assert entities.async_get("calendar.line_525_from_7009_01_timetable").disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert old.title == "Work line"
    for stop_nr in ("01", "02"):  # both stops had the one device of the line: both carry what was set on it
        (new,) = find_devices(env.device_registry, {(DOMAIN, f"line_525_7009_{stop_nr}")})
        assert (new.area_id, new.name_by_user) == (area.id, "Bus to work"), stop_nr
    assert find_devices(env.device_registry, {(DOMAIN, "line_525")}) == []
    assert second.entry_id not in [e.entry_id for e in env.hass.config_entries.async_entries(DOMAIN)]


async def test_e2e_33_a_token_wins_over_an_old_key_and_the_user_is_told(env):
    env.city.valid_keys.add(OTHER_KEY)
    old, token = await _as_1_1_x_left_them(
        env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02", "api_key": DEFAULT_TOKEN}
    )
    await _restart(env)
    assert old.data["api_key"] == DEFAULT_TOKEN
    issues = ir.async_get(env.hass)
    notice = issues.async_get_issue(DOMAIN, f"merged_keys_{old.entry_id}")
    assert notice is not None
    assert notice.translation_placeholders == {"line": "525"}
    assert issues.async_get_issue(DOMAIN, f"legacy_key_{old.entry_id}") is None  # a token: nothing to switch to
    assert env.city.count(contract="new") > 0


async def test_e2e_33_two_old_keys_leave_the_key_of_the_first_entry(env):
    env.city.valid_keys.add(OTHER_KEY)
    old, _ = await _as_1_1_x_left_them(
        env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02", "api_key": OTHER_KEY}
    )
    await _restart(env)
    assert old.data["api_key"] == DEFAULT_KEY
    assert ir.async_get(env.hass).async_get_issue(DOMAIN, f"merged_keys_{old.entry_id}") is not None
    assert ir.async_get(env.hass).async_get_issue(DOMAIN, f"legacy_key_{old.entry_id}") is not None  # still an old key


async def test_e2e_33_the_same_key_twice_is_no_news(env):
    old, _ = await _as_1_1_x_left_them(env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02"})
    await _restart(env)
    assert ir.async_get(env.hass).async_get_issue(DOMAIN, f"merged_keys_{old.entry_id}") is None


async def test_e2e_33_a_duplicate_of_1_1_x_is_one_stop(env):
    first, twin = await _as_1_1_x_left_them(env, {"line": "151"}, {"line": "151"})
    assert ir.async_get(env.hass).async_get_issue(DOMAIN, f"duplicate_{twin.entry_id}") is not None
    await _restart(env)
    assert env.hass.config_entries.async_entries(DOMAIN) == [first]
    assert len(first.subentries) == 1
    assert env.state().state not in ("unknown", "unavailable")
    assert ir.async_get(env.hass).async_get_issue(DOMAIN, f"duplicate_{twin.entry_id}") is None


async def test_e2e_33_the_stored_answers_follow_the_stop(env):
    old, second = await _as_1_1_x_left_them(env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02"})
    for entry in (old, second):
        assert await Store(env.hass, 1, store_key(entry.entry_id)).async_load() is not None
    await async_migrate_to_lines(env.hass)
    assert await Store(env.hass, 1, store_key(second.entry_id)).async_load() is None
    assert await Store(env.hass, 1, store_key(old.entry_id)).async_load() is None
    for subentry_id in old.subentries:
        stored = await Store(env.hass, 1, store_key(subentry_id)).async_load()
        assert stored is not None
        assert stored["answers"], "the timetable the stop had is the timetable it starts from"


async def test_e2e_33_running_it_again_changes_nothing(env):
    old, _ = await _as_1_1_x_left_them(env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02"})
    await _restart(env)
    snapshot = (
        dict(old.data),
        old.title,
        old.version,
        sorted(old.subentries),
        sorted(e.entity_id for e in er.async_entries_for_config_entry(env.entity_registry, old.entry_id)),
    )
    await async_migrate_to_lines(env.hass)
    assert snapshot == (
        dict(old.data),
        old.title,
        old.version,
        sorted(old.subentries),
        sorted(e.entity_id for e in er.async_entries_for_config_entry(env.entity_registry, old.entry_id)),
    )
    assert len(env.hass.config_entries.async_entries(DOMAIN)) == 1


async def test_e2e_33_a_run_that_was_cut_short_is_finished_by_the_next(env):
    old, second = await _as_1_1_x_left_them(env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02"})
    with patch.object(env.hass.config_entries, "async_remove", side_effect=RuntimeError("cut short")):
        await async_migrate_to_lines(env.hass)  # everything but the removal of the second entry happened
    assert old.version == 2
    assert second in env.hass.config_entries.async_entries(DOMAIN)
    assert len(old.subentries) == 2
    await _restart(env)
    assert env.hass.config_entries.async_entries(DOMAIN) == [old]
    assert len(old.subentries) == 2, "the stop that was added already is not added twice"
    for stop_nr in ("01", "02"):
        assert env.state("525", "7009", stop_nr).state not in ("unknown", "unavailable")


async def test_e2e_33_an_entry_that_cannot_be_read_is_left_as_it_is(env):
    broken = MockConfigEntry(domain=DOMAIN, title="Line 151", data={"api_key": DEFAULT_KEY, "line": "151"})
    broken.add_to_hass(env.hass)
    (fine,) = await _as_1_1_x_left_them(env, {"line": "525"})
    await _restart(env)
    assert broken.version == 1
    assert dict(broken.data) == {"api_key": DEFAULT_KEY, "line": "151"}
    assert fine.version == 2


async def test_e2e_33_an_old_key_gets_the_notice_of_the_line_and_not_one_per_old_entry(env):
    old, second = await _as_1_1_x_left_them(env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02"})
    issues = ir.async_get(env.hass)
    assert issues.async_get_issue(DOMAIN, f"legacy_key_{second.entry_id}") is not None
    await _restart(env)
    assert issues.async_get_issue(DOMAIN, f"legacy_key_{second.entry_id}") is None
    notice = issues.async_get_issue(DOMAIN, f"legacy_key_{old.entry_id}")
    assert notice is not None
    assert notice.translation_key == "legacy_key_line"


async def test_e2e_33_the_start_of_the_integration_converts_before_the_entries_are_set_up(env):
    (old,) = await _as_1_1_x_left_them(env, {"line": "151"})
    env.hass.config.components.remove(DOMAIN)  # Home Assistant has just started: the integration is not set up yet
    assert await env.hass.config_entries.async_setup(old.entry_id)
    await env.settle()
    assert (old.version, old.state) == (2, ConfigEntryState.LOADED)
    assert env.state().state not in ("unknown", "unavailable")


async def test_e2e_33_a_reload_after_the_conversion_changes_nothing(env):
    (old,) = await _as_1_1_x_left_them(env, {"line": "151"})
    await _restart(env)
    stops = sorted(old.subentries)
    assert await env.hass.config_entries.async_reload(old.entry_id)
    await env.settle()
    assert (old.version, sorted(old.subentries), old.state) == (2, stops, ConfigEntryState.LOADED)


async def test_e2e_33_an_installation_with_lines_of_several_stops_and_a_duplicate(env):
    specs = []
    for line in ("525", "520"):
        for stop_id, stop_nr in ((7009, "01"), (7009, "02"), (7013, "01")):
            specs.append({"line": line, "stop_id": stop_id, "stop_nr": stop_nr})
    specs.append({"line": "N25", "stop_nr": "01"})
    specs.append({"line": "N25", "stop_nr": "01"})  # a duplicate
    entries = await _as_1_1_x_left_them(env, *specs)
    ids_before = {
        e.unique_id: e.entity_id
        for entry in entries
        for e in er.async_entries_for_config_entry(env.entity_registry, entry.entry_id)
    }
    await _restart(env)
    lines = _lines(env)
    assert sorted(lines) == ["520", "525", "N25"]
    assert len(env.hass.config_entries.async_entries(DOMAIN)) == 3
    assert [len(lines[line].subentries) for line in ("520", "525", "N25")] == [3, 3, 1]
    ids_after = {
        e.unique_id: e.entity_id
        for entry in lines.values()
        for e in er.async_entries_for_config_entry(env.entity_registry, entry.entry_id)
    }
    assert ids_after == ids_before
    assert all(e.state is ConfigEntryState.LOADED for e in lines.values())


async def test_e2e_33_an_entry_the_user_switched_off_is_not_merged_and_stays_off(env):
    old, off, other = await _as_1_1_x_left_them(
        env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02"}, {"line": "525", "stop_id": 7013}
    )
    await env.hass.config_entries.async_set_disabled_by(off.entry_id, ConfigEntryDisabler.USER)
    off_entities = {e.entity_id: e.disabled_by for e in er.async_entries_for_config_entry(env.entity_registry, off.entry_id)}
    await _restart(env)
    assert (old.version, off.version) == (2, 1), "the entry that is off is left as it was"
    assert off.disabled_by is ConfigEntryDisabler.USER
    assert sorted(s.data["busstop_id"] for s in old.subentries.values()) == [7009, 7013]  # the two that are on
    assert {e.entity_id: e.disabled_by for e in er.async_entries_for_config_entry(env.entity_registry, off.entry_id)} == (
        off_entities
    )
    assert env.state("525", "7009", "01").state not in ("unknown", "unavailable")
    off_state = env.hass.states.get("sensor.line_525_from_7009_02")
    assert off_state is None or off_state.attributes.get("restored"), "still off: no live sensor"
    assert other.entry_id not in [e.entry_id for e in env.hass.config_entries.async_entries(DOMAIN)]


async def test_e2e_33_a_line_that_is_switched_off_keeps_the_stops_that_are_on_apart(env):
    first, second = await _as_1_1_x_left_them(env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02"})
    await _restart(env)
    assert (first.version, len(first.subentries)) == (2, 2)
    await env.hass.config_entries.async_set_disabled_by(first.entry_id, ConfigEntryDisabler.USER)
    with patch(NO_MIGRATION, AsyncMock()):
        late = await env.add_entry(line="525", stop_id=7013)  # a 1.1.x entry of the line that appears later
    await async_migrate_to_lines(env.hass)
    assert late.version == 1 and late in env.hass.config_entries.async_entries(DOMAIN)
    assert len(first.subentries) == 2


async def test_e2e_33_the_title_the_user_gave_a_stops_entry_names_its_stop(env):
    old, other = await _as_1_1_x_left_them(env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02"})
    env.hass.config_entries.async_update_entry(other, title="Home")
    await _restart(env)
    titles = {s.data["busstop_nr"]: s.title for s in old.subentries.values()}
    assert titles["02"] == "Home"
    assert titles["01"] != "Home"


async def test_e2e_33_a_rejection_of_the_old_key_is_not_carried_to_the_stop_that_has_the_new_one(env):
    old, other = await _as_1_1_x_left_them(
        env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02", "api_key": DEFAULT_TOKEN}
    )
    store = Store(env.hass, 1, store_key(old.entry_id))
    stored = await store.async_load()
    await store.async_save({**stored, "api_error": True, "rejections": 2})  # the old key had been rejected
    await _restart(env)
    (first_stop,) = (sid for sid, s in old.subentries.items() if s.data["busstop_nr"] == "01")
    carried = await Store(env.hass, 1, store_key(first_stop)).async_load()
    assert (carried["api_error"], carried["rejections"]) == (False, 0)  # it asks with the token now
    assert env.state("525", "7009", "01").state not in ("unknown", "unavailable")


async def test_e2e_33_a_stop_id_with_a_leading_zero_is_not_turned_into_another_number(env):
    from custom_components.ztm_warsaw.migration import _int_if_number

    assert [_int_if_number(v) for v in ("7009", "0101", "A12", "²", "")] == [7009, "0101", "A12", "²", ""]


async def test_e2e_33_a_disk_that_fails_before_the_registries_are_touched_leaves_the_entries_as_they_were(env):
    old, other = await _as_1_1_x_left_them(env, {"line": "525", "stop_nr": "01"}, {"line": "525", "stop_nr": "02"})
    with patch.object(Store, "async_save", side_effect=OSError("disk full")):
        await async_migrate_to_lines(env.hass)  # logged, not raised: the start of Home Assistant goes on
    assert (old.version, other.version) == (1, 1)
    assert not [e for e in er.async_entries_for_config_entry(env.entity_registry, other.entry_id) if e.config_subentry_id]
    await _restart(env)  # and the next start does it
    assert env.hass.config_entries.async_entries(DOMAIN) == [old]
    assert env.state("525", "7009", "02").state not in ("unknown", "unavailable")
