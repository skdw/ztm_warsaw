import logging
import voluptuous as vol
import aiohttp
from datetime import datetime
import re

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, CONF_API_KEY, CONF_BUSSTOP_ID, CONF_BUSSTOP_NR, CONF_LINE, CONF_DEPARTURES
import os, json


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

async def validate_input(api_key, stop_id, stop_nr, line):
    """Validate input against City of Warsaw API."""
    url = (
        "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
        "?id=e923fa0e-d96c-43f9-ae6e-60518c9f3238"
        f"&busstopId={stop_id}"
        f"&busstopNr={stop_nr}"
        f"&line={line}"
        f"&apikey={api_key}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    raise ValueError("api_http_error")

                data = await resp.json()
                if data.get("result") == "false":
                    raise ValueError("invalid_api_key")

                result = data.get("result")

                if result is None:
                    raise ValueError("no_departures")

                for item in result:
                    if not isinstance(item, list):
                        continue
                    czas = next((v["value"] for v in item if isinstance(v, dict) and v.get("key") == "czas"), None)
                    if czas and isinstance(czas, str) and re.match(r"^\d{2}:\d{2}:\d{2}$", czas):
                        return True

                raise ValueError("no_valid_times")

    except aiohttp.ClientError as e:
        _LOGGER.error("API connection error: %s", e)
        raise ValueError("api_connection_error")
    except ValueError:
        # Propagate known validation errors
        raise
    except Exception as e:
        _LOGGER.exception("Unexpected error: %s", e)
        raise ValueError("unknown")

class ZtmWarsawConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Validate stop number format
            if not user_input[CONF_BUSSTOP_NR].isdigit() or len(user_input[CONF_BUSSTOP_NR]) != 2:
                errors["base"] = "invalid_stop_number"
            else:
                try:
                    await validate_input(
                        user_input[CONF_API_KEY],
                        user_input[CONF_BUSSTOP_ID],
                        user_input[CONF_BUSSTOP_NR],
                        user_input[CONF_LINE],
                    )
                except ValueError as err:
                    key = str(err)
                    errors["base"] = key
                    _LOGGER.warning("Validation error: %s", key)
                except Exception as e:
                    _LOGGER.exception("Unexpected error: %s", e)
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
                default=self._config_entry.options.get(CONF_DEPARTURES, 1)
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
