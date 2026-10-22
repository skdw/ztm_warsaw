"""E2E-47: the City's old API is gone (const.LEGACY_API_RETIRED): an old key gets no request, only a clear message."""

from __future__ import annotations

import logging

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import issue_registry as ir

from custom_components.ztm_warsaw import config_flow
from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY, DEFAULT_TOKEN

pytestmark = pytest.mark.e2e

STATUS = "sensor.line_151_from_7009_01_status"


@pytest.fixture
def retired(monkeypatch):
    """Treat the City's old API as gone, as production does (the e2e environment switches it off for the other tests)."""
    monkeypatch.setattr("custom_components.ztm_warsaw.const.LEGACY_API_RETIRED", True)


async def test_e2e_47_an_old_key_sends_no_request_and_the_line_says_why_it_has_no_timetable(env, retired, caplog):
    caplog.set_level(logging.INFO)
    entry = await env.add_entry()
    assert entry.state is ConfigEntryState.LOADED, "the line loads, so that the key can be replaced in the notice"
    assert env.city.count() == 0, "nothing is asked of the old API"
    assert env.state().state == "unavailable"
    assert env.hass.states.get(STATUS).state == "old_api"
    issue = ir.async_get(env.hass).async_get_issue(DOMAIN, f"legacy_key_{entry.entry_id}")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR, "the notice is an error while the old API is gone"
    said = [r for r in caplog.records if r.levelno >= logging.WARNING and "old API" in r.getMessage()]
    assert len(said) == 1


async def test_e2e_47_it_is_said_once_for_all_the_lines(env, retired, caplog):
    caplog.set_level(logging.INFO)
    await env.add_entry()
    await env.add_entry(line="523")
    said = [r for r in caplog.records if r.levelno >= logging.WARNING and "old API" in r.getMessage()]
    assert len(said) == 1


async def test_e2e_47_the_timetable_saved_before_is_kept_and_nothing_is_asked(env, monkeypatch):
    entry = await env.add_entry()  # the old API still answers: a timetable is fetched and saved
    await env.advance(seconds=31)
    shown = env.state().state
    assert shown != "unavailable"
    monkeypatch.setattr("custom_components.ztm_warsaw.const.LEGACY_API_RETIRED", True)
    env.city.reset_counts()
    assert await env.hass.config_entries.async_reload(entry.entry_id)
    await env.settle()
    assert env.state().state == shown, "the saved timetable is shown while it is valid"
    assert env.city.count() == 0
    assert env.hass.states.get(STATUS).state == "old_api"


async def test_e2e_47_a_token_works_as_before(env, retired):
    await env.add_entry(api_key=DEFAULT_TOKEN)
    assert env.state().state != "unavailable"
    assert env.hass.states.get(STATUS).state == "running"
    assert env.city.count("timetable", contract="new") >= 1


async def test_e2e_47_a_new_line_with_an_old_key_is_refused_with_the_reason(env, retired):
    result = await env.hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    done = await env.hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": DEFAULT_KEY, "stop": "Testowa", "manual": False}
    )
    assert done["type"] == "form"
    assert done["errors"] == {"base": "old_api_retired"}
    assert env.city.count() == 0


async def test_e2e_47_pasting_an_old_key_as_the_new_one_is_refused_with_the_reason(env, retired):
    entry = await env.add_entry()
    assert await config_flow.key_error(env.hass, entry, DEFAULT_KEY) == ("old_api_retired", False)
    assert await config_flow.key_error(env.hass, entry, DEFAULT_TOKEN) is not None  # a token is asked about at the City as before
