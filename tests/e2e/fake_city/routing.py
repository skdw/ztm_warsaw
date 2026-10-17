"""Route the integration's real HTTPS URLs to the fake city, without touching production code.

The shipped 1.1.4 code has NO module-level endpoint constant: the URL is an instance attribute set
in ``ZTMStopClient.__init__`` and two f-strings in ``config_flow.validate_input``. The smallest
seam that needs zero production change is therefore the transport: wrap
``aiohttp.ClientSession._request`` and rewrite only the origin (scheme/host/port) of the two known
city hosts to the fake servers' loopback ports. Everything else (path, query, headers, body,
redirect handling, response parsing) is the real aiohttp client talking real HTTP over a real
socket. Any other destination makes the test fail loudly instead of reaching a network.
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


class NetworkBlocked(Exception):  # deliberately NOT an AssertionError: xfail(raises=AssertionError) must not hide it
    """Raised when code under test tries to reach anything but the fake city."""


@contextmanager
def route_to_fake_city(fake) -> Iterator[None]:
    origin_ports = {LEGACY_HOST: fake.legacy_port, NEW_HOST: fake.new_port}
    original = aiohttp.ClientSession._request

    async def _request(self, method, str_or_url, **kwargs):
        url = URL(str_or_url)
        if url.host in origin_ports:
            url = url.with_scheme("http").with_host(LOOPBACK).with_port(origin_ports[url.host])
        elif url.host != LOOPBACK:
            # The integration wraps requests in broad ``except Exception``, so also record the attempt:
            # the ``fake_city`` fixture fails the test at teardown if this list is not empty.
            fake.blocked.append(str(url.with_query(None)))
            raise NetworkBlocked(f"test tried to reach {url.host!r}; only the fake city is allowed")
        return await original(self, method, url, **kwargs)

    with patch.object(aiohttp.ClientSession, "_request", _request):
        yield
