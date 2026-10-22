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

from typing import Any

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .config_flow import KeyChoice, _form, close_reauth, key_can_change, key_error, line_label, save_key, tokens_of_others
from .const import CONF_API_KEY, DOMAIN, KEY_PORTAL_URL


class LegacyKeyRepairFlow(KeyChoice, RepairsFlow):
    """Ask for a token to replace the old key of an entry and save it."""

    def __init__(self, entry_id: str | None) -> None:
        """Remember the entry whose key is replaced (the issue carries its ID)."""
        super().__init__()
        self._entry_id = entry_id

    def _entry(self) -> ConfigEntry | None:
        """The entry whose key is replaced, or None when it is gone."""
        return self.hass.config_entries.async_get_entry(self._entry_id) if self._entry_id else None

    def _key_entry(self) -> ConfigEntry:
        """The entry whose key is replaced (the steps check it is there before they ask)."""
        entry = self._entry()
        if entry is None:
            raise RuntimeError("the entry of the notice is gone")
        return entry

    def _key_done(self) -> Any:
        """The key is replaced: Home Assistant deletes the notice (the reload brings it back only if an old key is left)."""
        return self.async_create_entry(data={})

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> Any:  # the result type differs between Home Assistant versions
        """The first step: Home Assistant calls it with the data of the issue, not with a form, so it offers the ways out:
        paste a token, use the token of another line, or ignore the notice (a fixable notice has no *Ignore* button in the
        Repairs list). Aborts when the entry is gone."""
        entry = self._entry()
        if entry is None or not key_can_change(entry):
            return self.async_abort(reason="unknown")
        options = ["token", "reuse", "ignore"] if tokens_of_others(self.hass, entry) else ["token", "ignore"]
        return self._key_menu("init", options, entry)

    async def async_step_reuse(self, user_input: dict[str, str] | None = None) -> Any:  # the result type differs between Home Assistant versions
        """Use the token another line already has: checked for this line like a pasted one, never shown. Aborts when the City does
        not accept it for this line (then pasting another is still possible by opening the notice again)."""
        if self._entry() is None:
            return self.async_abort(reason="unknown")
        return await self._reuse_step("reuse", user_input)

    async def async_step_ignore(self, user_input: dict[str, str] | None = None) -> Any:  # the result type differs between Home Assistant versions
        """Ignore the notice, as *Ignore* in the Repairs dialog of any other notice does: it stays ignored, across restarts,
        until it is deleted and created again. The old key keeps working; a key the City rejects is a reauth, a notice of its own."""
        ir.async_ignore_issue(self.hass, DOMAIN, self.issue_id, True)
        return self.async_abort(reason="ignored")

    async def async_step_token(self, user_input: dict[str, str] | None = None) -> Any:  # the result type differs between Home Assistant versions
        """The form for the new key, or the end of the flow once the key is saved; aborts when the entry is gone."""
        entry = self._entry()
        if entry is None or not key_can_change(entry):
            return self.async_abort(reason="unknown")
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            error, works = await key_error(self.hass, entry, key)
            if error is None or works:  # that the line does not run today is not the key's fault
                save_key(self.hass, entry, key)
                await close_reauth(self.hass, entry)
                await self._also_for_other_lines(entry, key, user_input)
                return self._key_done()
            errors["base"] = error
        schema: dict[Any, Any] = {vol.Required(CONF_API_KEY): str, **self._all_lines_field(entry)}
        return self.async_show_form(
            step_id="token",
            data_schema=_form(schema),
            errors=errors,
            description_placeholders={"line": line_label(entry), "portal": KEY_PORTAL_URL},
        )


# Home Assistant awaits this function with these arguments, so it has to be a coroutine function that takes all three.
async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None) -> RepairsFlow:  # NOSONAR
    """The fix flow of a fixable notice of this integration: both of them are about an old key, and carry the entry."""
    entry_id = (data or {}).get("entry_id")
    return LegacyKeyRepairFlow(entry_id if isinstance(entry_id, str) else None)
