import asyncio
import logging
from typing import Optional
import time
import json

import aiohttp
import async_timeout

from .models import ZTMDepartureData, ZTMDepartureDataReading

_LOGGER = logging.getLogger(__name__)

def _sanitize_params(params: dict) -> dict:
    """Return a shallow copy with API key masked for safe logging."""
    if not isinstance(params, dict):
        return {}
    red = dict(params)
    if "apikey" in red:
        red["apikey"] = "****"
    return red

def _ctx(params: dict) -> str:
    """Return a short, non-sensitive context string for logs.
    Only includes busstopId, busstopNr, and line. Sensitive fields are omitted."""
    if not isinstance(params, dict):
        return ""
    # Only include explicitly non-sensitive fields
    stop_id = params.get("busstopId")
    stop_nr = params.get("busstopNr")
    line = params.get("line")
    parts = []
    if stop_id is not None:
        parts.append(f"stop_id={stop_id}")
    if stop_nr is not None:
        parts.append(f"stop_nr={stop_nr}")
    if line is not None:
        parts.append(f"line={line}")
    # Never include apikey or other sensitive fields
    return ", ".join(parts)

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
        stop_info_ttl: int | None = None,
    ):
        # Endpoint to fetch the timetable for a given stop, line, and post number
        self._endpoint = "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
        self._data_id = "e923fa0e-d96c-43f9-ae6e-60518c9f3238"
        # Endpoint to fetch metadata for stops (name, location, etc.)
        self._stop_info_endpoint = "https://api.um.warszawa.pl/api/action/dbstore_get/"
        self._stop_info_data_id = "ab75c33d-3a26-4342-b36a-6e5fef0a3ac3"
        self._timeout = timeout or 20
        self._session = session
        self._stop_info_ttl = stop_info_ttl  # seconds; None means never refresh automatically
        self._stop_info_last_fetch: float | None = None
        # Retry policy for transient errors
        self._max_retries = 1  # number of retries on timeout/5xx
        self._retry_backoff = 1.5  # seconds for first backoff; multiplied per attempt

        self._params = {
            "id": self._data_id,
            "apikey": api_key,
            "busstopId": stop_id,
            "busstopNr": stop_number,
            "line": line,
        }
        self._stop_name = None
        self._stop_info_cache = {}

    async def _get_with_retry(self, url: str, params: dict, *, expect_json: bool = True):
        """Perform GET with timeout and a small retry on timeout/5xx.
        # English-only comments for OSS clarity
        """
        attempt = 0
        last_exc = None
        while True:
            try:
                async with async_timeout.timeout(self._timeout):
                    async with self._session.get(url, params=params) as resp:
                        text = await resp.text()
                        # Retry on 5xx
                        if 500 <= resp.status <= 599 and attempt < self._max_retries:
                            _LOGGER.warning(
                                "HTTP %s from %s; retrying (%s/%s)",
                                resp.status, url, attempt + 1, self._max_retries
                            )
                            attempt += 1
                            await asyncio.sleep(self._retry_backoff * attempt)
                            continue
                        if resp.status != 200:
                            _LOGGER.error(
                                "HTTP %s from %s (%s)",
                                resp.status, url, _ctx(params)
                            )
                            return None if not expect_json else {}
                        if expect_json:
                            try:
                                return json.loads(text)
                            except Exception:
                                _LOGGER.error(
                                    "Invalid JSON from %s (%s)",
                                    url, _ctx(params)
                                )
                                return {}
                        return text
            except asyncio.TimeoutError as e:
                last_exc = e
                if attempt < self._max_retries:
                    _LOGGER.warning(
                        "Timeout talking to %s; retrying (%s/%s)",
                        url, attempt + 1, self._max_retries
                    )
                    attempt += 1
                    await asyncio.sleep(self._retry_backoff * attempt)
                    continue
                _LOGGER.error(
                    "Timeout after %ss for %s (%s)",
                    self._timeout, url, _ctx({
                        "busstopId": self._params.get("busstopId"),
                        "busstopNr": self._params.get("busstopNr"),
                        "line": self._params.get("line"),
                    })
                )
                return None if not expect_json else {}
            except aiohttp.ClientError as e:
                _LOGGER.error(
                    "Network error for %s: %s (%s)",
                    url, e, _ctx(params)
                )
                return None if not expect_json else {}

    async def get_stop_name(self) -> Optional[dict]:
        """Fetch stop metadata (name, etc.) with caching and strict validation.
        This is called by sensors frequently, but the stop name does not change often.
        We therefore cache it and only re-fetch at most once per `self._stop_info_ttl`.
        """
        # If we already have a cached value and TTL not expired, return it.
        now = time.time()
        if self._stop_name is not None and (
            self._stop_info_ttl is None or (
                self._stop_info_last_fetch is not None and now - self._stop_info_last_fetch < self._stop_info_ttl
            )
        ):
            return self._stop_name

        cache_key = (self._params["busstopId"], self._params["busstopNr"])
        if cache_key in self._stop_info_cache:
            # Update in-memory main cache too, mark timestamp and return
            self._stop_name = self._stop_info_cache[cache_key]
            self._stop_info_last_fetch = now
            return self._stop_name

        params = {
            "id": self._stop_info_data_id,
            "apikey": self._params["apikey"],
        }

        json_response = await self._get_with_retry(self._stop_info_endpoint, params)
        if not isinstance(json_response, dict):
            return self._stop_name

        # Validate response shape strictly
        result = json_response.get("result")
        if result is None:
            _LOGGER.warning(
                "Stop info empty (result=None) for stop_id=%s stop_nr=%s",
                self._params.get("busstopId"),
                self._params.get("busstopNr"),
            )
            return self._stop_name

        if isinstance(result, str):
            # ZTM returns "false" on errors; log error field if present
            _LOGGER.warning(
                "Stop info returned string result=%r, error=%r for stop_id=%s stop_nr=%s",
                result,
                json_response.get("error"),
                self._params.get("busstopId"),
                self._params.get("busstopNr"),
            )
            return self._stop_name

        if not isinstance(result, list):
            _LOGGER.error(
                "Unexpected 'result' type from stop info: %s", type(result).__name__
            )
            return self._stop_name

        fallback = None
        stop_id_str = str(self._params["busstopId"])  # normalize for comparison
        stop_nr_str = str(self._params["busstopNr"])  # normalize for comparison

        for entry in result:
            if not isinstance(entry, dict):
                continue
            values = entry.get("values") or []
            if not isinstance(values, list):
                continue
            kv = {
                v.get("key"): v.get("value")
                for v in values
                if isinstance(v, dict) and "key" in v and "value" in v
            }
            if str(kv.get("zespol")) == stop_id_str:
                if str(kv.get("slupek")) == stop_nr_str:
                    # Exact match for stop & post
                    self._stop_name = {k: v for k, v in kv.items() if k not in ("zespol", "slupek")}
                    self._stop_info_cache[cache_key] = self._stop_name
                    self._stop_info_last_fetch = now
                    return self._stop_name
                if fallback is None:
                    fallback = {k: v for k, v in kv.items() if k not in ("zespol", "slupek")}

        if fallback is not None:
            self._stop_name = fallback
            self._stop_info_cache[cache_key] = self._stop_name
            self._stop_info_last_fetch = now
            return self._stop_name

        _LOGGER.warning(
            "Stop name not found in stop info for stop_id=%s stop_nr=%s",
            self._params.get("busstopId"),
            self._params.get("busstopNr"),
        )
        return self._stop_name

    async def get(self) -> Optional[ZTMDepartureData]:
        try:
            # Ensure stop info is cached; this will be a no-op after the first successful fetch
            await self.get_stop_name()

            json_response = await self._get_with_retry(self._endpoint, self._params)
            if not isinstance(json_response, dict):
                await self.get_stop_name()
                if self._stop_name and "nazwa_zespolu" in self._stop_name:
                    self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
                return ZTMDepartureData(departures=[], stop_info=self._stop_name)

            result = json_response.get("result")
            if not isinstance(result, list):
                if result is None:
                    await self.get_stop_name()
                    if self._stop_name and "nazwa_zespolu" in self._stop_name:
                        self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
                    return ZTMDepartureData(departures=[], stop_info=self._stop_name)
                if isinstance(result, str):
                    await self.get_stop_name()
                    if self._stop_name and "nazwa_zespolu" in self._stop_name:
                        self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
                    return ZTMDepartureData(departures=[], stop_info=self._stop_name)
                await self.get_stop_name()
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
            await self.get_stop_name()
            if self._stop_name and "nazwa_zespolu" in self._stop_name:
                self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
            return ZTMDepartureData(departures=_departures, stop_info=self._stop_name)

        except Exception as e:
            _LOGGER.error("Unexpected error in timetable fetch: %s", e, exc_info=True)
        await self.get_stop_name()
        if self._stop_name and "nazwa_zespolu" in self._stop_name:
            self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
        return ZTMDepartureData(departures=[], stop_info=self._stop_name)