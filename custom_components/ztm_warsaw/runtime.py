"""What a loaded entry holds while it runs (its ``runtime_data``), typed.

A line (version 2) has a coordinator and a client for each of its stops, by subentry id; an entry of 1.1.x (version 1, one
stop) holds that one pair itself. ``ZtmConfigEntry`` is the config entry with this data, so that mypy can check every use of
``entry.runtime_data`` (the strict-typing rule of Home Assistant's quality scale).
"""

from __future__ import annotations

from typing import TypedDict

from homeassistant.config_entries import ConfigEntry

from .client import ZTMStopClient
from .coordinator import ZTMStopCoordinator


class StopRuntime(TypedDict):
    """The running parts of one stop: its coordinator (the timetable) and its client (the City)."""

    coordinator: ZTMStopCoordinator
    client: ZTMStopClient


class LineRuntime(TypedDict):
    """The running stops of a line entry by subentry id."""

    units: dict[str | None, StopRuntime]


type RuntimeData = LineRuntime | StopRuntime
type ZtmConfigEntry = ConfigEntry[RuntimeData]
