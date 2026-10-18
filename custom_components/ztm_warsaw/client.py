# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Optional
import time
import json
import re

import aiohttp

from homeassistant.loader import async_get_integration

from .const import DOMAIN, REPOSITORY_URL
from .models import ZTMDepartureData, ZTMDepartureDataReading

_LOGGER = logging.getLogger(__name__)

_RETRY = object()  # what _attempt returns for an answer worth another try
_NEW_API = "https://dane.um.warszawa.pl/api/action/"
_NEW_TIMETABLE = "get_ztm_odjazdy_linii_z_przystanku"
_NEW_STOPS = "get_ztm_przystanki_komunikacji_miejskiej"
_NEW_LINES = "get_ztm_lista_linii_na_przystanku"
_LEGACY_LINES_ID = "88cd555f-6f31-43ca-9de4-66c479ad5942"
_TOKEN = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")  # a JWT: three dot-separated segments
# A key shaped like this belongs to the legacy host (GET, key in the query); any other key is a token for the new
# host (POST, raw Authorization header). A key is only ever sent to the host that can accept it.
_LEGACY_KEY = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.IGNORECASE)

def key_kind(key: str) -> str | None:
    """``legacy`` for a key of the old API (a UUID), ``token`` for one of the new API (a JWT), else None."""
    key = key.strip()
    if _LEGACY_KEY.match(key):
        return "legacy"
    return "token" if _TOKEN.match(key) else None


async def user_agent(hass) -> str:
    """Says which software asks (name, version, repository), never who."""
    version = (await async_get_integration(hass, DOMAIN)).version
    return f"{DOMAIN}/{version} (Home Assistant custom integration; +{REPOSITORY_URL})"


# What the legacy API puts in ``result`` when it does not know the stop pole / line (measured).
_PARAM_ERROR_TEXT = "Błędna metoda lub parametry wywołania"


class ZTMApiError(Exception):
    """The API answered, but not with a timetable. The message is fixed text: it never carries the key."""


class ZTMAuthError(ZTMApiError):
    """The API refused the API key."""


def _checked_result(json_response) -> list:
    """The readings of a timetable answer, or a ZTMApiError for an answer that is not a timetable.

    ``result`` null means the line exists but does not run today: a real, empty timetable ("No service").
    """
    if not isinstance(json_response, dict) or "result" not in json_response:
        raise ZTMApiError("The City of Warsaw API sent an answer in an unknown format")
    result = json_response["result"]
    if result is None:
        return []
    if result == "false" and "apikey" in str(json_response.get("error", "")).lower():
        raise ZTMAuthError("The City of Warsaw API rejected the API key")
    if result == _PARAM_ERROR_TEXT:
        raise ZTMApiError("The City of Warsaw API does not know this stop, pole and line; check them")
    if not isinstance(result, list):
        raise ZTMApiError("The City of Warsaw API sent an answer in an unknown format")
    return result


def _sanitize_params(params: dict) -> dict:
    """Return a shallow copy with API key masked for safe logging."""
    if not isinstance(params, dict):
        return {}
    red = dict(params)
    if "apikey" in red:
        red["apikey"] = "****"
    return red

def _ctx(params: dict | None = None, *, stop_id: str | None = None, stop_nr: str | None = None, line: str | None = None) -> str:
    """Return a short, non-sensitive context string for logs.
    Accepts a full params dict (from which only whitelisted keys are read), or explicit kwargs.
    Values are sanitized to avoid leaking sensitive/free-form data.
    """
    # If a dict is passed, extract only whitelisted keys
    if isinstance(params, dict):
        stop_id = params.get("busstopId") if stop_id is None else stop_id
        stop_nr = params.get("busstopNr") if stop_nr is None else stop_nr
        line = params.get("line") if line is None else line

    def _safe(v: str | None) -> str:
        if v is None:
            return ""
        # Keep only alphanumerics and a few safe characters; mask the rest
        s = str(v)
        s = re.sub(r"[^A-Za-z0-9_\-]", "*", s)
        return s

    parts: list[str] = []
    if stop_id is not None:
        parts.append(f"stop_id={_safe(stop_id)}")
    if stop_nr is not None:
        parts.append(f"stop_nr={_safe(stop_nr)}")
    if line is not None:
        parts.append(f"line={_safe(line)}")
    return ", ".join(parts)


