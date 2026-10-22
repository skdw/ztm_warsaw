"""The stops of every line, shipped with the integration.

The City of Warsaw's open data has no list of the stops a line serves, and the setup starts from the line. ``line_stops.json``
holds that list (``scripts/build_line_index.py`` builds it from the City's lines at every pole, and is run again at each release,
because the City changes its lines a few times a year). It is small, and read once per Home Assistant start.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

INDEX_FILE = Path(__file__).parent / "line_stops.json"
_KEY = f"{DOMAIN}_line_index"


def line_order(line: str) -> tuple[int, int, str]:
    """How a person reads a list of lines: the numbers first, then the letters (N31, S4)."""
    return (0, int(line), line) if line.isdigit() else (1, 0, line)


def _read() -> dict[str, list[str]] | None:
    """The index from its file (in the executor), or None when the file is missing or not what it should be."""
    try:
        lines = json.loads(INDEX_FILE.read_text(encoding="utf-8"))["lines"]
    except (OSError, ValueError, KeyError, TypeError):
        _LOGGER.warning("The list of the stops of each line (line_stops.json) could not be read, so the setup asks for the numbers")
        return None
    if not isinstance(lines, dict) or not all(isinstance(ids, list) for ids in lines.values()):
        _LOGGER.warning("The list of the stops of each line (line_stops.json) is not in the expected shape")
        return None
    return {str(line): [str(stop) for stop in ids] for line, ids in lines.items()}


async def async_line_stops(hass: HomeAssistant) -> dict[str, list[str]] | None:
    """``{line: [stop IDs]}``, read once and kept; None when it cannot be read (the setup then falls back to the numbers)."""
    if _KEY not in hass.data:
        hass.data[_KEY] = await hass.async_add_executor_job(_read)
    result: dict[str, list[str]] | None = hass.data[_KEY]
    return result
