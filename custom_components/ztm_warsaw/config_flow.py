import logging
import re

import voluptuous as vol

from types import MappingProxyType

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError
from homeassistant.config_entries import ConfigSubentry, ConfigSubentryData, ConfigSubentryFlow
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import ZTMApiError, ZTMAuthError, ZTMStopClient, key_kind, user_agent
from .entries import SUBENTRY_STOP, entry_api_key, is_line_entry, line_of, stop_keys, stop_units
from .const import KEY_PORTAL_URL, NEXT_DEPARTURES, DOMAIN, CONF_API_KEY, CONF_BUSSTOP_ID, CONF_BUSSTOP_NR, CONF_LINE, CONF_DEPARTURES

_LOGGER = logging.getLogger(__name__)

class KeyWorks(ValueError):
    """The City accepted the key and answered, but not with something to show (the line is not in its list, an empty
    timetable). Setup refuses it like any other ValueError; a reauth only wants to know that the key works."""

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): str,
    vol.Required(CONF_BUSSTOP_ID): vol.Coerce(int),
    vol.Required(CONF_BUSSTOP_NR): str,
    vol.Required(CONF_LINE): str,
})


async def _check_lines(client, line):
    """The line must stop at the pole. When the request fails on the new API (which answers every rejected request
    alike) the catalogue tells a stop that does not exist from a service that is down."""
    try:
        lines = await client.get_lines()
    except ZTMAuthError:
        raise
    except ZTMApiError:
        raise ValueError("line_not_found") from None
    if lines is None:
        known = await client.stop_in_catalogue() if client.uses_token else True
        if known is None:
            raise ValueError("invalid_token_or_unavailable")
        raise ValueError("line_not_found" if known is False else "api_connection_error")
    if line not in lines:
        raise KeyWorks("line_not_found")


async def _check_timetable(client):
    try:
        data = await client.get(fetch_stop_name=False)
    except ZTMAuthError:
        raise
    except ZTMApiError:
        raise ValueError("no_valid_times") from None
    if data is None:
        raise ValueError("api_connection_error")
    if not data.departures:
        raise KeyWorks("no_departures")


async def validate_input(hass, api_key, stop_id, stop_nr, line):
    """Check the input against the City of Warsaw API with the client the sensor uses. Raises ValueError(<error key>).

    A key that is neither a UUID (old API) nor a token (new API) is refused before anything is sent.
    """
    if key_kind(api_key) is None:
        raise ValueError("invalid_api_key")
    client = ZTMStopClient(
        async_get_clientsession(hass), api_key, str(stop_id), stop_nr, line, user_agent=await user_agent(hass)
    )
    try:
        await _check_lines(client, line)
        await _check_timetable(client)
    except ZTMAuthError:
        raise ValueError("invalid_api_key") from None


async def error_for(hass, user_input, *, check_stop_number=True) -> tuple[str | None, bool]:
    """``(error key, key works)`` for this input: the error is None when it is valid, and ``key works`` says that an
    error still proves the City accepted the key (the line does not run today, say). Logs what went wrong, never the key."""
    if check_stop_number and not re.fullmatch(r"\d{2}", user_input[CONF_BUSSTOP_NR], re.ASCII):
        return "invalid_stop_number", False
    unexpected = None
    key_works = False
    try:
        await validate_input(
            hass,
            user_input[CONF_API_KEY],
            user_input[CONF_BUSSTOP_ID],
            user_input[CONF_BUSSTOP_NR],
            user_input[CONF_LINE],
        )
        return None, True
    except ValueError as err:
        key = str(err)
        key_works = isinstance(err, KeyWorks)
    except Exception as err:
        # Only the class: the text or the traceback of an unexpected error can carry the URL, and the key.
        unexpected, key = type(err).__name__, "unknown"
    if unexpected:
        _LOGGER.error("Unexpected error during validation: %s", unexpected)
    else:
        _LOGGER.warning("Validation error: %s", key)
    return key, key_works


class ZtmWarsawConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    VERSION = 2  # a line with its stops as subentries; a version 1 entry (one stop) is still read as it was

    async def _error_for(self, user_input, *, check_stop_number=True):
        """The error key for this input, or None when it is valid (see ``error_for``).
        ``self.key_works`` tells afterwards whether the error still proves that the City accepted the key."""
        error, self.key_works = await error_for(self.hass, user_input, check_stop_number=check_stop_number)
        return error

    def _is_configured(self, key):
        return any(key in stop_keys(entry) for entry in self._async_current_entries())

    def _entry_of_line(self, line):
        """The line entry that already runs this line, if any: a new stop of the line goes into it."""
        return next((e for e in self._async_current_entries() if is_line_entry(e) and line_of(e) == line), None)

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            user_input = {k: v.strip() if isinstance(v, str) else v for k, v in user_input.items()}
            new_key = (str(user_input[CONF_BUSSTOP_ID]), user_input[CONF_BUSSTOP_NR], user_input[CONF_LINE])
            if self._is_configured(new_key):
                return self.async_abort(reason="already_configured")  # a second sensor of the same stop, pole and line cannot exist
            existing = self._entry_of_line(user_input[CONF_LINE])
            if existing is not None:  # one more stop of a line that is set up: it is asked with the key that line has
                user_input = {**user_input, CONF_API_KEY: entry_api_key(existing) or user_input[CONF_API_KEY]}
            error = await self._error_for(user_input)
            if error is None:
                if self._is_configured(new_key):  # another flow may have finished while the City was being asked
                    return self.async_abort(reason="already_configured")
                stop = ConfigSubentryData(
                    subentry_type=SUBENTRY_STOP,
                    title=f"{user_input[CONF_BUSSTOP_ID]}/{user_input[CONF_BUSSTOP_NR]}",  # the stop's name replaces it once known
                    data={CONF_BUSSTOP_ID: user_input[CONF_BUSSTOP_ID], CONF_BUSSTOP_NR: user_input[CONF_BUSSTOP_NR]},
                    unique_id=_stop_unique_id(user_input[CONF_BUSSTOP_ID], user_input[CONF_BUSSTOP_NR]),
                )
                existing = self._entry_of_line(user_input[CONF_LINE])
                if existing is not None:  # the line is set up already: this is one more stop of it
                    try:
                        self.hass.config_entries.async_add_subentry(existing, _subentry(stop))
                    except HomeAssistantError:  # another flow added the same stop while the City was being asked
                        return self.async_abort(reason="already_configured")
                    return self.async_abort(reason="stop_added")
                # The number of departures is no longer asked (3 are always listed); the key stays in the data as it was.
                return self.async_create_entry(
                    title=f"Line {user_input[CONF_LINE]}",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_LINE: user_input[CONF_LINE],
                        CONF_DEPARTURES: NEXT_DEPARTURES,
                    },
                    subentries=[stop],
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask for a new API key or token for an entry whose key the City rejects; the rest of the entry stays."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None or not _key_can_change(entry):
            return self.async_abort(reason="unknown")
        errors = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            error, self.key_works = await _key_error(self.hass, entry, key)
            if error is None or self.key_works:  # that the line does not run today is not the key's fault
                loaded = entry.state is config_entries.ConfigEntryState.LOADED  # read first: the update may start a reload
                changed = self.hass.config_entries.async_update_entry(entry, **_with_key(entry, key))
                # A loaded entry reloads itself through its update listener, but only when its data changed (the same
                # key again, after the City had recovered, is a reload the listener does not do).
                if not (loaded and changed):
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ZtmWarsawOptionsFlow(config_entry)

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry):
        # Only a line has stops to add; an entry of 1.1.x is one stop and has no "Add stop".
        return {SUBENTRY_STOP: ZtmStopSubentryFlow} if is_line_entry(config_entry) else {}


def _subentry(stop: ConfigSubentryData) -> ConfigSubentry:
    return ConfigSubentry(
        subentry_type=stop["subentry_type"],
        title=stop["title"],
        data=MappingProxyType(stop["data"]),
        unique_id=stop.get("unique_id"),
    )


def _stop_unique_id(stop_id, stop_nr) -> str:
    return f"{stop_id}_{stop_nr}"


def _key_can_change(entry) -> bool:
    """An entry whose data cannot be read is not changed blindly: a 1.1.x entry needs its stop, a line needs only its key."""
    return entry_api_key(entry) is not None and (is_line_entry(entry) or bool(stop_units(entry)))


async def _key_error(hass, entry, key: str) -> tuple[str | None, bool]:
    """``(error key, key works)`` for a new key of this entry (see ``error_for``): the City is asked with the entry's stop,
    or with the first stop of a line. A line that has no stop left has only the shape of the key to check."""
    units = stop_units(entry)
    if not units:
        return (None, True) if key_kind(key) is not None else ("invalid_api_key", False)
    unit = units[0]
    return await error_for(
        hass,
        {CONF_API_KEY: key, CONF_BUSSTOP_ID: unit.stop_id, CONF_BUSSTOP_NR: unit.stop_nr, CONF_LINE: unit.line},
        check_stop_number=False,  # an old entry keeps the number it has; only the key is asked for here
    )


def _host_of(api_key: str) -> str:
    """The City host the key belongs to, for the Configure form (neutral in every language); '?' for a key of neither kind."""
    kind = key_kind(api_key)
    if kind == "legacy":
        return "api.um.warszawa.pl"
    return "dane.um.warszawa.pl" if kind is not None else "?"


