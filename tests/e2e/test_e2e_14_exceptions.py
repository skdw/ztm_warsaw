"""E2E-42: the exceptions the integration raises carry translation keys, and every key has a text in every language."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ztm_warsaw import coordinator as coordinator_module
from custom_components.ztm_warsaw.client import ZTMApiError, ZTMAuthError
from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY

pytestmark = pytest.mark.e2e

LINE = "525"
TRANSLATIONS = Path(__file__).resolve().parents[2] / "custom_components" / "ztm_warsaw" / "translations"
KEYS = ["city_timeout", "city_not_ready", "city_rejected", "city_swapping", "no_cached_timetable", "fetch_failed"]


def _coordinator(entry):
    """The coordinator of the one stop of the line."""
    (runtime,) = entry.runtime_data["units"].values()
    return runtime["coordinator"]


def test_e2e_42_every_exception_key_has_a_text_in_every_language():
    for path in sorted(TRANSLATIONS.glob("*.json")):
        exceptions = json.loads(path.read_text())["exceptions"]
        assert set(exceptions) == set(KEYS), path.name
        assert all(exceptions[key]["message"] for key in KEYS), path.name


async def test_e2e_42_a_rejected_key_raises_a_translated_update_failed_and_the_text_never_holds_the_key(env):
    entry = await env.add_entry_via_flow(line=LINE)
    coordinator = _coordinator(entry)
    with pytest.raises(UpdateFailed) as failure:
        coordinator._api_rejected(ZTMApiError("the City answered with something else"))
    assert (failure.value.translation_domain, failure.value.translation_key) == (DOMAIN, "city_rejected")
    assert failure.value.translation_placeholders == {"error": "the City answered with something else"}
    assert DEFAULT_KEY not in str(failure.value.translation_placeholders)


async def test_e2e_42_three_rejected_keys_in_a_row_raise_a_translated_auth_failure(env):
    entry = await env.add_entry_via_flow(line=LINE)
    coordinator = _coordinator(entry)
    with pytest.raises(ConfigEntryAuthFailed) as failure:
        for _ in range(coordinator_module.REJECTIONS_BEFORE_REAUTH):
            try:
                coordinator._api_rejected(ZTMAuthError("the key was rejected"))
            except UpdateFailed:
                continue
    assert failure.value.translation_key == "city_rejected"


async def test_e2e_42_the_swap_of_the_city_without_a_cached_timetable_is_a_translated_failure(env):
    entry = await env.add_entry_via_flow(line=LINE)
    coordinator = _coordinator(entry)
    coordinator.data = None
    with pytest.raises(UpdateFailed) as failure:
        coordinator._hold_during_swap()
    assert failure.value.translation_key == "city_swapping"


async def test_e2e_42_a_first_refresh_that_runs_out_of_time_is_a_translated_not_ready(env):
    entry = await env.add_entry_via_flow(line=LINE)
    coordinator = _coordinator(entry)
    base = type(coordinator).__mro__[1]  # the Home Assistant coordinator whose first refresh the integration waits for
    with patch.object(coordinator, "_restore", AsyncMock(side_effect=lambda: setattr(coordinator, "data", None))), patch.object(
        base, "async_config_entry_first_refresh", side_effect=TimeoutError
    ):
        with pytest.raises(ConfigEntryNotReady) as failure:
            await coordinator.async_config_entry_first_refresh()
    assert failure.value.translation_key == "city_timeout"


async def test_e2e_42_a_first_refresh_that_fails_without_a_reason_is_a_translated_not_ready_with_the_cause(env):
    entry = await env.add_entry_via_flow(line=LINE)
    coordinator = _coordinator(entry)
    base = type(coordinator).__mro__[1]
    with patch.object(base, "async_config_entry_first_refresh", side_effect=ConfigEntryNotReady()):
        with pytest.raises(ConfigEntryNotReady) as failure:
            await coordinator.async_config_entry_first_refresh()
    assert (failure.value.translation_key, failure.value.translation_placeholders) == ("city_not_ready", {"error": "-"})
