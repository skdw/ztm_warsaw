"""The shortest check that the integration installs and unloads on the OLDEST and the NEWEST Home Assistant it claims.

It uses only what both ends have: the real integration, the real config flow and a real Home Assistant, talking
to the fake City of Warsaw on loopback, in real time. It asks the questions a user would: does it install, does
the sensor appear, does it unload. The job ``Compat smoke`` runs the whole suite on the oldest release, so this
file is also the first thing to read when that job goes red; see CONTRIBUTING.md.
"""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ztm_warsaw.const import DOMAIN
from tests.e2e.fake_city import DEFAULT_KEY, FakeCity, route_to_fake_city

pytestmark = pytest.mark.compat

ENTRY_DATA = {"api_key": DEFAULT_KEY, "busstop_id": 7009, "busstop_nr": "01", "line": "151", "departures": 1}
SENSOR = "sensor.line_151_from_7009_01"


@pytest.fixture
async def city(socket_enabled):
    fake = FakeCity()
    await fake.start()
    try:
        with route_to_fake_city(fake):
            yield fake
        assert not fake.blocked, f"code under test tried to leave the sandbox: {fake.blocked}"
    finally:
        await fake.stop()


async def test_the_config_flow_creates_an_entry_that_loads(hass, enable_custom_integrations, city):
    flow = hass.config_entries.flow
    result = await flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form"
    result = await flow.async_configure(result["flow_id"], {k: v for k, v in ENTRY_DATA.items() if k != "departures"})
    await hass.async_block_till_done()
    assert result["type"] == "create_entry", result.get("errors")
    assert result["result"].state is ConfigEntryState.LOADED
    entry = result["result"]
    assert dict(entry.data) == {"api_key": ENTRY_DATA["api_key"], "line": "151", "departures": 3}  # a line ...
    (stop,) = entry.subentries.values()  # ... and its stop
    assert dict(stop.data) == {"busstop_id": 7009, "busstop_nr": "01"}


async def test_a_sensor_appears_and_is_removed_with_the_entry(hass, enable_custom_integrations, city):
    entry = MockConfigEntry(domain=DOMAIN, title="Line 151 from 7009/01", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get(SENSOR)
    assert state is not None
    assert state.state != "unavailable", state
    assert "Stop, ID" in state.attributes
    assert city.count("timetable") >= 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(SENSOR).state == "unavailable"