# The spellings of the key that the setup reads (see _entry_values); an option with one of them overrides the data.
_KEY_SPELLINGS = ("api_key", "apikey", "apiKey")


def _with_key(entry, key: str) -> dict:
    """The ``data`` and ``options`` of the entry with ``key`` as its key: the canonical field of the data is set and an
    option that overrides it (a restored entry may have one: options win over data) is dropped, so the new key is used."""
    return {
        "data": {**entry.data, CONF_API_KEY: key},
        "options": {k: v for k, v in entry.options.items() if k not in _KEY_SPELLINGS},
    }


async def _close_reauth(hass, entry) -> None:
    """A re-authentication that was waiting for this key is done. Home Assistant 2026.10 closes it when the entry reloads;
    older versions leave the flow open, and aborting a flow through the manager does not remove the Repairs issue and the
    notification that went with it, so they are cleared here (what Home Assistant itself does when it removes an entry)."""
    flows = hass.config_entries.flow
    for flow in flows.async_progress_by_handler(DOMAIN, match_context={"entry_id": entry.entry_id, "source": "reauth"}):
        flows.async_abort(flow["flow_id"])
    ir.async_delete_issue(hass, HOMEASSISTANT_DOMAIN, f"config_entry_reauth_{entry.domain}_{entry.entry_id}")
    if not flows.async_progress_by_handler(DOMAIN, match_context={"source": "reauth"}) and hass.services.has_service(
        "persistent_notification", "dismiss"
    ):
        await hass.services.async_call(
            "persistent_notification", "dismiss", {"notification_id": "config_entry_reconfigure"}, blocking=True
        )


class ZtmWarsawOptionsFlow(config_entries.OptionsFlow):
    """*Configure*: replace the API key or token of the entry, e.g. an old key by a token of the new API."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return await self._change_key(user_input)

    async def async_step_token(self, user_input=None):
        """The same step for an entry that already has a token: its form does not ask for an old key."""
        return await self._change_key(user_input)

    async def _change_key(self, user_input):
        entry = self._config_entry
        api_key = entry_api_key(entry)
        if api_key is None or not _key_can_change(entry):
            return self.async_abort(reason="unknown")
        errors = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            error, works = await _key_error(self.hass, entry, key)
            if error is None or works:  # that the line does not run today is not the key's fault
                loaded = entry.state is config_entries.ConfigEntryState.LOADED  # read first: the update may start a reload
                changed = self.hass.config_entries.async_update_entry(entry, **_with_key(entry, key))
                # A loaded entry reloads itself through its update listener when its data changed; any other state has
                # no listener (the setup failed or is being retried), and the same key again is no change: reload it.
                if not (loaded and changed):
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                await _close_reauth(self.hass, entry)
                return self.async_create_entry(title="", data=dict(entry.options))
            errors["base"] = error
        return self.async_show_form(
            step_id="init" if key_kind(api_key) == "legacy" else "token",  # an old key is nudged to the token, a token is not
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={"current": _host_of(api_key), "portal": KEY_PORTAL_URL},
        )


class ZtmStopSubentryFlow(ConfigSubentryFlow):
    """*Add stop*: another stop (and pole) of the line, asked with the key the line already has."""

    async def async_step_user(self, user_input=None):
        entry = self._get_entry()
        api_key, line = entry_api_key(entry), line_of(entry)
        if api_key is None or line is None:
            return self.async_abort(reason="unknown")
        errors = {}
        if user_input is not None:
            stop_id, stop_nr = user_input[CONF_BUSSTOP_ID], user_input[CONF_BUSSTOP_NR].strip()  # the stop id is an int
            if any((str(stop_id), stop_nr, line) in stop_keys(e) for e in self.hass.config_entries.async_entries(DOMAIN)):
                return self.async_abort(reason="already_configured")
            error, _ = await error_for(
                self.hass, {CONF_API_KEY: api_key, CONF_BUSSTOP_ID: stop_id, CONF_BUSSTOP_NR: stop_nr, CONF_LINE: line}
            )
            if error is None:
                if any((str(stop_id), stop_nr, line) in stop_keys(e) for e in self.hass.config_entries.async_entries(DOMAIN)):
                    return self.async_abort(reason="already_configured")  # added by another flow while the City was asked
                return self.async_create_entry(
                    title=f"{stop_id}/{stop_nr}",
                    data={CONF_BUSSTOP_ID: stop_id, CONF_BUSSTOP_NR: stop_nr},
                    unique_id=_stop_unique_id(stop_id, stop_nr),
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_BUSSTOP_ID): vol.Coerce(int), vol.Required(CONF_BUSSTOP_NR): str}),
            errors=errors,
            description_placeholders={"line": line or ""},
        )
