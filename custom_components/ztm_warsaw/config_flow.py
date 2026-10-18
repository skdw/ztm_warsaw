import logging
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import ZTMApiError, ZTMAuthError, ZTMStopClient, key_kind, user_agent
from . import _entry_values
from .const import DOMAIN, CONF_API_KEY, CONF_BUSSTOP_ID, CONF_BUSSTOP_NR, CONF_LINE, CONF_DEPARTURES

_LOGGER = logging.getLogger(__name__)

class KeyWorks(ValueError):
    """The City accepted the key and answered, but not with something to show (the line is not in its list, an empty
    timetable). Setup refuses it like any other ValueError; a reauth only wants to know that the key works."""

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): str,
    vol.Required(CONF_BUSSTOP_ID): vol.Coerce(int),
    vol.Required(CONF_BUSSTOP_NR): str,
    vol.Required(CONF_LINE): str,
    vol.Required(CONF_DEPARTURES, default=1): vol.In({
        1: "Next departure",
        2: "Next two departures",
        3: "Next three departures"
    }),
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


class ZtmWarsawConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    VERSION = 1

    async def _error_for(self, user_input, *, check_stop_number=True):
        """The error key for this input, or None when it is valid. Logs what went wrong, never the key.
        ``self.key_works`` tells afterwards whether the error still proves that the City accepted the key."""
        self.key_works = False
        if check_stop_number and not re.fullmatch(r"\d{2}", user_input[CONF_BUSSTOP_NR], re.ASCII):
            return "invalid_stop_number"
        unexpected = None
        try:
            await validate_input(
                self.hass,
                user_input[CONF_API_KEY],
                user_input[CONF_BUSSTOP_ID],
                user_input[CONF_BUSSTOP_NR],
                user_input[CONF_LINE],
            )
            return None
        except ValueError as err:
            key = str(err)
            self.key_works = isinstance(err, KeyWorks)
        except Exception as err:
            # Only the class: the text or the traceback of an unexpected error can carry the URL, and the key.
            unexpected, key = type(err).__name__, "unknown"
        if unexpected:
            _LOGGER.error("Unexpected error during validation: %s", unexpected)
        else:
            _LOGGER.warning("Validation error: %s", key)
        return key

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            user_input = {k: v.strip() if isinstance(v, str) else v for k, v in user_input.items()}
            error = await self._error_for(user_input)
            if error is None:
                title = f"Line {user_input[CONF_LINE]} from {user_input[CONF_BUSSTOP_ID]}/{user_input[CONF_BUSSTOP_NR]}"
                return self.async_create_entry(title=title, data=user_input)
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
        values = _entry_values(entry) if entry else None
        if entry is None or values is None:
            return self.async_abort(reason="unknown")
        _, stop_id, stop_nr, line = values
        errors = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            error = await self._error_for(
                {CONF_API_KEY: key, CONF_BUSSTOP_ID: stop_id, CONF_BUSSTOP_NR: stop_nr, CONF_LINE: line},
                check_stop_number=False,  # an old entry keeps the number it has; only the key is asked for here
            )
            if error is None or self.key_works:  # that the line does not run today is not the key's fault
                loaded = entry.state is config_entries.ConfigEntryState.LOADED  # read first: the update may start a reload
                changed = self.hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_API_KEY: key})
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


class ZtmWarsawOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        schema = vol.Schema({
            vol.Optional(
                CONF_DEPARTURES,
                default=self._config_entry.options.get(
                    CONF_DEPARTURES,
                    self._config_entry.data.get(CONF_DEPARTURES, 1),
                )
            ): vol.In({
                1: "Next departure",
                2: "Next two departures",
                3: "Next three departures",
            })
        })

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={},
        ) 