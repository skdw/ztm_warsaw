"""The fix flow of the notice about an old key: paste the token in the dialog of the notice itself.

The notice (``legacy_key`` for an entry of one stop, ``legacy_key_line`` for a line) is fixable, so Home Assistant opens
this flow from the Repairs list and no *Ignore* button of its own (the Repairs list shows that only for a notice that is not
fixable). The flow therefore starts with a menu: paste a token, or ignore the notice for good, which is what *Ignore* does
(``ir.async_ignore_issue``): the notice stays ignored across restarts until it is deleted and created again. Pasting asks for the new key (a token of the new API), checks
it with the City exactly as *Configure* does (``key_error``) and saves it with the same code (``save_key``): the entry
reloads once. Home Assistant deletes the notice when the flow finishes, and the reload brings it back only if the entry still
has an old key (a token is the end of it; another old key leaves the notice, which is then not dismissed any more).
"""
from __future__ import annotations

from typing import Any, cast

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .config_flow import close_reauth, key_can_change, key_error, save_key
from .const import CONF_API_KEY, DOMAIN, KEY_PORTAL_URL
from .entries import line_of, stop_units


class LegacyKeyRepairFlow(RepairsFlow):
    """Ask for a token to replace the old key of an entry and save it."""

    def __init__(self, entry_id: str | None) -> None:
        """Remember the entry whose key is replaced (the issue carries its ID)."""
        super().__init__()
        self._entry_id = entry_id

    def _line_of_entry(self, entry) -> str:
        """The line of the entry whose key is replaced, for the texts of the dialog."""
        units = stop_units(entry)
        return line_of(entry) or (units[0].line if units else "")

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> Any:  # the result type differs between Home Assistant versions
        """The first step: Home Assistant calls it with the data of the issue, not with a form, so it offers the two ways out:
        paste a token, or ignore the notice (a fixable notice has no *Ignore* button in the Repairs list). Aborts when the entry is gone."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id) if self._entry_id else None
        if entry is None or not key_can_change(entry):
            return self.async_abort(reason="unknown")
        return self.async_show_menu(
            step_id="init",
            menu_options=["token", "ignore"],
            description_placeholders={"line": self._line_of_entry(entry), "portal": KEY_PORTAL_URL},
        )

    async def async_step_ignore(self, user_input: dict[str, str] | None = None) -> Any:  # the result type differs between Home Assistant versions
        """Ignore the notice, as *Ignore* in the Repairs dialog of any other notice does: it stays ignored, across restarts,
        until it is deleted and created again. The old key keeps working; a key the City rejects is a reauth, a notice of its own."""
        ir.async_ignore_issue(self.hass, DOMAIN, self.issue_id, True)
        return self.async_abort(reason="ignored")

    async def async_step_token(self, user_input: dict[str, str] | None = None) -> Any:  # the result type differs between Home Assistant versions
        """The form for the new key, or the end of the flow once the key is saved; aborts when the entry is gone."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id) if self._entry_id else None
        if entry is None or not key_can_change(entry):
            return self.async_abort(reason="unknown")
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            error, works = await key_error(self.hass, entry, key)
            if error is None or works:  # that the line does not run today is not the key's fault
                save_key(self.hass, entry, key)
                await close_reauth(self.hass, entry)
                return self.async_create_entry(data={})
            errors["base"] = error
        line = self._line_of_entry(entry)
        return self.async_show_form(
            step_id="token",
            data_schema=cast("Any", vol.Schema({vol.Required(CONF_API_KEY): str})),  # Home Assistant 2026.10 types it for another schema library
            errors=errors,
            description_placeholders={"line": line, "portal": KEY_PORTAL_URL},
        )


# Home Assistant awaits this function with these arguments, so it has to be a coroutine function that takes all three.
async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None) -> RepairsFlow:  # NOSONAR
    """The fix flow of a fixable notice of this integration: both of them are about an old key, and carry the entry."""
    entry_id = (data or {}).get("entry_id")
    return LegacyKeyRepairFlow(entry_id if isinstance(entry_id, str) else None)
