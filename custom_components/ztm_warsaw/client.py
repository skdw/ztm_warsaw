# -*- coding: utf-8 -*-
"""The client of the City of Warsaw open-data API, for both hosts it runs on.

The old host (``api.um.warszawa.pl``: GET, a UUID key in the query, answers ``{"result": ...}``) and the new one
(``dane.um.warszawa.pl``: POST, a JWT token in the ``Authorization`` header, bare lists, every rejected request answered with the same 500) are told
apart by the shape of the key, and a key is only ever sent to the host that accepts it. ``ZTMStopClient`` asks for the
timetable, the lines and the name of one stop; ``StopCatalogue`` shares the 1.6 MB list of stops between entries.
Errors are raised as ``ZTMApiError`` or, for a rejected key, ``ZTMAuthError``; no message carries the key.
"""

import asyncio
import time
import logging
from typing import Any, Optional
import json
from datetime import date, datetime, timezone
import re
import unicodedata

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .const import DOMAIN, REPOSITORY_URL
from .models import ZTMDepartureData, ZTMDepartureDataReading, service_date_at

_LOGGER = logging.getLogger(__name__)

_RETRY = object()  # what _attempt returns for an answer worth another try
_NEW_API = "https://dane.um.warszawa.pl/api/action/"
_NEW_TIMETABLE = "get_ztm_odjazdy_linii_z_przystanku"
_NEW_STOPS = "get_ztm_przystanki_komunikacji_miejskiej"
_NEW_LINES = "get_ztm_lista_linii_na_przystanku"
_NEW_VEHICLES = "get_ztm_lokalizacja_pojazdow"
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


async def user_agent(hass: HomeAssistant) -> str:
    """Says which software asks (name, version, repository), never who."""
    version = (await async_get_integration(hass, DOMAIN)).version
    return f"{DOMAIN}/{version} (Home Assistant custom integration; +{REPOSITORY_URL})"


_STOP_INFO_BACKOFF = (2 * 3600, 6 * 3600)  # seconds to wait after the first and the second failed attempt
_STOP_INFO_MAX_ATTEMPTS = 3  # then the stop name is given up until the entry is reloaded


def _stop_fields(row: object) -> dict[str, Any]:
    """The ``{key: value}`` pairs of one record of the stops catalogue (``{"values": [{key, value}, ...]}``)."""
    values = row.get("values") if isinstance(row, dict) else None
    if not isinstance(values, list):
        return {}
    return {v["key"]: v["value"] for v in values if isinstance(v, dict) and "key" in v and "value" in v}


_MAX_BYTES = 2_000_000  # the largest timetable or list of lines accepted
_MAX_CATALOGUE_BYTES = 8_000_000  # the stops catalogue is bigger (1.6 MB of 2 MB in 2026) and grows


SEARCH_LIMIT = 30  # the poles a search lists at most; more asks the user to narrow it


def _fold(text: str) -> str:
    """Text for comparing names: lower case, without diacritics (the Polish "ł" has none to remove, so it is turned into "l")."""
    decomposed = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _matches(numbers: re.Match[str] | None, wanted: str, stop_id: str, stop_nr: str, name: str) -> bool:
    """Whether a pole is what the user typed: the stop ID (or the ID and the pole number) when it was typed as numbers, else a
    part of the stop's name."""
    if numbers:
        return stop_id == numbers.group(1) and (numbers.group(2) is None or stop_nr == numbers.group(2))
    return bool(wanted) and wanted in _fold(name)


