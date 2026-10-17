"""Read an HTTP response body completely, but never more than the integration's own size cap."""

from __future__ import annotations

import aiohttp

from tests.contract_shapes import RESPONSE_CAP_BYTES


async def read_capped(resp: aiohttp.ClientResponse, cap: int = RESPONSE_CAP_BYTES) -> bytes:
    """Return the whole body, or just past ``cap`` bytes if the body is larger (so the caller can tell).

    ``StreamReader.read(n)`` returns as soon as ANY data is buffered and may hand back fewer than ``n`` bytes,
    which would pass a truncated body on as if it were the whole response; read chunk by chunk until EOF.
    """
    body = bytearray()
    async for chunk in resp.content.iter_chunked(64 * 1024):
        body += chunk
        if len(body) > cap:
            break
    return bytes(body)
