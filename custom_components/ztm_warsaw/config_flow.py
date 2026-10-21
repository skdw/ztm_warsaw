"""The dialogs of the integration: adding a line and its first stop, adding another stop, changing the key.

Every key typed here is checked with the City before anything is saved, and a key is never logged or put into an
error. ``ZtmWarsawConfigFlow`` creates a line entry (or adds a stop to the one that exists), ``ZtmStopSubentryFlow``
is *Add stop* on an entry, ``ZtmWarsawOptionsFlow`` is *Configure* (a new key for the whole line), and the reauth
step asks for a new key when the City rejects the old one.
"""

import logging
import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from types import MappingProxyType

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import SEARCH_LIMIT, StopCatalogue, ZTMApiError, ZTMAuthError, ZTMStopClient, key_kind, user_agent
from .entries import SUBENTRY_STOP, walking_minutes_of, entry_api_key, is_line_entry, line_of, stop_keys, stop_units
from .const import (
    CONF_API_KEY,
    CONF_BUSSTOP_ID,
    CONF_BUSSTOP_NR,
    CONF_DEPARTURES,
    CONF_LINE,
    CONF_WALKING_TIME,
    DOMAIN,
    KEY_PORTAL_URL,
    MAX_WALKING_TIME,
    NEXT_DEPARTURES,
)

_LOGGER = logging.getLogger(__name__)

class KeyWorks(ValueError):
    """The City accepted the key and answered, but not with something to show (the line is not in its list, an empty
    timetable). Setup refuses it like any other ValueError; a reauth only wants to know that the key works."""

def _form(fields: dict[Any, Any]) -> Any:
    """The schema of a form (Home Assistant 2026.10 types a form's schema for another schema library, hence ``Any``)."""
    return vol.Schema(fields)


CONF_STOP = "stop"  # the form fields of the setup dialog that are not stored: what to search for, the pole picked, "I know the numbers"
CONF_POLE = "pole"
CONF_MANUAL = "manual"


async def _client_for_catalogue(hass: HomeAssistant, key: str, stop_id: str = "0", stop_nr: str = "0") -> tuple[ZTMStopClient, StopCatalogue]:
    """A client with this key (any stop: the catalogue and the list of lines at a pole need none) and the catalogue every entry shares."""
    catalogue: StopCatalogue = hass.data.setdefault(f"{DOMAIN}_catalogue", StopCatalogue())
    client = ZTMStopClient(async_get_clientsession(hass), key, stop_id, stop_nr, "0", user_agent=await user_agent(hass), catalogue=catalogue)
    return client, catalogue


async def search_poles(hass: HomeAssistant, key: str, query: str) -> tuple[bool | None, list[dict[str, Any]]]:
    """``(readable, poles)`` for what the user typed: see ``StopCatalogue.search``."""
    client, catalogue = await _client_for_catalogue(hass, key)
    return await catalogue.search(client, query)


async def lines_at(hass: HomeAssistant, key: str, stop_id: str, stop_nr: str) -> list[str] | None:
    """The lines that stop at this pole today, in the order a person reads them (numbers first); None when the City did not say.
    A rejected key is raised as ``ZTMAuthError``."""
    client, _ = await _client_for_catalogue(hass, key, stop_id, stop_nr)
    try:
        lines = await client.get_lines()
    except ZTMAuthError:
        raise
    except ZTMApiError:
        return None
    if lines is None:
        return None
    return sorted(set(lines), key=lambda line: (0, int(line), line) if line.isdigit() else (1, 0, line))


def pole_options(poles: list[dict[str, Any]]) -> list[SelectOptionDict]:
    """The choices of the pole step: "Marcelin 01 → Metro Wilanowska" (the arrow and the numbers are the same in every language)."""
    return [
        SelectOptionDict(
            value=f"{p['stop_id']}/{p['stop_nr']}",
            label=f"{p['name']} {p['stop_nr']}" + (f" → {p['direction']}" if p["direction"] else "") + f" ({p['stop_id']}/{p['stop_nr']})",
        )
        for p in poles
    ]


