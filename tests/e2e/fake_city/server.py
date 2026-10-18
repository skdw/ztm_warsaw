"""A fake City of Warsaw API on localhost.

Two aiohttp servers on 127.0.0.1 (random ports), sharing one state object:

* ``legacy``: the contract the integration speaks today, measured on api.um.warszawa.pl:
  ``GET /api/action/dbtimetable_get/?id=<dataset>&busstopId&busstopNr&line&apikey`` answering
  ``{"result": ...}`` (see ``data/README.md`` for what was captured and what is derived).
* ``new``: the dane.um.warszawa.pl contract, measured on 2026-10-18 with the maintainer's own token
  (``data/README.md``): ``POST /api/action/<action>`` with a raw ``Authorization: <JWT>`` header and a JSON
  body of STRINGS, answering a BARE list (``null`` for a line that does not run today). EVERY rejected request
  is the same HTTP 500 ``{"message":"Service unavailable"}``. Whatever no measurement covers is marked
  ``UNVERIFIED`` below: a placeholder, not knowledge.

The "service day" is a pure function of the clock the test controls (``freezer``): before
``flip_at`` (default 03:00 Warsaw; measured between 02:55:51 and 03:00:51) the previous date's schedule is served.
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import timezone, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import web
from aiohttp.test_utils import TestServer
from homeassistant.util import dt as dt_util

from . import data
from .behaviors import BadKey, Behavior, NullResult, ParamError, Respond
from .data import (
    LEGACY_LINES_ID,
    LEGACY_STOPS_ID,
    LEGACY_TIMETABLE_ID,
    NEW_ACTION_LINES,
    NEW_ACTION_STOPS,
    NEW_ACTION_TIMETABLE,
    SERVICE_UNAVAILABLE_PAYLOAD,
    DaySet,
)

WARSAW = ZoneInfo("Europe/Warsaw")
# Synthetic, obviously fake credentials for the fake city; none of them was ever issued by anyone.
DEFAULT_KEY = "11111111-2222-3333-4444-555555555555"  # legacy-shaped (UUID)  # gitleaks:allow


def _fake_jwt() -> str:
    """A JWT-SHAPED string built at import time, so no literal ``ey...`` token sits in the source for scanners."""
    part = lambda obj: base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()  # noqa: E731
    return ".".join([part({"alg": "none"}), part({"sub": "ztm-e2e-fake"}), "not-a-real-signature"])


DEFAULT_TOKEN = _fake_jwt()  # new-contract-shaped

ENDPOINTS = ("timetable", "lines", "stops")


@dataclass
class Call:
    """One HTTP request as the fake city saw it."""

    n: int
    contract: str  # "legacy" | "new"
    endpoint: str  # "timetable" | "lines" | "stops" | "unknown"
    method: str
    path: str
    query: dict[str, str]
    query_string: str
    body: Any
    key: str | None  # legacy ?apikey= or new Authorization header (raw, test-only)
    at_utc: datetime
    service_date: date
    day_set: str
    behavior: str = "ok"
    status: int | None = None
    bytes_sent: int = 0
    hanging: bool = False
    user_agent: str | None = None  # the User-Agent header the request carried
    mutator: Any = field(default=None, repr=False)

    @property
    def params(self) -> dict[str, str]:
        """busstopId/busstopNr/line from the query (legacy) or the body (new)."""
        src = self.query if self.contract == "legacy" else (self.body if isinstance(self.body, dict) else {})
        return {k: str(v) for k, v in src.items() if k in ("busstopId", "busstopNr", "line")}


@dataclass
class _Rule:
    endpoint: str | None
    contract: str | None
    queue: deque
    repeat_last: bool

    def matches(self, call: Call) -> bool:
        return (self.endpoint in (None, call.endpoint)) and (self.contract in (None, call.contract))

    def next(self) -> Behavior | None:
        if not self.queue:
            return None
        if len(self.queue) == 1 and self.repeat_last:
            return self.queue[0]
        return self.queue.popleft()


class FakeCity:
    def __init__(
        self,
        *,
        valid_keys: tuple[str, ...] = (DEFAULT_KEY,),
        valid_tokens: tuple[str, ...] = (DEFAULT_TOKEN,),
        catalogue_bytes: int = data.SMALL_CATALOGUE,
        flip_at: time = time(3, 0),
    ) -> None:
        self.valid_keys = set(valid_keys)
        self.valid_tokens = set(valid_tokens)
        self.catalogue_bytes = catalogue_bytes
        self.flip_at = flip_at
        self.ensure_ascii = False
        self.day_overrides: dict[date, str] = {}  # force a day set for a service date
        self.calls: list[Call] = []
        self.blocked: list[str] = []  # attempts to reach a host that is not the fake city
        self._rules: list[_Rule] = []
        self._gate = asyncio.Event()
        self._hanging = 0
        self._hang_waiters: list[tuple[int, asyncio.Future]] = []
        self._offline = False
        self._legacy = TestServer(self._legacy_app(), host="127.0.0.1", port=0)
        self._new = TestServer(self._new_app(), host="127.0.0.1", port=0)

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        # access_log=None: the fake's access log would print every ?apikey=... and pollute log assertions
        await self._legacy.start_server(access_log=None)
        await self._new.start_server(access_log=None)

    async def stop(self) -> None:
        self.release_hangs()
        for _ in range(5):  # let released handlers finish before the runner is torn down
            await asyncio.sleep(0)
        if not self._offline:
            await self._legacy.close()
        await self._new.close()

    async def take_offline(self) -> None:
        """Stop listening on the legacy port: the next connection attempt is refused (server down)."""
        self.release_hangs()
        await asyncio.sleep(0)
        await self._legacy.close()
        self._offline = True

    @property
    def legacy_port(self) -> int:
        return self._legacy.port

    @property
    def new_port(self) -> int:
        return self._new.port

    # ------------------------------------------------------------------ test control
    def script(
        self,
        endpoint: str | None,
        *behaviors: Behavior,
        contract: str | None = None,
        repeat_last: bool = False,
    ) -> None:
        """Answer the next requests of ``endpoint`` with these behaviors, in order.

        ``repeat_last=True`` keeps applying the last one until :meth:`heal`.
        """
        self._rules.append(_Rule(endpoint, contract, deque(behaviors), repeat_last))

    def always(self, endpoint: str | None, behavior: Behavior, *, contract: str | None = None) -> None:
        self.script(endpoint, behavior, contract=contract, repeat_last=True)

    def heal(self) -> None:
        """Drop every scripted behavior (and release hanging requests)."""
        self._rules.clear()
        self.release_hangs()

    def release_hangs(self) -> None:
        self._gate.set()

    def rearm_hangs(self) -> None:
        self._gate.clear()

    def hung_total(self) -> int:
        """How many requests have entered a Hang behavior so far (finished or not)."""
        return sum(1 for c in self.calls if c.hanging)

    def _hang_started(self) -> None:
        """Called by the Hang behavior once a request is stuck: wake the waiters whose threshold is met."""
        total = self.hung_total()
        for waiter in list(self._hang_waiters):
            threshold, future = waiter
            if total >= threshold and not future.done():
                future.set_result(None)
            if future.done():
                self._hang_waiters.remove(waiter)

    async def wait_hung(self, n: int = 1) -> None:
        """Wait until ``n`` requests in total have hit a Hang.

        Event-driven, not a bounded spin: a spin budget is a race against the speed of the machine (it ran out
        on a CI runner with coverage tracing). If a request never arrives, the per-test timeout ends the test.
        """
        if self.hung_total() >= n:
            return
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._hang_waiters.append((n, future))
        try:
            await future
        finally:
            self._hang_waiters[:] = [w for w in self._hang_waiters if w[1] is not future]

    # ------------------------------------------------------------------ counting
    def count(self, endpoint: str | None = None, contract: str | None = None, **match: str) -> int:
        return len(self.matching(endpoint, contract, **match))

    def matching(self, endpoint: str | None = None, contract: str | None = None, **match: str) -> list[Call]:
        out = []
        for c in self.calls:
            if endpoint is not None and c.endpoint != endpoint:
                continue
            if contract is not None and c.contract != contract:
                continue
            if any(c.params.get(k) != str(v) for k, v in match.items()):
                continue
            out.append(c)
        return out

    def bytes_sent(self, endpoint: str | None = None) -> int:
        return sum(c.bytes_sent for c in self.matching(endpoint))

    def reset_counts(self) -> None:
        self.calls.clear()

    # ------------------------------------------------------------------ service day
    def now(self) -> datetime:
        return dt_util.utcnow()

    def service_date(self, now: datetime | None = None) -> date:
        moment = now or self.now()
        local = moment.astimezone(WARSAW)
        # The flip is one instant: the first time the clock shows ``flip_at`` that night. Comparing wall times would
        # roll back to yesterday during the repeated hour of the autumn night.
        flip = datetime.combine(local.date(), self.flip_at, WARSAW).astimezone(timezone.utc)
        return local.date() if moment >= flip else local.date() - timedelta(days=1)

    def day_set_for(self, d: date) -> DaySet:
        name = self.day_overrides.get(d) or ("friday" if d.weekday() < 5 else "saturday")
        return data.day_sets()[name]

    def current_day_set(self) -> DaySet:
        return self.day_set_for(self.service_date())

    # ------------------------------------------------------------------ apps
    def _legacy_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/api/action/dbtimetable_get/", self._legacy_handler)
        app.router.add_get("/api/action/dbtimetable_get", self._legacy_handler)
        app.router.add_route("*", "/{tail:.*}", self._not_found)
        return app

    def _new_app(self) -> web.Application:
        app = web.Application()
        app.router.add_route("*", "/api/action/{action}", self._new_handler)
        app.router.add_route("*", "/{tail:.*}", self._not_found)
        return app

    async def _not_found(self, request: web.Request) -> web.Response:
        call = self._new_call(request, "legacy" if request.app is self._legacy.app else "new", "unknown", None, None)
        return self._finish(call, web.json_response({"message": "fake city: no such route"}, status=404))

    # ------------------------------------------------------------------ helpers
    def _new_call(self, request, contract, endpoint, key, body) -> Call:
        now = self.now()
        sd = self.service_date(now)
        call = Call(
            n=len(self.calls) + 1,
            contract=contract,
            endpoint=endpoint,
            method=request.method,
            path=request.path,
            query=dict(request.query),
            query_string=request.query_string,
            body=body,
            key=key,
            at_utc=now,
            service_date=sd,
            day_set=self.day_set_for(sd).name,
            user_agent=request.headers.get("User-Agent"),
        )
        self.calls.append(call)
        return call

    def _finish(self, call: Call, resp: web.StreamResponse) -> web.StreamResponse:
        call.status = resp.status
        body = getattr(resp, "body", None)
        if isinstance(body, bytes | bytearray):
            call.bytes_sent = len(body)
        return resp

    def _pick_behavior(self, call: Call) -> Behavior | None:
        for rule in self._rules:
            if rule.matches(call):
                behavior = rule.next()
                if behavior is not None:
                    return behavior
        return None

    def _json(self, payload: Any, status: int = 200) -> web.Response:
        return web.Response(
            status=status,
            body=json.dumps(payload, ensure_ascii=self.ensure_ascii).encode("utf-8"),
            content_type="application/json",
            charset="utf-8",
        )

    def _new_json(self, payload: Any, status: int = 200) -> web.Response:
        """The new host's JSON as measured: compact separators, UTF-8 bytes, NO charset in the Content-Type."""
        return web.Response(
            status=status,
            body=json.dumps(payload, ensure_ascii=self.ensure_ascii, separators=(",", ":")).encode("utf-8"),
            content_type="application/json",
        )

    # ------------------------------------------------------------------ legacy contract
    async def _legacy_handler(self, request: web.Request) -> web.StreamResponse:
        q = request.query
        dataset = q.get("id")
        endpoint = {LEGACY_TIMETABLE_ID: "timetable", LEGACY_LINES_ID: "lines", LEGACY_STOPS_ID: "stops"}.get(
            dataset or "", "unknown"
        )
        call = self._new_call(request, "legacy", endpoint, q.get("apikey"), None)

        behavior = self._pick_behavior(call)
        if behavior is not None:
            call.behavior = behavior.name
            resp = await behavior.respond(self, call, request)
            if resp is not None:
                return self._finish(call, resp)

        resp = await self._legacy_answer(call, q)
        if call.mutator is not None and isinstance(resp, web.Response) and resp.body:
            payload = json.loads(resp.body)
            resp = self._json(call.mutator(payload))
        return self._finish(call, resp)

    async def _legacy_answer(self, call: Call, q) -> web.Response:
        if call.key not in self.valid_keys:
            call.behavior = "bad_key"
            return await BadKey().respond(self, call, None)  # type: ignore[arg-type]
        if call.endpoint == "stops":
            return web.Response(
                body=data.stops_catalogue_bytes(self.catalogue_bytes, ensure_ascii=self.ensure_ascii),
                content_type="application/json",
                charset="utf-8",
            )
        stop_id, nr, line = q.get("busstopId"), q.get("busstopNr"), q.get("line")
        ds = self.current_day_set()
        if call.endpoint == "lines":
            if not stop_id or not nr or (stop_id, nr) not in data.all_known_stops():
                return await ParamError().respond(self, call, None)  # type: ignore[arg-type]
            lines = ds.lines.get((stop_id, nr), [])
            return self._json({"result": [{"values": [{"key": "linia", "value": ln}]} for ln in lines]})
        if call.endpoint == "timetable":
            if not stop_id or not nr or not line or (((stop_id, nr), line)) not in data.all_known_pairs():
                return await ParamError().respond(self, call, None)  # type: ignore[arg-type]
            rows = ds.timetables.get(((stop_id, nr), line))
            if rows is None:  # known pair, not running on this service day
                return await NullResult().respond(self, call, None)  # type: ignore[arg-type]
            return self._json({"result": rows})
        return await ParamError().respond(self, call, None)  # type: ignore[arg-type]

    # ------------------------------------------------------------------ new contract
    async def _new_handler(self, request: web.Request) -> web.StreamResponse:
        action = request.match_info["action"]
        endpoint = {NEW_ACTION_TIMETABLE: "timetable", NEW_ACTION_LINES: "lines", NEW_ACTION_STOPS: "stops"}.get(
            action, "unknown"
        )
        body: Any = None
        if request.can_read_body:
            raw = await request.read()
            try:
                body = json.loads(raw)
                if isinstance(body, str):  # a JSON *string* holding JSON (double-encoded)
                    body = json.loads(body)
            except ValueError:
                body = {"_unparseable": raw[:80].decode("utf-8", "replace")}
        call = self._new_call(request, "new", endpoint, request.headers.get("Authorization"), body)

        behavior = self._pick_behavior(call)
        if behavior is not None:
            call.behavior = behavior.name
            resp = await behavior.respond(self, call, request)
            if resp is not None:
                return self._finish(call, resp)

        resp = self._new_answer(call, request)
        if call.mutator is not None and isinstance(resp, web.Response) and resp.body:
            resp = self._json(call.mutator(json.loads(resp.body)))
        return self._finish(call, resp)

    def _new_answer(self, call: Call, request: web.Request) -> web.Response:
        """OBSERVED on the real service on 2026-10-18 unless a line says UNVERIFIED (see data/README.md)."""
        if call.endpoint == "unknown":  # UNVERIFIED: whether this is checked before the method and the token
            return self._new_json({"message": "Resource not found"}, status=404)
        if request.method != "POST":
            return self._new_json({"detail": "Method Not Allowed"}, status=405)
        if call.key not in self.valid_tokens:  # no header, "x.y.z", a forged signature or "Bearer <token>": the same
            call.behavior = "bad_token"
            return self._new_json(SERVICE_UNAVAILABLE_PAYLOAD, status=500)
        if call.endpoint == "stops":
            return web.Response(
                body=data.stops_catalogue_bytes(self.catalogue_bytes, ensure_ascii=self.ensure_ascii, new_host=True),
                content_type="application/json",
            )
        body = call.body if isinstance(call.body, dict) else {}
        wanted = ("busstopId", "busstopNr", "line") if call.endpoint == "timetable" else ("busstopId", "busstopNr")
        if not all(isinstance(body.get(key), str) and body[key] for key in wanted):
            # A missing parameter, an empty object and numbers instead of strings all answer like a bad token.
            call.behavior = "bad_params"
            return self._new_json(SERVICE_UNAVAILABLE_PAYLOAD, status=500)
        stop = (body["busstopId"], body["busstopNr"])
        ds = self.current_day_set()
        if call.endpoint == "lines":
            if stop not in data.all_known_stops():  # OBSERVED for 9999/99
                call.behavior = "unknown_stop"
                return self._new_json(SERVICE_UNAVAILABLE_PAYLOAD, status=500)
            # UNVERIFIED: a known stop that has no line at all on this service day
            return self._new_json([{"values": [{"value": ln, "key": "linia"}]} for ln in ds.lines.get(stop, [])])
        pair = (stop, body["line"])
        if pair not in data.all_known_pairs():  # OBSERVED for line ZZZ at a real stop and for 9999/99
            # UNVERIFIED: a line that exists elsewhere but is not served at this stop
            call.behavior = "unknown_pair"
            return self._new_json(SERVICE_UNAVAILABLE_PAYLOAD, status=500)
        rows = ds.timetables.get(pair)
        if rows is None:  # OBSERVED for line 411 on a Saturday: HTTP 200 and the bare JSON value null
            call.behavior = "null"
            return self._new_json(None)
        return self._new_json([[{"value": e["value"], "key": e["key"]} for e in row] for row in rows])


__all__ = ["DEFAULT_KEY", "DEFAULT_TOKEN", "ENDPOINTS", "Call", "FakeCity", "Respond"]
