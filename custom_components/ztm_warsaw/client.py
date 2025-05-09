import asyncio
import logging
from datetime import datetime
from typing import Optional

import aiohttp
import async_timeout

from .models import ZTMDepartureData, ZTMDepartureDataReading

_LOGGER = logging.getLogger(__name__)


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
        self._endpoint = "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
        self._data_id = "e923fa0e-d96c-43f9-ae6e-60518c9f3238"
        self._timeout = timeout or 10
        self._session = session

        self._params = {
            "id": self._data_id,
            "apikey": api_key,
            "busstopId": stop_id,
            "busstopNr": stop_number,
            "line": line,
        }

    async def get(self) -> Optional[ZTMDepartureData]:
        try:
            async with async_timeout.timeout(self._timeout):
                async with self._session.get(self._endpoint, params=self._params) as response:
                    if response.status != 200:
                        _LOGGER.error("Error fetching data: %s", await response.text())
                        return ZTMDepartureData(departures=[])

                    json_response = await response.json()

                    result = json_response.get("result")
                    if not isinstance(result, list):
                        if result is None:
                            return ZTMDepartureData(departures=[])
                        if isinstance(result, str):
                            return ZTMDepartureData(departures=[])
                        return ZTMDepartureData(departures=[])

                    _departures = []

                    for reading in result:
                        if not isinstance(reading, list):
                            _LOGGER.warning("Unexpected entry format in result: %s", reading)
                            continue

                        _data = {entry["key"]: entry["value"] for entry in reading if isinstance(entry, dict) and "key" in entry and "value" in entry}
                        try:
                            parsed = ZTMDepartureDataReading.from_dict(_data)
                            # Pobierz wszystkie odjazdy, bez filtrowania czasowego
                            if parsed.dt:
                                _departures.append(parsed)
                        except Exception:
                            _LOGGER.debug("Invalid reading skipped: %s", _data)

                    _departures.sort(key=lambda x: x.time_to_depart)
                    _LOGGER.debug("Loaded %d departures from API", len(_departures))
                    return ZTMDepartureData(departures=_departures)

        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            _LOGGER.error("Connection error: %s", e)
        except ValueError:
            _LOGGER.error("Non-JSON data received from API")
        return ZTMDepartureData(departures=[])
