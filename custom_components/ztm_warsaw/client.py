import asyncio
import logging
from datetime import datetime
from typing import Optional

import aiohttp
import async_timeout

from .models import ZTMDepartureData, ZTMDepartureDataReading

_LOGGER = logging.getLogger(__name__)

# Client for interacting with the Warsaw ZTM public transport API
class ZTMStopClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        stop_id: str,
        stop_number: str,
        line: str,
        timeout: int | None = None,
    ):
        # Endpoint to fetch the timetable for a given stop, line, and post number
        self._endpoint = "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
        self._data_id = "e923fa0e-d96c-43f9-ae6e-60518c9f3238"
        # Endpoint to fetch metadata for stops (name, location, etc.)
        self._stop_info_endpoint = "https://api.um.warszawa.pl/api/action/dbstore_get/"
        self._stop_info_data_id = "ab75c33d-3a26-4342-b36a-6e5fef0a3ac3"
        self._timeout = timeout or 10
        self._session = session

        self._params = {
            "id": self._data_id,
            "apikey": api_key,
            "busstopId": stop_id,
            "busstopNr": stop_number,
            "line": line,
        }
        self._stop_name = None
        self._stop_info_cache = {}

    async def get_stop_name(self) -> Optional[dict]:
        cache_key = (self._params["busstopId"], self._params["busstopNr"])
        if cache_key in self._stop_info_cache:
            return self._stop_info_cache[cache_key]
        try:
            # Prepare request parameters to fetch stop metadata
            params = {
                "id": self._stop_info_data_id,
                "apikey": self._params["apikey"],
            }
            async with async_timeout.timeout(self._timeout):
                async with self._session.get(self._stop_info_endpoint, params=params) as response:
                    if response.status != 200:
                        _LOGGER.warning("Failed to get stop info: %s", await response.text())
                        return None
                    json_response = await response.json()
                    fallback = None
                    # Search for the stop with matching stop ID and post number
                    for entry in json_response.get("result", []):
                        values = {x["key"]: x["value"] for x in entry.get("values", [])}
                        # Match stop ID ("zespol") and optionally match post number ("slupek")
                        if values.get("zespol") == self._params["busstopId"]:
                            if values.get("slupek") == self._params["busstopNr"]:
                                result = {k: v for k, v in values.items() if k not in ["zespol", "slupek"]}
                                self._stop_info_cache[cache_key] = result
                                return result
                            # use as fallback if exact post is not found
                            if fallback is None:
                                fallback = {k: v for k, v in values.items() if k not in ["zespol", "slupek"]}
                    if fallback is not None:
                        self._stop_info_cache[cache_key] = fallback
                        return fallback
        except Exception as e:
            _LOGGER.warning("Failed to fetch stop name: %s", e, exc_info=True)
        return None

    async def get(self) -> Optional[ZTMDepartureData]:
        try:
            async with async_timeout.timeout(self._timeout):
                async with self._session.get(self._endpoint, params=self._params) as response:
                    if response.status != 200:
                        _LOGGER.error("Error fetching data: %s", await response.text())
                        self._stop_name = await self.get_stop_name()
                        if self._stop_name and "nazwa_zespolu" in self._stop_name:
                            self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
                        return ZTMDepartureData(departures=[], stop_info=self._stop_name)

                    json_response = await response.json()

                    result = json_response.get("result")
                    if not isinstance(result, list):
                        if result is None:
                            self._stop_name = await self.get_stop_name()
                            if self._stop_name and "nazwa_zespolu" in self._stop_name:
                                self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
                            return ZTMDepartureData(departures=[], stop_info=self._stop_name)
                        if isinstance(result, str):
                            self._stop_name = await self.get_stop_name()
                            if self._stop_name and "nazwa_zespolu" in self._stop_name:
                                self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
                            return ZTMDepartureData(departures=[], stop_info=self._stop_name)
                        self._stop_name = await self.get_stop_name()
                        if self._stop_name and "nazwa_zespolu" in self._stop_name:
                            self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
                        return ZTMDepartureData(departures=[], stop_info=self._stop_name)

                    # Parse each departure from the API response
                    _departures = []

                    for reading in result:
                        if not isinstance(reading, list):
                            _LOGGER.warning("Unexpected entry format in result: %s", reading)
                            continue

                        _data = {entry["key"]: entry["value"] for entry in reading if isinstance(entry, dict) and "key" in entry and "value" in entry}
                        try:
                            parsed = ZTMDepartureDataReading.from_dict(_data)
                            # Load all departures, without time filtering
                            if parsed.dt:
                                _departures.append(parsed)
                        except Exception:
                            _LOGGER.debug("Invalid reading skipped: %s", _data)

                    # Sort departures by their scheduled time
                    _departures.sort(key=lambda x: x.time_to_depart)
                    _LOGGER.debug("Loaded %d departures from API", len(_departures))
                    # Fetch stop metadata (name, location, etc.) after loading departures
                    self._stop_name = await self.get_stop_name()
                    if self._stop_name and "nazwa_zespolu" in self._stop_name:
                        self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
                    return ZTMDepartureData(departures=_departures, stop_info=self._stop_name)

        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            _LOGGER.error("Connection error: %s", e, exc_info=True)
        except ValueError:
            _LOGGER.error("Non-JSON data received from API", exc_info=True)
        self._stop_name = await self.get_stop_name()
        if self._stop_name and "nazwa_zespolu" in self._stop_name:
            self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
        return ZTMDepartureData(departures=[], stop_info=self._stop_name)