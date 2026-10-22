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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .client import key_kind
from .config_flow import close_reauth, key_can_change, key_error, save_key
from .const import CONF_API_KEY, DOMAIN, KEY_PORTAL_URL
from .entries import entry_api_key, line_of, stop_units


CONF_ALL_LINES = "all_lines"  # the checkbox of the paste step: use the token for every line that still has an old key
CONF_TOKEN = "token"  # the field of the step that picks one of several tokens (the number of the token in the list shown)


class LegacyKeyRepairFlow(RepairsFlow):
    """Ask for a token to replace the old key of an entry and save it."""

    def __init__(self, entry_id: str | None) -> None:
        """Remember the entry whose key is replaced (the issue carries its ID)."""
        super().__init__()
        self._entry_id = entry_id

    def _line_of_entry(self, entry: ConfigEntry) -> str:
        """The line of the entry whose key is replaced, for the texts of the dialog."""
        units = stop_units(entry)
        return line_of(entry) or (units[0].line if units else "")

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> Any:  # the result type differs between Home Assistant versions
        """The first step: Home Assistant calls it with the data of the issue, not with a form, so it offers the two ways out:
        paste a token, or ignore the notice (a fixable notice has no *Ignore* button in the Repairs list). Aborts when the entry is gone."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id) if self._entry_id else None
        if entry is None or not key_can_change(entry):
            return self.async_abort(reason="unknown")
        options = ["token", "reuse", "ignore"] if self._tokens(entry) else ["token", "ignore"]
        return self.async_show_menu(
            step_id="init",
            menu_options=options,
            description_placeholders={"line": self._line_of_entry(entry), "portal": KEY_PORTAL_URL},
        )

    def _others(self, entry: ConfigEntry) -> list[ConfigEntry]:
        """The other entries of the integration, whose key can be read."""
        return [e for e in self.hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id and entry_api_key(e)]

    def _tokens(self, entry: ConfigEntry) -> list[tuple[str, list[str]]]:
        """The different tokens the other entries of the integration have, each with the lines that use it, in the order they
        are met (a token is the account's: one serves every line, but there may be more than one account's)."""
        found: dict[str, list[str]] = {}
        for other in self._others(entry):
            key = entry_api_key(other) or ""
            if key_kind(key) == "token":
                lines = found.setdefault(key, [])
                line = self._line_of_entry(other)
                if line and line not in lines:
                    lines.append(line)
        return list(found.items())

    def _legacy_others(self, entry: ConfigEntry) -> list[ConfigEntry]:
        """The other entries that still have an old key and could take the new token as well."""
        return [e for e in self._others(entry) if key_kind(entry_api_key(e) or "") == "legacy" and key_can_change(e)]

    async def async_step_reuse(self, user_input: dict[str, str] | None = None) -> Any:  # the result type differs between Home Assistant versions
        """Use the token another line already has: checked for this line like a pasted one, never shown. Aborts when the City does
        not accept it for this line (then pasting another is still possible by opening the notice again)."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id) if self._entry_id else None
        tokens = self._tokens(entry) if entry is not None else []
        if entry is None or not key_can_change(entry) or not tokens:
            return self.async_abort(reason="unknown")
        if len(tokens) == 1:
            return await self._use(entry, tokens[0][0])
        choices = {str(n): f"…{key[-4:]}  ·  {', '.join(lines) or '-'}" for n, (key, lines) in enumerate(tokens)}
        if user_input is not None and user_input.get(CONF_TOKEN) in choices:
            return await self._use(entry, tokens[int(user_input[CONF_TOKEN])][0])
        return self.async_show_form(
            step_id="reuse",
            data_schema=cast("Any", vol.Schema({vol.Required(CONF_TOKEN): vol.In(choices)})),  # Home Assistant 2026.10 types it for another schema library
            description_placeholders={"line": self._line_of_entry(entry)},
        )

    async def _use(self, entry: ConfigEntry, token: str) -> Any:  # the result type differs between Home Assistant versions
        """Give the entry this token, checked for its line like a pasted one (the token is never shown)."""
        error, works = await key_error(self.hass, entry, token)
        if error is not None and not works:
            return self.async_abort(reason="reuse_rejected")
        save_key(self.hass, entry, token)
        await close_reauth(self.hass, entry)
        return self.async_create_entry(data={})

    async def _also_for_other_lines(self, entry: ConfigEntry, key: str) -> None:
        """Give the token to every other line that still has an old key, where the City accepts it for that line."""
        for other in self._legacy_others(entry):
            error, works = await key_error(self.hass, other, key)
            if error is None or works:
                save_key(self.hass, other, key)
                await close_reauth(self.hass, other)

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
                if user_input.get(CONF_ALL_LINES) and key_kind(key) == "token":
                    await self._also_for_other_lines(entry, key)
                return self.async_create_entry(data={})
            errors["base"] = error
        line = self._line_of_entry(entry)
        schema: dict[Any, Any] = {vol.Required(CONF_API_KEY): str}
        if self._legacy_others(entry):  # asked only when there is another line that still has an old key
            schema[vol.Optional(CONF_ALL_LINES, default=True)] = bool
        return self.async_show_form(
            step_id="token",
            data_schema=cast("Any", vol.Schema(schema)),  # Home Assistant 2026.10 types it for another schema library
            errors=errors,
            description_placeholders={"line": line, "portal": KEY_PORTAL_URL},
        )


# Home Assistant awaits this function with these arguments, so it has to be a coroutine function that takes all three.
async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None) -> RepairsFlow:  # NOSONAR
    """The fix flow of a fixable notice of this integration: both of them are about an old key, and carry the entry."""
    entry_id = (data or {}).get("entry_id")
    return LegacyKeyRepairFlow(entry_id if isinstance(entry_id, str) else None)
