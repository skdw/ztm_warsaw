"""Route the integration's real HTTPS URLs to the fake city, without touching production code.

The shipped code has NO single module-level endpoint constant: the URLs are set in ``client.py``. The smallest
seam that needs zero production change is therefore the transport: wrap
``aiohttp.ClientSession._request`` and rewrite only the origin (scheme/host/port) of the two known
city hosts to the fake servers' loopback ports. Everything else (path, query, headers, body,
redirect handling, response parsing) is the real aiohttp client talking real HTTP over a real
socket. Any other destination makes the test fail loudly instead of reaching a network: the initial URL
is checked in ``_request``, and every connection (so also the target of a redirect, which aiohttp follows
inside the original ``_request``) is checked in ``TCPConnector._resolve_host``, before any DNS lookup.
pytest-socket still guards the socket layer underneath.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import aiohttp
from yarl import URL

LEGACY_HOST = "api.um.warszawa.pl"
NEW_HOST = "dane.um.warszawa.pl"
LOOPBACK = "127.0.0.1"


class HarnessError(Exception):
    """The test harness itself failed (setup, timing, a missing entity). Deliberately NOT an AssertionError:
    ``known_bug`` is ``xfail(raises=AssertionError)``, so a harness failure must stay red instead of passing as
    'the known bug is still there'."""


class NetworkBlocked(Exception):  # deliberately NOT an AssertionError: xfail(raises=AssertionError) must not hide it
    """Raised when code under test tries to reach anything but the fake city."""


@contextmanager
def route_to_fake_city(fake) -> Iterator[None]:
    """Point the aiohttp client at ``fake`` for the duration of the ``with`` block.

    Requests to the two city hosts are rewritten to the fake's loopback ports; any other destination raises
    ``NetworkBlocked`` and is recorded in ``fake.blocked``."""
    origin_ports = {LEGACY_HOST: fake.legacy_port, NEW_HOST: fake.new_port}
    fake_ports = set(origin_ports.values())
    original = aiohttp.ClientSession._request
    original_resolve = aiohttp.TCPConnector._resolve_host

    def block(destination: str) -> NetworkBlocked:
        """Record the refused ``destination`` and return the exception to raise for it."""
        # The integration wraps requests in broad ``except Exception``, so also record the attempt:
        # the ``fake_city`` fixture fails the test at teardown if this list is not empty.
        fake.blocked.append(destination)
        return NetworkBlocked(f"test tried to reach {destination!r}; only the fake city is allowed")

    async def _request(self, method, str_or_url, **kwargs):
        """Rewrite the origin of a city URL to its fake port, refuse anything else, then do the real request."""
        url = URL(str_or_url)
        if url.host in origin_ports:
            url = url.with_scheme("http").with_host(LOOPBACK).with_port(origin_ports[url.host])
        elif url.host != LOOPBACK or url.port not in fake_ports:
            raise block(str(url.with_query(None)))
        return await original(self, method, url, **kwargs)

    async def _resolve_host(self, host, port, traces=None):
        """Refuse every connection that is not to a fake city port, before any DNS lookup; this also covers redirects."""
        if host != LOOPBACK or port not in fake_ports:
            raise block(f"{host}:{port}")
        return await original_resolve(self, host, port, traces)

    with (
        patch.object(aiohttp.ClientSession, "_request", _request),
        patch.object(aiohttp.TCPConnector, "_resolve_host", _resolve_host),
    ):
        yield
