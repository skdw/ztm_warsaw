import logging
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import ZTMApiError, ZTMAuthError, ZTMStopClient, key_kind, user_agent
from .const import DOMAIN, CONF_API_KEY, CONF_BUSSTOP_ID, CONF_BUSSTOP_NR, CONF_LINE, CONF_DEPARTURES

_LOGGER = logging.getLogger(__name__)

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


async def validate_input(hass, api_key, stop_id, stop_nr, line):
    """Check the input against the City of Warsaw API with the client the sensor uses. Raises ValueError(<error key>).

    A key that is neither a UUID (old API) nor a token (new API) is refused before anything is sent. The new API
    answers every rejected request with the same HTTP 500, so when its request for the lines fails, a request with
    no parameters to get wrong tells a bad token from a bad stop.
    """
    if key_kind(api_key) is None:
        raise ValueError("invalid_api_key")
    client = ZTMStopClient(
        async_get_clientsession(hass), api_key, str(stop_id), stop_nr, line, user_agent=await user_agent(hass)
    )
    try:
        lines = await client.get_lines()
        if lines is None:
            if not client.uses_token:
                raise ValueError("api_connection_error")
            raise ValueError("line_not_found" if await client.token_is_accepted() else "invalid_token_or_unavailable")
        if line not in lines:
            raise ValueError("line_not_found")
        data = await client.get(fetch_stop_name=False)
    except ZTMAuthError:
        raise ValueError("invalid_api_key") from None
    except ZTMApiError:
        raise ValueError("line_not_found") from None
    if data is None:
        raise ValueError("api_connection_error")
    if not data.departures:
        raise ValueError("no_departures")


class ZtmWarsawConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            user_input = {k: v.strip() if isinstance(v, str) else v for k, v in user_input.items()}
            if not re.fullmatch(r"[0-9]{2}", user_input[CONF_BUSSTOP_NR]):
                errors["base"] = "invalid_stop_number"
            else:
                try:
                    await validate_input(
                        self.hass,
                        user_input[CONF_API_KEY],
                        user_input[CONF_BUSSTOP_ID],
                        user_input[CONF_BUSSTOP_NR],
                        user_input[CONF_LINE],
                    )
                except ValueError as err:
                    errors["base"] = str(err)
                    _LOGGER.warning("Validation error: %s", errors["base"])
                except Exception as err:
                    # Only the class: the text or the traceback of an unexpected error can carry the URL, and the key.
                    _LOGGER.error("Unexpected error during validation: %s", type(err).__name__)
                    errors["base"] = "unknown"
                else:
                    title = f"Line {user_input[CONF_LINE]} from {user_input[CONF_BUSSTOP_ID]}/{user_input[CONF_BUSSTOP_NR]}"
                    return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors
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