# Helper to build safe context string from a params dict
def _ctxp(params: dict | None) -> str:
    """Build safe context string from a params dict.
    Values are first sanitized via `_sanitize_params`, then only whitelisted keys are used.
    """
    sp = _sanitize_params(params or {})
    return _ctx(
        stop_id=sp.get("busstopId"),
        stop_nr=sp.get("busstopNr"),
        line=sp.get("line"),
    )

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
        user_agent: str | None = None,
    ):
        api_key = api_key.strip()
        self._user_agent = user_agent
        self._legacy = bool(_LEGACY_KEY.match(api_key))
        # Endpoint to fetch the timetable for a given stop, line, and post number
        self._endpoint = "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
        # Endpoint to fetch metadata for stops (name, location, etc.)
        self._stop_info_endpoint = "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
        self._stop_info_data_id = "ab75c33d-3a26-4342-b36a-6e5fef0a3ac3"
        self._data_id = "e923fa0e-d96c-43f9-ae6e-60518c9f3238"  # timetable endpoint id (dbtimetable_get)
        self._timeout = timeout or 20
        self._session = session
        self._stop_info_ttl = stop_info_ttl  # seconds; None means never refresh automatically
        self._stop_info_last_fetch: float | None = None
        # Stop-info retry/backoff state (never refetch after first success)
        self._stop_info_attempts: int = 0               # how many failed attempts so far
        self._stop_info_next_retry: float | None = None # UTC timestamp when we may retry
        self._stop_info_permanent_missing: bool = False # give up after N attempts (until manual reload)
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
        self._stop_name: dict | None = None
        self._stop_info_cache: dict[tuple[str, str], dict] = {}

    async def _call(self, kind: str):
        """One request for the ``timetable``, the ``lines`` at the stop or the ``stops`` of this client, on the host
        that matches its key. The answer has the legacy shape ``{"result": ...}`` whichever host sent it.
        """
        params = self._params
        if self._legacy:
            if kind == "stops":
                params = {"id": self._stop_info_data_id, "apikey": params["apikey"]}
            elif kind == "lines":
                params = {**{k: params[k] for k in ("apikey", "busstopId", "busstopNr")}, "id": _LEGACY_LINES_ID}
            return await self._get_with_retry(self._endpoint, params)
        keys = {"timetable": ("busstopId", "busstopNr", "line"), "lines": ("busstopId", "busstopNr"), "stops": ()}[kind]
        action = {"timetable": _NEW_TIMETABLE, "lines": _NEW_LINES, "stops": _NEW_STOPS}[kind]
        return await self._get_with_retry(
            _NEW_API + action, None, method="POST", json_body={k: str(params[k]) for k in keys} if keys else None,
            headers={"Authorization": params["apikey"]}, wrap=True,
        )

    @property
    def uses_token(self) -> bool:
        return not self._legacy

    async def get_lines(self) -> list[str] | None:
        """The lines that stop at this pole today; None when the request failed. Raises ZTMApiError like get()."""
        answer = await self._call("lines")
        if answer is None:
            return None
        rows = _checked_result(answer)
        return [v["value"] for row in rows if isinstance(row, dict)
                for v in row.get("values") or [] if isinstance(v, dict) and v.get("key") == "linia"]

    async def token_is_accepted(self) -> bool:
        """Whether the new API answers a request that has no parameters to get wrong. It answers every rejected
        request alike (HTTP 500), so this is the only way to tell a bad token from a bad stop."""
        return await self._call("stops") is not None

    async def _get_with_retry(self, url: str, params: dict | None, *, expect_json: bool = True,
                              method: str = "GET", json_body: dict | None = None,
                              headers: dict | None = None, wrap: bool = False):
        """Send the request with a timeout and a small retry on timeout, network error and 5xx.

        Redirects are never followed: the request carries the key, and a 3xx is an error. ``wrap`` puts a bare
        JSON answer into ``{"result": ...}``. Returns the answer, or None when the request finally failed.
        # English-only comments for OSS clarity
        """
        attempt = 0
        while True:
            reason = None
            try:
                result = await self._attempt(url, params, expect_json, method, json_body, headers, wrap, attempt)
            except asyncio.TimeoutError:
                reason = f"timeout after {self._timeout}s"
            except aiohttp.ClientError as err:
                # The text of a network error can carry the URL, and so the key: only its class is logged.
                reason = f"network error ({type(err).__name__})"
            else:
                if result is not _RETRY:
                    return result
            if reason is not None:
                if attempt >= self._max_retries:
                    _LOGGER.error("Request to %s failed: %s", url, reason)
                    return None
                _LOGGER.warning("Request to %s failed: %s; retrying (%s/%s)", url, reason, attempt + 1, self._max_retries)
            attempt += 1
            await asyncio.sleep(self._retry_backoff * attempt)

    async def _attempt(self, url, params, expect_json, method, json_body, headers, wrap, attempt):
        """One request. The answer, None for a failure that is final, or _RETRY for a 5xx worth another try."""
        if self._user_agent:  # says which software asks (name, version, repository), never who
            headers = {**(headers or {}), "User-Agent": self._user_agent}
        async with (
            asyncio.timeout(self._timeout),
            self._session.request(
                method, url, params=params, json=json_body, headers=headers, allow_redirects=False
            ) as resp,
        ):
            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.content.iter_chunked(65536):
                total += len(chunk)
                if total > 2_000_000:
                    _LOGGER.error("Response too large (>2 MB) from %s; skipping", url)
                    return None
                chunks.append(chunk)
            text = b"".join(chunks).decode(resp.charset or "utf-8", errors="replace")
            if 500 <= resp.status <= 599 and attempt < self._max_retries:
                _LOGGER.warning("HTTP %s from %s; retrying (%s/%s)", resp.status, url, attempt + 1, self._max_retries)
                return _RETRY
            if resp.status != 200:
                _LOGGER.error("HTTP %s from %s", resp.status, url)
                return None
            if not expect_json:
                return text
            try:
                value = json.loads(text)
            except ValueError:
                _LOGGER.error("Invalid JSON from %s", url)
                return None
            return {"result": value} if wrap else value

    async def get_stop_name(self) -> Optional[dict]:
        """Fetch stop metadata (name, etc.) with caching and strict validation.
        This is called by sensors frequently, but the stop name does not change often.
        We therefore cache it and only re-fetch at most once per `self._stop_info_ttl`.
        """
        # If we already have a cached value, never refetch automatically
        if self._stop_name is not None:
            return self._stop_name

        # Respect permanent-missing flag to avoid log spam
        if getattr(self, "_stop_info_permanent_missing", False):
            _LOGGER.debug(
                "Stop-info permanently marked missing for stop_id=%s stop_nr=%s; skip fetch",
                self._params.get("busstopId"),
                self._params.get("busstopNr"),
            )
            return None

        # Respect backoff window after previous failures
        from homeassistant.util import dt as dt_util
        now = time.time()
        now_ts = dt_util.utcnow().timestamp()
        if getattr(self, "_stop_info_next_retry", None) and now_ts < self._stop_info_next_retry:
            _LOGGER.debug(
                "Stop-info fetch skipped until %s (backoff) for stop_id=%s stop_nr=%s",
                dt_util.utc_from_timestamp(self._stop_info_next_retry),
                self._params.get("busstopId"),
                self._params.get("busstopNr"),
            )
            return None

        cache_key = (self._params["busstopId"], self._params["busstopNr"])
        if cache_key in self._stop_info_cache:
            # Update in-memory main cache too, mark timestamp and return
            self._stop_name = self._stop_info_cache[cache_key]
            self._stop_info_last_fetch = now
            return self._stop_name

        json_response = await self._call("stops")
        if not isinstance(json_response, dict):
            from homeassistant.util import dt as dt_util
            # Increment failed attempts and schedule next retry (capped at 3 attempts)
            self._stop_info_attempts = int(getattr(self, "_stop_info_attempts", 0)) + 1
            if self._stop_info_attempts >= 3:
                self._stop_info_permanent_missing = True
                self._stop_info_next_retry = None
                _LOGGER.info(
                    "Stop-info not available for stop_id=%s stop_nr=%s after %d attempts; suppressing further retries",
                    self._params.get("busstopId"),
                    self._params.get("busstopNr"),
                    self._stop_info_attempts,
                )
            else:
                backoffs = [2 * 3600, 6 * 3600]
                delay = backoffs[min(self._stop_info_attempts - 1, len(backoffs) - 1)]
                self._stop_info_next_retry = dt_util.utcnow().timestamp() + delay
                _LOGGER.debug(
                    "Stop-info attempt %d failed; next retry in %d seconds for stop_id=%s stop_nr=%s",
                    self._stop_info_attempts,
                    delay,
                    self._params.get("busstopId"),
                    self._params.get("busstopNr"),
                )
            return None

        # Validate response shape strictly
        result = json_response.get("result")
        if result is None:
            from homeassistant.util import dt as dt_util
            _LOGGER.debug(
                "Stop info empty (result=None) for stop_id=%s stop_nr=%s",
                self._params.get("busstopId"),
                self._params.get("busstopNr"),
            )
            self._stop_info_attempts = int(getattr(self, "_stop_info_attempts", 0)) + 1
            if self._stop_info_attempts >= 3:
                self._stop_info_permanent_missing = True
                self._stop_info_next_retry = None
                _LOGGER.info(
                    "Stop-info not available for stop_id=%s stop_nr=%s after %d attempts; suppressing further retries",
                    self._params.get("busstopId"),
                    self._params.get("busstopNr"),
                    self._stop_info_attempts,
                )
            else:
                backoffs = [2 * 3600, 6 * 3600]
                delay = backoffs[min(self._stop_info_attempts - 1, len(backoffs) - 1)]
                self._stop_info_next_retry = dt_util.utcnow().timestamp() + delay
                _LOGGER.debug(
                    "Stop-info attempt %d failed; next retry in %d seconds for stop_id=%s stop_nr=%s",
                    self._stop_info_attempts,
                    delay,
                    self._params.get("busstopId"),
                    self._params.get("busstopNr"),
                )
            return None

        if isinstance(result, str):
            # ZTM sometimes returns a localized string message instead of a list (transient backend state).
            # Treat ANY string result as transient; retry once after a short backoff.
            await asyncio.sleep(0.8)
            retry_resp = await self._call("stops")
            if isinstance(retry_resp, dict):
                result = retry_resp.get("result")
                if isinstance(result, list):
                    json_response = retry_resp  # continue with normal parsing below
                else:
                    from homeassistant.util import dt as dt_util
                    _LOGGER.debug(
                        "Stop info string result persisted after retry: %r (stop_id=%s stop_nr=%s)",
                        result,
                        self._params.get("busstopId"),
                        self._params.get("busstopNr"),
                    )
                    self._stop_info_attempts = int(getattr(self, "_stop_info_attempts", 0)) + 1
                    if self._stop_info_attempts >= 3:
                        self._stop_info_permanent_missing = True
                        self._stop_info_next_retry = None
                        _LOGGER.info(
                            "Stop-info not available for stop_id=%s stop_nr=%s after %d attempts; suppressing further retries",
                            self._params.get("busstopId"),
                            self._params.get("busstopNr"),
                            self._stop_info_attempts,
                        )
                    else:
                        backoffs = [2 * 3600, 6 * 3600]
                        delay = backoffs[min(self._stop_info_attempts - 1, len(backoffs) - 1)]
                        self._stop_info_next_retry = dt_util.utcnow().timestamp() + delay
                        _LOGGER.debug(
                            "Stop-info attempt %d failed; next retry in %d seconds for stop_id=%s stop_nr=%s",
                            self._stop_info_attempts,
                            delay,
                            self._params.get("busstopId"),
                            self._params.get("busstopNr"),
                        )
                    return None
            else:
                return None

        if not isinstance(result, list):
            from homeassistant.util import dt as dt_util
            _LOGGER.error(
                "Unexpected 'result' type from stop info: %s", type(result).__name__
            )
            self._stop_info_attempts = int(getattr(self, "_stop_info_attempts", 0)) + 1
            if self._stop_info_attempts >= 3:
                self._stop_info_permanent_missing = True
                self._stop_info_next_retry = None
                _LOGGER.info(
                    "Stop-info not available for stop_id=%s stop_nr=%s after %d attempts; suppressing further retries",
                    self._params.get("busstopId"),
                    self._params.get("busstopNr"),
                    self._stop_info_attempts,
                )
            else:
                backoffs = [2 * 3600, 6 * 3600]
                delay = backoffs[min(self._stop_info_attempts - 1, len(backoffs) - 1)]
                self._stop_info_next_retry = dt_util.utcnow().timestamp() + delay
                _LOGGER.debug(
                    "Stop-info attempt %d failed; next retry in %d seconds for stop_id=%s stop_nr=%s",
                    self._stop_info_attempts,
                    delay,
                    self._params.get("busstopId"),
                    self._params.get("busstopNr"),
                )
            return None

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
                    # Add a stable alias key for sensors/UX
                    if "nazwa_zespolu" in self._stop_name and "stop_name" not in self._stop_name:
                        self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
                    self._stop_info_cache[cache_key] = self._stop_name
                    self._stop_info_last_fetch = now
                    # Clear retry/backoff state on success
                    self._stop_info_attempts = 0
                    self._stop_info_next_retry = None
                    self._stop_info_permanent_missing = False
                    return self._stop_name
                if fallback is None:
                    fallback = {k: v for k, v in kv.items() if k not in ("zespol", "slupek")}

        if fallback is not None:
            self._stop_name = fallback
            if "nazwa_zespolu" in self._stop_name and "stop_name" not in self._stop_name:
                self._stop_name["stop_name"] = self._stop_name["nazwa_zespolu"]
            self._stop_info_cache[cache_key] = self._stop_name
            self._stop_info_last_fetch = now
            # Clear retry/backoff state on success (fallback)
            self._stop_info_attempts = 0
            self._stop_info_next_retry = None
            self._stop_info_permanent_missing = False
            return self._stop_name

        from homeassistant.util import dt as dt_util
        _LOGGER.warning(
            "Stop name not found in stop info for stop_id=%s stop_nr=%s",
            self._params.get("busstopId"),
            self._params.get("busstopNr"),
        )
        self._stop_info_attempts = int(getattr(self, "_stop_info_attempts", 0)) + 1
        if self._stop_info_attempts >= 3:
            self._stop_info_permanent_missing = True
            self._stop_info_next_retry = None
            _LOGGER.info(
                "Stop-info not available for stop_id=%s stop_nr=%s after %d attempts; suppressing further retries",
                self._params.get("busstopId"),
                self._params.get("busstopNr"),
                self._stop_info_attempts,
            )
        else:
            backoffs = [2 * 3600, 6 * 3600]
            delay = backoffs[min(self._stop_info_attempts - 1, len(backoffs) - 1)]
            self._stop_info_next_retry = dt_util.utcnow().timestamp() + delay
            _LOGGER.debug(
                "Stop-info attempt %d failed; next retry in %d seconds for stop_id=%s stop_nr=%s",
                self._stop_info_attempts,
                delay,
                self._params.get("busstopId"),
                self._params.get("busstopNr"),
            )
        return None

    async def get(self, *, fetch_stop_name: bool = True) -> Optional[ZTMDepartureData]:
        try:
            # Ensure stop name is fetched once on first use.
            # This will not spam the API: get_stop_name() respects backoff and permanent-missing.
            if fetch_stop_name and self._stop_name is None:
                await self.get_stop_name()
            json_response = await self._call("timetable")
            if json_response is None:
                _LOGGER.warning(
                    "Timetable fetch failed (no response) for %s",
                    _ctxp(self._params),
                )
                return None
            result = _checked_result(json_response)

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
            return ZTMDepartureData(departures=_departures, stop_info=self._stop_name)

        except ZTMApiError:
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error in timetable fetch: %s", e, exc_info=True)
        return None
