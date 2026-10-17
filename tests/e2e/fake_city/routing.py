"""Route the integration's real HTTPS URLs to the fake city, without touching production code.

The shipped 1.1.4 code has NO module-level endpoint constant: the URL is an instance attribute set
in ``ZTMStopClient.__init__`` and two f-strings in ``config_flow.validate_input``. The smallest
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
    origin_ports = {LEGACY_HOST: fake.legacy_port, NEW_HOST: fake.new_port}
    fake_ports = set(origin_ports.values())
    original = aiohttp.ClientSession._request
    original_resolve = aiohttp.TCPConnector._resolve_host

    def block(destination: str) -> NetworkBlocked:
        # The integration wraps requests in broad ``except Exception``, so also record the attempt:
        # the ``fake_city`` fixture fails the test at teardown if this list is not empty.
        fake.blocked.append(destination)
        return NetworkBlocked(f"test tried to reach {destination!r}; only the fake city is allowed")

    async def _request(self, method, str_or_url, **kwargs):
        url = URL(str_or_url)
        if url.host in origin_ports:
            url = url.with_scheme("http").with_host(LOOPBACK).with_port(origin_ports[url.host])
        elif url.host != LOOPBACK or url.port not in fake_ports:
            raise block(str(url.with_query(None)))
        return await original(self, method, url, **kwargs)

    async def _resolve_host(self, host, port, traces=None):
        if host != LOOPBACK or port not in fake_ports:
            raise block(f"{host}:{port}")
        return await original_resolve(self, host, port, traces)

    with (
        patch.object(aiohttp.ClientSession, "_request", _request),
        patch.object(aiohttp.TCPConnector, "_resolve_host", _resolve_host),
    ):
        yield
