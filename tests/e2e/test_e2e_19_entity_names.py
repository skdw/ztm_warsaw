"""E2E-46: the names of the entities come from the translations, and the entity IDs do not depend on the language."""

from __future__ import annotations

import pytest

from .fake_city import stop_name_for

pytestmark = pytest.mark.e2e

LINE = "151"


async def test_e2e_46_a_polish_installation_has_polish_names_and_the_same_entity_ids(env):
    env.hass.config.language = "pl"
    await env.add_entry_via_flow(line=LINE)
    status = env.hass.states.get(f"sensor.line_{LINE}_from_7009_01_status")
    assert status is not None  # the ID is the English one, whatever the language
    assert status.attributes["friendly_name"] == f"Line {LINE} {stop_name_for('7009')} 01 · status"
    main = env.hass.states.get(f"sensor.line_{LINE}_from_7009_01")
    assert main.attributes["friendly_name"] == f"Line {LINE} {stop_name_for('7009')} 01"


async def test_e2e_46_the_name_follows_the_stop_name_without_touching_the_entity_id(env):
    await env.add_entry_via_flow(line=LINE)
    entity_id = env.entity_registry.async_get_entity_id("sensor", "ztm_warsaw", f"line_{LINE}_from_7009_01_status")
    assert entity_id == f"sensor.line_{LINE}_from_7009_01_status"  # made from the numbers, though the name carries the stop's name
    assert env.hass.states.get(entity_id).attributes["friendly_name"] == f"Line {LINE} {stop_name_for('7009')} 01 Status"
