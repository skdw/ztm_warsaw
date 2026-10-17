"""Failure modes the fake city can be told to produce, per endpoint.

A behavior is applied INSTEAD of the normal answer. ``Mutate`` is the exception: it lets the normal
handler run and then edits the payload (malformed rows etc.).
"""

from __future__ import annotations

import json
import socket
import struct
from collections.abc import Callable
from typing import Any

from aiohttp import web

from .data import BAD_KEY_PAYLOAD, PARAM_ERROR_TEXT


class Behavior:
    """Base class. ``respond`` returns the response to send, or ``None`` for 'carry on normally'."""

    name = "behavior"

    async def respond(self, fake: Any, call: Any, request: web.Request) -> web.StreamResponse | None:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.name}>"


class Respond(Behavior):
    """A fixed HTTP answer."""

    def __init__(
        self,
        status: int = 200,
        body: Any = None,
        *,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        name: str | None = None,
    ) -> None:
        self.status = status
        self.body = body
        self.content_type = content_type
        self.headers = headers or {}
        if name:
            self.name = name

    async def respond(self, fake, call, request):
        if isinstance(self.body, bytes):
            data = self.body
        elif isinstance(self.body, str):
            data = self.body.encode("utf-8")
        else:
            data = json.dumps(self.body, ensure_ascii=False).encode("utf-8")
        return web.Response(
            status=self.status,
            body=data,
            headers=self.headers,
            content_type=self.content_type,
            charset="utf-8" if self.content_type.startswith(("application/json", "text/")) else None,
        )


def BadKey() -> Behavior:
    """Legacy answer to an unknown/expired key: HTTP 200 + result "false" (measured)."""
    return Respond(200, BAD_KEY_PAYLOAD, name="bad_key")


def ParamError() -> Behavior:
    """Legacy answer to an unknown stop/line or missing params: HTTP 200 + text in result (measured)."""
    return Respond(200, {"result": PARAM_ERROR_TEXT}, name="param_error_text")


def NullResult() -> Behavior:
    """Legacy answer for a line that exists but does not run today (measured)."""
    return Respond(200, {"result": None}, name="result_null")


def EmptyList() -> Behavior:
    return Respond(200, {"result": []}, name="result_empty_list")


def Http(status: int, body: Any = None) -> Behavior:
    return Respond(status, body if body is not None else {"message": "Service unavailable"}, name=f"http_{status}")


def InvalidJson() -> Behavior:
    return Respond(200, '{"result": [[{"key": "czas", "value": "12:0', name="invalid_json")


def Html() -> Behavior:
    return Respond(
        200,
        "<html><head><title>Maintenance</title></head><body><h1>Serwis niedostępny</h1></body></html>",
        content_type="text/html",
        name="html",
    )


def Oversize(total_bytes: int = 2_500_000) -> Behavior:
    """A valid JSON envelope that is larger than the integration's 2 MB cap."""
    pad = "x" * total_bytes
    return Respond(200, json.dumps({"result": [], "pad": pad}), name="oversize")


def Redirect(location: str, status: int = 302) -> Behavior:
    return Respond(status, b"", headers={"Location": location}, name=f"redirect_{status}")


class RedirectSelf(Behavior):
    """302 to the very same URL (query included): a redirect loop, ends in aiohttp's TooManyRedirects."""

    name = "redirect_loop"

    async def respond(self, fake, call, request):
        return web.Response(status=302, headers={"Location": str(request.rel_url)})


class RedirectOnce(Behavior):
    """302 to the same URL once, then answer normally (a benign same-origin redirect)."""

    name = "redirect_once"

    def __init__(self) -> None:
        self._done = False

    async def respond(self, fake, call, request):
        if self._done:
            return None
        self._done = True
        return web.Response(status=302, headers={"Location": str(request.rel_url)})


class Reset(Behavior):
    """Kill the TCP connection with an RST (what the 04:35 ConnectionResetError looked like)."""

    name = "connection_reset"

    async def respond(self, fake, call, request):
        transport = request.transport
        if transport is not None:
            sock = transport.get_extra_info("socket")
            if sock is not None:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            transport.abort()
        return web.Response(status=200)  # never reaches the client


class Truncated(Behavior):
    """Promise a long body, send a little, then drop the connection (ClientPayloadError)."""

    name = "truncated_body"

    async def respond(self, fake, call, request):
        resp = web.StreamResponse(status=200, headers={"Content-Type": "application/json"})
        resp.content_length = 5000
        await resp.prepare(request)
        await resp.write(b'{"result": [[{"key": "czas", "val')
        if request.transport is not None:
            request.transport.abort()
        return resp


class Hang(Behavior):
    """Accept the request and never answer until the test releases the gate (client timeout test)."""

    name = "hang"

    async def respond(self, fake, call, request):
        call.hanging = True
        fake._hanging += 1
        try:
            await fake._gate.wait()
        finally:
            fake._hanging -= 1
        return web.Response(status=200, text="released", content_type="text/plain")


class Mutate(Behavior):
    """Run the normal handler, then let ``fn(payload)`` edit the decoded JSON before it is sent."""

    def __init__(self, fn: Callable[[Any], Any], name: str = "mutate") -> None:
        self.fn = fn
        self.name = name

    async def respond(self, fake, call, request):
        call.mutator = self.fn
        return None


def drop_czas_from_first_row(payload: Any) -> Any:
    """Malformed row: a reading without ``czas`` (known bug: missing-czas-phantom-departure)."""
    rows = payload["result"] if isinstance(payload, dict) else payload
    if rows:
        rows[0] = [e for e in rows[0] if e["key"] != "czas"]
    return payload