def _select(options: list[SelectOptionDict]) -> Any:
    """A list to pick from (Home Assistant draws the choices as rows)."""
    return SelectSelector(SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST))


async def _check_lines(client: ZTMStopClient, line: str) -> None:
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


async def _check_timetable(client: ZTMStopClient) -> None:
    """The timetable must come back with departures: ``ValueError`` for the error key to show, ``KeyWorks`` when the City
    accepted the key but the line has no departures today. A rejected key is passed on as ``ZTMAuthError``.
    """
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


async def validate_input(hass: HomeAssistant, api_key: str, stop_id: str | int, stop_nr: str, line: str) -> None:
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


async def error_for(hass: HomeAssistant, user_input: Mapping[str, Any], *, check_stop_number: bool = True) -> tuple[str | None, bool]:
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


class ZtmWarsawConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg,unused-ignore]
    """The dialog that adds a line (or, for a line that is set up, one more stop of it)."""

    VERSION = 2  # a line with its stops as subentries; a version 1 entry (one stop) is converted into a line at startup (migration.py)

    async def _error_for(self, user_input: Mapping[str, Any], *, check_stop_number: bool = True) -> str | None:
        """The error key for this input, or None when it is valid (see ``error_for``).
        ``self.key_works`` tells afterwards whether the error still proves that the City accepted the key."""
        error, self.key_works = await error_for(self.hass, user_input, check_stop_number=check_stop_number)
        return error

    def _is_configured(self, key: tuple[str, str, str]) -> bool:
        """Whether a stop, pole and line is already run by an entry (a 1.1.x entry or a line); a second sensor for it could not exist."""
        return any(key in stop_keys(entry) for entry in self._async_current_entries())

    def _entry_of_line(self, line: str) -> ConfigEntry | None:
        """The line entry that already runs this line, if any: a new stop of the line goes into it."""
        return next((e for e in self._async_current_entries() if is_line_entry(e) and line_of(e) == line), None)

    def _create_or_add(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """The input is valid: a new line is an entry with this stop, a line that is set up gets one more stop."""
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

    def __init__(self) -> None:
        """What the steps of the dialog hand on to each other: the key, what was searched for, the poles found and the one picked."""
        self._key = ""
        self._query = ""
        self._poles: list[dict[str, Any]] = []
        self._pole: tuple[str, str] = ("", "")
        self._lines: list[str] = []

    def _user_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """The first step: the key and part of the stop's name (or its ID), or "I know the numbers"."""
        schema = _form(
            {
                vol.Required(CONF_API_KEY, default=self._key): str,
                vol.Required(CONF_STOP, default=self._query): str,
                vol.Optional(CONF_MANUAL, default=False): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors or {})

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The first screen: the key and part of the stop's name. The catalogue of stops is searched, and the poles found are
        offered next; "I know the numbers" (or a catalogue that cannot be read) leads to the form of the numbers."""
        if user_input is None:
            return self._user_form()
        self._key, self._query = user_input[CONF_API_KEY].strip(), user_input[CONF_STOP].strip()
        if key_kind(self._key) is None:
            return self._user_form({"base": "invalid_api_key"})
        if user_input.get(CONF_MANUAL):
            return await self.async_step_manual()
        readable, poles = await search_poles(self.hass, self._key, self._query)
        if readable is not True:  # the list of stops could not be read: the numbers can still be typed
            return self._manual_form({"base": "cannot_load_stops"})
        if not poles:
            return self._user_form({"base": "no_stop_found"})
        if len(poles) > SEARCH_LIMIT:
            return self._user_form({"base": "too_many_matches"})
        self._poles = poles
        return await self.async_step_pole()

    def _pole_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """The second step: which of the poles found."""
        return self.async_show_form(
            step_id="pole",
            data_schema=_form({vol.Required(CONF_POLE): _select(pole_options(self._poles))}),
            errors=errors or {},
            description_placeholders={"query": self._query},
        )

    async def async_step_pole(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """Which pole: the stop's name and its direction, from the catalogue."""
        if user_input is None:
            return self._pole_form()
        stop_id, stop_nr = user_input[CONF_POLE].split("/")
        self._pole = (stop_id, stop_nr)
        self._lines = []
        return await self.async_step_line()

    def _line_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """The third step: which of the lines that stop at the pole."""
        stop_id, stop_nr = self._pole
        return self.async_show_form(
            step_id="line",
            data_schema=_form({vol.Required(CONF_LINE): _select([SelectOptionDict(value=line, label=line) for line in self._lines])}),
            errors=errors or {},
            description_placeholders={"stop": f"{stop_id}/{stop_nr}"},
        )

    async def async_step_line(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """Which line: only those the City lists at the pole today. Then the same checks as the form of the numbers."""
        stop_id, stop_nr = self._pole
        if user_input is None:
            try:
                lines = await lines_at(self.hass, self._key, stop_id, stop_nr)
            except ZTMAuthError:
                return self._user_form({"base": "invalid_api_key"})
            if lines is None:
                return self._pole_form({"base": "cannot_load_lines"})
            if not lines:
                return self._pole_form({"base": "no_lines"})
            self._lines = lines
            return self._line_form()
        outcome = await self._finish(
            {CONF_API_KEY: self._key, CONF_BUSSTOP_ID: int(stop_id), CONF_BUSSTOP_NR: stop_nr, CONF_LINE: user_input[CONF_LINE]}
        )
        return outcome if not isinstance(outcome, str) else self._line_form({"base": outcome})

    async def _finish(self, user_input: dict[str, Any]) -> ConfigFlowResult | str:
        """Check the stop, pole and line with the City and make the entry (or add the stop to the line's entry): the result, or the
        key of the error to show."""
        new_key = (str(user_input[CONF_BUSSTOP_ID]), user_input[CONF_BUSSTOP_NR], user_input[CONF_LINE])
        if self._is_configured(new_key):
            return self.async_abort(reason="already_configured")  # a second sensor of the same stop, pole and line cannot exist
        existing = self._entry_of_line(user_input[CONF_LINE])
        if existing is not None:  # one more stop of a line that is set up: it is asked with the key that line has
            user_input = {**user_input, CONF_API_KEY: entry_api_key(existing) or user_input[CONF_API_KEY]}
        error = await self._error_for(user_input)
        if error is not None:
            return error
        if self._is_configured(new_key):  # another flow may have finished while the City was being asked
            return self.async_abort(reason="already_configured")
        return self._create_or_add(user_input)

    def _manual_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """The form of the numbers: the key, the stop ID, the pole and the line typed."""
        schema = _form(
            {
                vol.Required(CONF_API_KEY, default=self._key): str,
                vol.Required(CONF_BUSSTOP_ID): vol.Coerce(str),  # a text, so the form starts empty; stored as the number it is
                vol.Required(CONF_BUSSTOP_NR): str,
                vol.Required(CONF_LINE): str,
            }
        )
        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors or {})

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The form of the numbers: the stop ID, the pole and the line typed by someone who knows them (or when the list of stops
        cannot be read): checked with the City, then an entry with the stop, or one more stop in the line's entry."""
        if user_input is None:
            return self._manual_form()
        user_input = {k: v.strip() if isinstance(v, str) else v for k, v in user_input.items()}
        self._key = user_input[CONF_API_KEY]
        stop_id = _stop_id_of(user_input[CONF_BUSSTOP_ID])
        if stop_id is None:
            return self._manual_form({"base": "invalid_stop_id"})
        user_input[CONF_BUSSTOP_ID] = stop_id
        outcome = await self._finish(user_input)
        return outcome if not isinstance(outcome, str) else self._manual_form({"base": outcome})

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Home Assistant starts this when the City rejects the key of an entry: it asks for a new key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """Ask for a new API key or token for an entry whose key the City rejects; the rest of the entry stays."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None or not key_can_change(entry):
            return self.async_abort(reason="unknown")
        errors = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            error, self.key_works = await key_error(self.hass, entry, key)
            if error is None or self.key_works:  # that the line does not run today is not the key's fault
                save_key(self.hass, entry, key)
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=_form({vol.Required(CONF_API_KEY): str}), errors=errors
        )

    async def async_step_reconfigure(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """*Reconfigure* on a line (Home Assistant's own menu item): replace its API key or token, nudging an old key to a token."""
        return await self._reconfigure_key(user_input)

    async def async_step_reconfigure_token(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """The same step for an entry that already has a token: its form does not ask for an old key."""
        return await self._reconfigure_key(user_input)

    async def _reconfigure_key(self, user_input: dict[str, str] | None) -> ConfigFlowResult:
        """Ask for the new key (the same check and the same saving as *Configure* and the notice in Repairs), then end the flow;
        the entry reloads once with it and a reauth that was waiting for it is closed."""
        entry = self._get_reconfigure_entry()
        api_key = entry_api_key(entry)
        if api_key is None or not key_can_change(entry):
            return self.async_abort(reason="unknown")
        errors = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            error, works = await key_error(self.hass, entry, key)
            if error is None or works:  # that the line does not run today is not the key's fault
                save_key(self.hass, entry, key)
                await close_reauth(self.hass, entry)
                return self.async_abort(reason="reconfigure_successful")
            errors["base"] = error
        return self.async_show_form(
            step_id="reconfigure" if key_kind(api_key) == "legacy" else "reconfigure_token",
            data_schema=_form({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={"current": _host_of(api_key), "portal": KEY_PORTAL_URL},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "ZtmWarsawOptionsFlow":
        """Home Assistant asks for the *Configure* dialog of an entry here."""
        return ZtmWarsawOptionsFlow(config_entry)

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        """The subentry dialogs of an entry: *Add stop* on a line; an entry of 1.1.x (one stop) has no stops to add."""
        # Only a line has stops to add; an entry of 1.1.x is one stop and has no "Add stop".
        return {SUBENTRY_STOP: ZtmStopSubentryFlow} if is_line_entry(config_entry) else {}


def _subentry(stop: ConfigSubentryData) -> ConfigSubentry:
    """The ``ConfigSubentry`` of a stop from its description (the dialog creates the entry with the description, an added stop needs the object)."""
    return ConfigSubentry(
        subentry_type=stop["subentry_type"],
        title=stop["title"],
        data=MappingProxyType(stop["data"]),
        unique_id=stop.get("unique_id"),
    )


def _stop_id_of(value: object) -> int | None:
    """The stop ID typed in a form as the number the entry stores, or None when it is not one (up to nine digits, spaces around are removed)."""
    text = str(value).strip()
    return int(text) if text.isascii() and text.isdigit() and len(text) <= 9 else None  # a longer one cannot be a stop


def _stop_unique_id(stop_id: str | int, stop_nr: str) -> str:
    """The unique ID of a stop's subentry: ``<stop id>_<pole number>``, which is also what makes a stop impossible to add twice."""
    return f"{stop_id}_{stop_nr}"


def key_can_change(entry: ConfigEntry) -> bool:
    """An entry whose data cannot be read is not changed blindly: a 1.1.x entry needs its stop, a line needs only its key."""
    return entry_api_key(entry) is not None and (is_line_entry(entry) or bool(stop_units(entry)))


async def key_error(hass: HomeAssistant, entry: ConfigEntry, key: str) -> tuple[str | None, bool]:
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


def _with_key(entry: ConfigEntry, key: str) -> dict[str, Any]:
    """The ``data`` and ``options`` of the entry with ``key`` as its key: the canonical field of the data is set and an
    option that overrides it (a restored entry may have one: options win over data) is dropped, so the new key is used."""
    return {
        "data": {**entry.data, CONF_API_KEY: key},
        "options": {k: v for k, v in entry.options.items() if k not in _KEY_SPELLINGS},
    }


def save_key(hass: HomeAssistant, entry: ConfigEntry, key: str) -> None:
    """Save a new key in the entry and make sure the entry runs with it.

    A loaded entry reloads itself through its update listener when its data changed; any other state has no listener (the
    setup failed or is being retried), and the same key again is no change: it is reloaded here."""
    loaded = entry.state is config_entries.ConfigEntryState.LOADED  # read first: the update may start a reload
    changed = hass.config_entries.async_update_entry(entry, **_with_key(entry, key))
    if not (loaded and changed):
        hass.config_entries.async_schedule_reload(entry.entry_id)


async def close_reauth(hass: HomeAssistant, entry: ConfigEntry) -> None:
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

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Keep the entry whose key is changed."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """The step of *Configure* for an entry with an old (UUID) key: the form for the new key, nudging to a token. An entry that has a token gets ``async_step_token``; both go through ``_change_key``."""
        return await self._change_key(user_input)

    async def async_step_token(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """The same step for an entry that already has a token: its form does not ask for an old key."""
        return await self._change_key(user_input)

    async def _change_key(self, user_input: dict[str, str] | None) -> ConfigFlowResult:
        """Ask for the new key (the nudge to a token for an old key, a plain form for a token), check it with the City and save it.

        The entry reloads once with the new key; a reauth that was waiting for it is closed.
        """
        entry = self._config_entry
        api_key = entry_api_key(entry)
        if api_key is None or not key_can_change(entry):
            return self.async_abort(reason="unknown")
        errors = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            error, works = await key_error(self.hass, entry, key)
            if error is None or works:  # that the line does not run today is not the key's fault
                save_key(self.hass, entry, key)
                await close_reauth(self.hass, entry)
                return self.async_create_entry(title="", data=dict(entry.options))
            errors["base"] = error
        return self.async_show_form(
            step_id="init" if key_kind(api_key) == "legacy" else "token",  # an old key is nudged to the token, a token is not
            data_schema=_form({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={"current": _host_of(api_key), "portal": KEY_PORTAL_URL},
        )


class ZtmStopSubentryFlow(ConfigSubentryFlow):
    """*Add stop*: another stop (and pole) of the line, asked with the key the line already has."""

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """*Reconfigure* on a stop: how many minutes it takes to walk to it. The sensor of the stop then skips the departures
        that are sooner than that (they cannot be caught); 0 is no walking time, the default."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            data = {**subentry.data, CONF_WALKING_TIME: int(user_input[CONF_WALKING_TIME])}
            return self.async_update_and_abort(entry, subentry, data=data)
        schema = _form(
            {
                vol.Required(CONF_WALKING_TIME, default=walking_minutes_of(subentry.data)): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=MAX_WALKING_TIME, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                )
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, description_placeholders={"stop": subentry.title})

    def __init__(self) -> None:
        """What the steps hand on to each other: what was searched for and the poles found."""
        self._query = ""
        self._poles: list[dict[str, Any]] = []

    def _line_and_key(self) -> tuple[str, str] | None:
        """The line of the entry and its key (the line is fixed: only the stop is asked), or None when the entry cannot be read."""
        entry = self._get_entry()
        api_key, line = entry_api_key(entry), line_of(entry)
        return (line, api_key) if api_key is not None and line is not None else None

    def _user_form(self, line: str, errors: dict[str, str] | None = None) -> SubentryFlowResult:
        """The first step: part of the stop's name (or its ID), or "I know the numbers"."""
        schema = _form({vol.Required(CONF_STOP, default=self._query): str, vol.Optional(CONF_MANUAL, default=False): bool})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors or {}, description_placeholders={"line": line})

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """*Add stop*: part of the stop's name; the catalogue is searched and the poles found are offered next (a catalogue that
        cannot be read, or "I know the numbers", leads to the form of the numbers)."""
        known = self._line_and_key()
        if known is None:
            return self.async_abort(reason="unknown")
        line, api_key = known
        if user_input is None:
            return self._user_form(line)
        self._query = user_input[CONF_STOP].strip()
        if user_input.get(CONF_MANUAL):
            return await self.async_step_manual()
        readable, poles = await search_poles(self.hass, api_key, self._query)
        if readable is not True:
            return self._manual_form(line, {"base": "cannot_load_stops"})
        if not poles:
            return self._user_form(line, {"base": "no_stop_found"})
        if len(poles) > SEARCH_LIMIT:
            return self._user_form(line, {"base": "too_many_matches"})
        self._poles = poles
        return await self.async_step_pole()

    async def async_step_pole(self, user_input: dict[str, str] | None = None) -> SubentryFlowResult:
        """Which pole of those found: the line is checked to stop there, and the stop is added."""
        known = self._line_and_key()
        if known is None:
            return self.async_abort(reason="unknown")
        line, api_key = known
        if user_input is None:
            return self._pole_form(line)
        stop_id, stop_nr = user_input[CONF_POLE].split("/")
        outcome = await self._finish(line, api_key, int(stop_id), stop_nr)
        return outcome if not isinstance(outcome, str) else self._pole_form(line, {"base": outcome})

    def _pole_form(self, line: str, errors: dict[str, str] | None = None) -> SubentryFlowResult:
        """The second step: which of the poles found."""
        return self.async_show_form(
            step_id="pole",
            data_schema=_form({vol.Required(CONF_POLE): _select(pole_options(self._poles))}),
            errors=errors or {},
            description_placeholders={"line": line, "query": self._query},
        )

    async def _finish(self, line: str, api_key: str, stop_id: int, stop_nr: str) -> SubentryFlowResult | str:
        """Check the pole with the line's key (the line must stop there) and add it as a subentry: the result, or the key of the error to show."""
        if any((str(stop_id), stop_nr, line) in stop_keys(e) for e in self.hass.config_entries.async_entries(DOMAIN)):
            return self.async_abort(reason="already_configured")
        error, _ = await error_for(self.hass, {CONF_API_KEY: api_key, CONF_BUSSTOP_ID: stop_id, CONF_BUSSTOP_NR: stop_nr, CONF_LINE: line})
        if error is not None:
            return error
        if any((str(stop_id), stop_nr, line) in stop_keys(e) for e in self.hass.config_entries.async_entries(DOMAIN)):
            return self.async_abort(reason="already_configured")  # added by another flow while the City was asked
        return self.async_create_entry(
            title=f"{stop_id}/{stop_nr}",
            data={CONF_BUSSTOP_ID: stop_id, CONF_BUSSTOP_NR: stop_nr},
            unique_id=_stop_unique_id(stop_id, stop_nr),
        )

    def _manual_form(self, line: str, errors: dict[str, str] | None = None) -> SubentryFlowResult:
        """The form of the numbers: the stop ID and the pole typed."""
        schema = _form({vol.Required(CONF_BUSSTOP_ID): vol.Coerce(str), vol.Required(CONF_BUSSTOP_NR): str})
        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors or {}, description_placeholders={"line": line})

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """The form of the numbers: the stop ID and the pole, checked with the line's key."""
        known = self._line_and_key()
        if known is None:
            return self.async_abort(reason="unknown")
        line, api_key = known
        if user_input is None:
            return self._manual_form(line)
        stop_id, stop_nr = _stop_id_of(user_input[CONF_BUSSTOP_ID]), user_input[CONF_BUSSTOP_NR].strip()
        if stop_id is None:
            return self._manual_form(line, {"base": "invalid_stop_id"})
        outcome = await self._finish(line, api_key, stop_id, stop_nr)
        return outcome if not isinstance(outcome, str) else self._manual_form(line, {"base": outcome})