def _index_stops(rows: list[Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """The catalogue as ``{stop: {pole: what it says about the pole, without the ids}}``, in the order of the records."""
    index: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        fields = _stop_fields(row)
        if "zespol" in fields:
            info = {k: v for k, v in fields.items() if k not in ("zespol", "slupek")}
            index.setdefault(str(fields["zespol"]), {}).setdefault(str(fields.get("slupek")), info)
    return index


class StopCatalogue:
    """The stops catalogue (1.6 MB) is the same for every entry: one download serves all of them, and a reload does
    not repeat it. Only a small index is kept (not the records), for ``ttl`` seconds; a failure is not retried for
    ``retry_after`` seconds, so a City that is down is asked once, not once per entry."""

    def __init__(self, ttl: float = 86400, retry_after: float = 60):
        """Set how long the index of the catalogue is kept (``ttl``) and how long a failed download is not repeated (``retry_after``)."""
        self._ttl = ttl
        self._retry_after = retry_after
        self._locks: dict[bool, asyncio.Lock] = {}  # one per kind of host: a slow host does not hold up the other
        self._index: dict[bool, tuple[float, dict[str, dict[str, dict[str, Any]]]]] = {}  # per host kind (token or not): (when, index)
        self._failed: dict[bool, float] = {}
        self.old_api_said = False  # the log has said once that the City's old API does not answer (shared by every stop of this instance)

    async def _load(self, client: "ZTMStopClient") -> tuple[bool | None, dict[str, dict[str, dict[str, Any]]] | None]:
        """``(readable, index)``: the index of the catalogue for the host of this client's key, downloaded when it is not kept
        (or is older than ``ttl``). ``readable`` is None when a failure is still fresh (not asked), False when the answer could not be read."""
        key = client.uses_token
        async with self._locks.setdefault(key, asyncio.Lock()):
            cached = self._index.get(key)
            if cached is None or time.monotonic() - cached[0] >= self._ttl:
                failed = self._failed.get(key)
                if failed is not None and time.monotonic() - failed < self._retry_after:
                    return None, None
                rows = await client._stop_info_rows()
                index = _index_stops(rows) if rows else {}
                if not index:  # nothing readable (an empty or foreign answer) is not worth keeping for a day
                    self._failed[key] = time.monotonic()  # from the end of the download, not from its start
                    return False, None
                self._failed.pop(key, None)
                cached = (time.monotonic(), index)
                if self._ttl > 0:
                    self._index[key] = cached
            return True, cached[1]

    async def find(self, client: "ZTMStopClient", stop_id: str, stop_nr: str) -> tuple[bool | None, dict[str, Any] | None]:
        """``(readable, info)``: whether the catalogue could be read (None: not asked, a failure is still fresh), and what
        it says about the pole (the first pole of the stop when this one is not listed; None when the stop is not there)."""
        readable, index = await self._load(client)
        if index is None:
            return readable, None
        poles = index.get(stop_id)
        if not poles:
            return True, None
        info = poles[stop_nr] if stop_nr in poles else next(iter(poles.values()))
        return True, dict(info)

    async def search(self, client: "ZTMStopClient", query: str, limit: int = SEARCH_LIMIT) -> tuple[bool | None, list[dict[str, Any]]]:
        """``(readable, poles)``: the poles whose stop name contains ``query`` (case, diacritics and the Polish "ł" do not matter),
        or whose stop ID, or stop ID and pole number ("7009" or "7009/01"), is what was typed. A pole is
        ``{"stop_id", "stop_nr", "name", "direction"}``, sorted by name, ID and number; at most ``limit + 1`` come back, so
        that the caller can tell "too many" from "all of them"."""
        readable, index = await self._load(client)
        if index is None:
            return readable, []
        wanted = _fold(query).strip()
        numbers = re.fullmatch(r"(\d{1,9})(?:/(\d{2}))?", query.strip())
        found: list[dict[str, Any]] = []
        for stop_id, poles in index.items():
            for stop_nr, info in poles.items():
                name = str(info.get("nazwa_zespolu") or "")
                if _matches(numbers, wanted, stop_id, stop_nr, name):
                    found.append({"stop_id": stop_id, "stop_nr": stop_nr, "name": name, "direction": str(info.get("kierunek") or "")})
        found.sort(key=lambda p: (_fold(p["name"]), p["stop_id"], p["stop_nr"]))
        return True, found[: limit + 1]


# What the legacy API puts in ``result`` when it does not know the stop pole / line (measured).
_PARAM_ERROR_TEXT = "Błędna metoda lub parametry wywołania"


class ZTMApiError(Exception):
    """The API answered, but not with a timetable. The message is fixed text: it never carries the key."""


class ZTMAuthError(ZTMApiError):
    """The API refused the API key."""


_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _by_moment(reading: ZTMDepartureDataReading) -> datetime:
    """The sort key of a reading: the moment it departs (a reading without one sorts first)."""
    return reading.dt or _EPOCH


def _checked_result(json_response: Any) -> list[Any]:
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


def _readings(result: list[Any], service_date: date) -> list[ZTMDepartureDataReading]:
    """The departures of a timetable answer that can be read (all of them, without time filtering); the others are skipped and logged."""
    departures: list[ZTMDepartureDataReading] = []
    for reading in result:
        if not isinstance(reading, list):
            _LOGGER.warning("Unexpected entry format in result: %s", reading)
            continue
        data = {entry["key"]: entry["value"] for entry in reading if isinstance(entry, dict) and "key" in entry and "value" in entry}
        try:
            parsed = ZTMDepartureDataReading.from_dict(data, service_date)
            if parsed.dt:
                departures.append(parsed)
        except Exception:
            _LOGGER.debug("Invalid reading skipped: %s", data)
    return departures


def _sanitize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with API key masked for safe logging."""
    if not isinstance(params, dict):
        return {}
    red = dict(params)
    if "apikey" in red:
        red["apikey"] = "****"
    return red

def _ctx(params: dict[str, Any] | None = None, *, stop_id: str | None = None, stop_nr: str | None = None, line: str | None = None) -> str:
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
        """Reduce a value to letters, digits, ``_`` and ``-`` (anything else becomes ``*``), so it is safe in a log line."""
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
def _ctxp(params: dict[str, Any] | None) -> str:
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
    """Asks the City of Warsaw for the timetable, the lines and the name of one line at one pole.

    One client belongs to one stop unit. Which host it talks to follows from the key it is given (see ``key_kind``);
    it never sends the key anywhere else.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        stop_id: str,
        stop_number: str,
        line: str,
        timeout: int | None = None,
        user_agent: str | None = None,
        catalogue: StopCatalogue | None = None,
    ):
        """Prepare the requests for this stop; nothing is sent until ``get``, ``get_lines`` or ``get_stop_name`` is called.

        ``timeout`` is in seconds (20 by default); ``catalogue`` is the shared list of stops (a private one, which keeps
        nothing, when none is given).
        """
        api_key = api_key.strip()
        self._user_agent = user_agent
        self._catalogue = catalogue or StopCatalogue(ttl=0)  # alone: nothing is kept
        self._legacy = bool(_LEGACY_KEY.match(api_key))
        # Endpoint to fetch the timetable for a given stop, line, and post number
        self._endpoint = "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
        # Endpoint to fetch metadata for stops (name, location, etc.)
        self._stop_info_endpoint = "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
        self._stop_info_data_id = "ab75c33d-3a26-4342-b36a-6e5fef0a3ac3"
        self._data_id = "e923fa0e-d96c-43f9-ae6e-60518c9f3238"  # timetable endpoint id (dbtimetable_get)
        self._timeout = timeout or 20
        self._session = session
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
        self._stop_name: dict[str, Any] | None = None
        self._outage_said = False  # a failed request is in the log: the next ones are not, until the City answers again
        self._no_response_said = False  # the same for "no response" of the timetable

    async def _call(self, kind: str) -> Any:
        """One request for the ``timetable``, the ``lines`` at the stop or the ``stops`` of this client, on the host
        that matches its key. The answer has the legacy shape ``{"result": ...}`` whichever host sent it.
        """
        params = self._params
        limit = _MAX_CATALOGUE_BYTES if kind == "stops" else _MAX_BYTES
        if self._legacy:
            if kind == "stops":
                params = {"id": self._stop_info_data_id, "apikey": params["apikey"]}
            elif kind == "lines":
                params = {**{k: params[k] for k in ("apikey", "busstopId", "busstopNr")}, "id": _LEGACY_LINES_ID}
            return await self._get_with_retry(self._endpoint, params, limit=limit)
        keys = {"timetable": ("busstopId", "busstopNr", "line"), "lines": ("busstopId", "busstopNr"), "stops": ()}[kind]
        action = {"timetable": _NEW_TIMETABLE, "lines": _NEW_LINES, "stops": _NEW_STOPS}[kind]
        return await self._get_with_retry(
            _NEW_API + action, None, method="POST", json_body={k: str(params[k]) for k in keys} if keys else None,
            headers={"Authorization": params["apikey"]}, wrap=True, limit=limit,
        )

    async def get_vehicles(self, kind: int) -> list[Any] | None:
        """The rows of the City's vehicle positions for the buses (``kind`` 1) or the trams (2), as the City sends them
        (``Lines``, ``Brigade``, ``VehicleNumber``, ``Lat``, ``Lon``, ``Time``); None when the answer is missing or is not a list.
        Only the new host serves them, so an old key gets None without a request."""
        if self._legacy:
            return None
        answer = await self._get_with_retry(
            _NEW_API + _NEW_VEHICLES, None, method="POST", json_body={"type": kind},
            headers={"Authorization": self._params["apikey"]}, wrap=True,
        )
        result = answer.get("result") if isinstance(answer, dict) else None
        return result if isinstance(result, list) else None

    @property
    def uses_token(self) -> bool:
        """Whether the key is a token of the new host (and not an old key); the shared catalogue keeps one index per kind."""
        return not self._legacy

    def has_same_key_as(self, other: "ZTMStopClient") -> bool:
        """Whether both clients use the same key (they then share one feed of vehicle positions); the key itself is not handed out."""
        return bool(self._params["apikey"] == other._params["apikey"])

    async def get_lines(self) -> list[str] | None:
        """The lines that stop at this pole today; None when the request failed. Raises ZTMApiError like get()."""
        answer = await self._call("lines")
        if answer is None:
            return None
        rows = _checked_result(answer)
        return [v["value"] for row in rows if isinstance(row, dict)
                for v in row.get("values") or [] if isinstance(v, dict) and v.get("key") == "linia"]

    async def stop_in_catalogue(self) -> bool | None:
        """Whether this stop pole is in the stops catalogue; None when the catalogue could not be read.

        The new API answers every rejected request with the same HTTP 500, so when a request fails this is how to
        tell a stop that does not exist (False) from a service that is down or a token that is refused (None).
        """
        answer = await self._call("stops")
        if answer is None:
            return None
        try:
            rows = _checked_result(answer)
        except ZTMApiError:
            return None
        return any(
            (str(f.get("zespol")), str(f.get("slupek"))) == (str(self._params["busstopId"]), str(self._params["busstopNr"]))
            for f in map(_stop_fields, rows)
        )

    async def _get_with_retry(self, url: str, params: dict[str, Any] | None, *, expect_json: bool = True,
                              method: str = "GET", json_body: dict[str, Any] | None = None,
                              headers: dict[str, str] | None = None, wrap: bool = False, limit: int = _MAX_BYTES) -> Any:
        """Send the request with a timeout and a small retry on timeout, network error and 5xx.

        Redirects are never followed: the request carries the key, and a 3xx is an error. ``wrap`` puts a bare
        JSON answer into ``{"result": ...}``. Returns the answer, or None when the request finally failed.
        # English-only comments for OSS clarity
        """
        attempt = 0
        while True:
            reason = None
            try:
                result = await self._attempt(url, params, expect_json, method, json_body, headers, wrap, attempt, limit)
            except asyncio.TimeoutError:
                reason = f"timeout after {self._timeout}s"
            except aiohttp.ClientError as err:
                # The text of a network error can carry the URL, and so the key: only its class is logged.
                reason = f"network error ({type(err).__name__})"
            else:
                if result is not _RETRY:
                    self._say_answered(result)
                    return result
            if reason is not None:
                final = attempt >= self._max_retries
                self._say_failed(url, reason, attempt, final)
                if final:
                    return None
            attempt += 1
            await asyncio.sleep(self._retry_backoff * attempt)

    def _say_failed(self, url: str, reason: str, attempt: int, final: bool) -> None:
        """Log a failed request: loudly when an outage starts, at debug level while it goes on (it is said once, not at every try)."""
        if self._legacy:  # the old API: one clear line for all the stops, the rest only for debugging
            if final and not self._catalogue.old_api_said:
                self._catalogue.old_api_said = True
                _LOGGER.warning(
                    "The City of Warsaw's old API (api.um.warszawa.pl) does not answer and may have been switched off. "
                    "Replace the old key with a token: see the notice in Settings > Repairs (%s)", reason)
            else:
                _LOGGER.debug("Request to %s failed: %s", url, reason)
            self._outage_said = self._outage_said or final
            return
        if final:
            _LOGGER.log(logging.DEBUG if self._outage_said else logging.ERROR, "Request to %s failed: %s", url, reason)
            self._outage_said = True
        else:
            _LOGGER.log(logging.DEBUG if self._outage_said else logging.WARNING, "Request to %s failed: %s; retrying (%s/%s)", url, reason, attempt + 1, self._max_retries)

    def _say_answered(self, result: Any) -> None:
        """An answer after an outage that was said: say that the City is back (once)."""
        if result is not None and self._outage_said:
            self._outage_said = False
            if not self._legacy or self._catalogue.old_api_said:
                _LOGGER.info("The City of Warsaw answers again")
            if self._legacy:
                self._catalogue.old_api_said = False

    async def _attempt(self, url: str, params: dict[str, Any] | None, expect_json: bool, method: str, json_body: dict[str, Any] | None,
                       headers: dict[str, str] | None, wrap: bool, attempt: int, limit: int) -> Any:
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
                if total > limit:
                    _LOGGER.error("Response too large (>%d MB) from %s; skipping", limit // 1_000_000, url)
                    return None
                chunks.append(chunk)
            text = b"".join(chunks).decode(resp.charset or "utf-8", errors="replace")
            if 500 <= resp.status <= 599 and attempt < self._max_retries:
                self._say_failed(url, f"HTTP {resp.status}", attempt, final=False)
                return _RETRY
            if resp.status != 200:
                self._say_failed(url, f"HTTP {resp.status}", attempt, final=True)
                return None
            if not expect_json:
                return text
            try:
                value = json.loads(text)
            except ValueError:
                _LOGGER.error("Invalid JSON from %s", url)
                return None
            return {"result": value} if wrap else value

    def _say_no_response(self) -> None:
        """Log that the timetable could not be fetched, once for a run of failures (then at debug level)."""
        _LOGGER.log(
            logging.DEBUG if self._no_response_said or self._legacy else logging.WARNING,  # the old API's outage is said once, in _say_failed
            "Timetable fetch failed (no response) for %s",
            _ctxp(self._params),
        )
        self._no_response_said = True

    async def get_stop_name(self) -> Optional[dict[str, Any]]:
        """The stop's metadata (name, street, position), fetched once and cached. A failure is retried after a back-off
        and given up after a few attempts, so a missing stop name never hammers the API or blocks the timetable."""
        if self._stop_name is not None:
            return self._stop_name
        where = "stop_id=%s stop_nr=%s" % (self._params.get("busstopId"), self._params.get("busstopNr"))
        if self._stop_info_permanent_missing:
            _LOGGER.debug("Stop-info permanently marked missing for %s; skip fetch", where)
            return None
        if self._stop_info_next_retry and dt_util.utcnow().timestamp() < self._stop_info_next_retry:
            _LOGGER.debug("Stop-info fetch skipped until %s (backoff) for %s", dt_util.utc_from_timestamp(self._stop_info_next_retry), where)
            return None
        readable, info = await self._catalogue.find(self, str(self._params["busstopId"]), str(self._params["busstopNr"]))
        if readable is None:  # another entry's request failed a moment ago: not asked, not a failed attempt of ours
            return None
        if info is None:
            if readable:
                _LOGGER.warning("Stop name not found in stop info for %s", where)
            self._stop_info_failed(where)
            return None
        if "nazwa_zespolu" in info and "stop_name" not in info:
            info["stop_name"] = info["nazwa_zespolu"]  # a stable alias for the sensors
        self._stop_info_attempts, self._stop_info_next_retry, self._stop_info_permanent_missing = 0, None, False
        self._stop_name = info
        return self._stop_name

    async def _stop_info_rows(self) -> list[Any] | None:
        """The rows of the stops catalogue, or None when the answer is missing or not a list (a string is a transient
        message of the old API: asked once more after a short wait)."""
        answer = await self._call("stops")
        result = answer.get("result") if isinstance(answer, dict) else None
        if isinstance(result, str):
            await asyncio.sleep(0.8)
            retry = await self._call("stops")
            result = retry.get("result") if isinstance(retry, dict) else None
        if result is not None and not isinstance(result, list):
            _LOGGER.error("Unexpected 'result' type from stop info: %s", type(result).__name__)
            return None
        return result

    def _stop_info_failed(self, where: str) -> None:
        """Count a failed attempt: wait 2 h, then 6 h, then give up until the entry is reloaded."""
        self._stop_info_attempts += 1
        if self._stop_info_attempts >= _STOP_INFO_MAX_ATTEMPTS:
            self._stop_info_permanent_missing = True
            self._stop_info_next_retry = None
            _LOGGER.info("Stop-info not available for %s after %d attempts; suppressing further retries", where, self._stop_info_attempts)
        else:
            delay = _STOP_INFO_BACKOFF[min(self._stop_info_attempts - 1, len(_STOP_INFO_BACKOFF) - 1)]
            self._stop_info_next_retry = dt_util.utcnow().timestamp() + delay
            _LOGGER.debug("Stop-info attempt %d failed; next retry in %d seconds for %s", self._stop_info_attempts, delay, where)

    async def get(self, *, fetch_stop_name: bool = True) -> Optional[ZTMDepartureData]:
        """The timetable of the stop today, or None when the request failed.

        The stop's name is fetched once on the way (``fetch_stop_name``; it respects its own back-off, so it never hammers
        the API). Raises ``ZTMApiError`` for an answer that is not a timetable, and ``ZTMAuthError`` for a rejected key.
        """
        try:
            # Ensure stop name is fetched once on first use.
            # This will not spam the API: get_stop_name() respects backoff and permanent-missing.
            if fetch_stop_name and self._stop_name is None:
                await self.get_stop_name()
            json_response = await self._call("timetable")
            if json_response is None:
                self._say_no_response()
                return None
            self._no_response_said = False
            result = _checked_result(json_response)
            service_date = service_date_at(dt_util.utcnow())

            _departures = _readings(result, service_date)

            if result and not _departures:
                raise ZTMApiError("The City of Warsaw API sent readings that cannot be read")

            # Sort departures by their scheduled time
            _departures.sort(key=_by_moment)
            _LOGGER.debug("Loaded %d departures from API", len(_departures))
            return ZTMDepartureData(departures=_departures, stop_info=self._stop_name, service_date=service_date)

        except ZTMApiError:
            raise
        except Exception:
            _LOGGER.exception("Unexpected error in timetable fetch")  # the traceback carries the error itself
        return None
