"""Fixtures for the OPTIONAL live-contract tests. Nothing here runs unless ``ZTM_LIVE_API_KEY`` is set AND the
run selects the marker (``pytest -m live``): ``pyproject.toml`` deselects ``live`` by default, so neither
the PR pipeline nor a plain ``pytest`` can reach the city's servers."""

from __future__ import annotations

import os

import pytest
import pytest_socket

LIVE_HOSTS = ["api.um.warszawa.pl", "dane.um.warszawa.pl"]


def pytest_collection_modifyitems(config, items):
    """Belt and braces: a ``live`` test without the key is skipped, never failed."""
    if os.environ.get("ZTM_LIVE_API_KEY"):
        return
    skip = pytest.mark.skip(reason="set ZTM_LIVE_API_KEY (and run `pytest -m live`) to validate the real API")
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip)


class LiveKey(str):
    """The key as a ``str`` whose ``repr`` is redacted.

    pytest prints the arguments of a failing test and of the last traceback frame, and assertion
    introspection prints the operands of a failed ``assert``; both use ``repr``. ``str()``, f-strings and
    the value itself are unchanged, so the key still works as a request parameter or header.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "<ZTM_LIVE_API_KEY redacted>"


@pytest.fixture
def live_key() -> LiveKey:
    return LiveKey(os.environ["ZTM_LIVE_API_KEY"].strip())


@pytest.fixture
def live_network(socket_enabled):
    """Let this one test open sockets to the two city hosts (the HA test plugin allows loopback only)."""
    pytest_socket.socket_allow_hosts(LIVE_HOSTS)
    yield
    pytest_socket.socket_allow_hosts(["127.0.0.1"])
