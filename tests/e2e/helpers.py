"""Small pure helpers shared by the e2e tests: the reference oracle, mark factory, log scanner."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta

import pytest

from tests.contract_shapes import kv

from .fake_city import WARSAW, day_sets
from .fake_city.data import StopKey


def known_bug(
    finding: str, why: str, *, raises: type[BaseException] | tuple[type[BaseException], ...] = AssertionError
):
    """xfail(strict) for a CONFIRMED bug: the test states the correct behaviour.

    ``raises`` keeps the xfail honest: a harness error (KeyError, TimeoutError ...) is a failure, only the
    expected kind of failure counts as "the known bug is still there". When the bug is fixed the test
    XPASSes and strict mode turns that into a red build, which is the cue to drop the mark.
    """
    return pytest.mark.xfail(strict=True, raises=raises, reason=f"{finding}: {why}")


def find_devices(registry, identifiers):
    """The devices with these identifiers, on every Home Assistant the suite may run on.

    ``async_get_device`` is deprecated (and raises under the test plugin) from Home Assistant 2026.10, where
    ``async_get_devices`` replaces it. Also from 2026.10 a device belongs to ONE config entry, so two entries
    of the same line get two devices with the same identifiers; the older releases share one device.
    """
    lookup = getattr(registry, "async_get_devices", None)
    if lookup is not None:
        return list(lookup(identifiers=identifiers))
    device = registry.async_get_device(identifiers=identifiers)
    return [device] if device is not None else []


def owners_of(devices) -> set[str]:
    """Every config entry id that the devices belong to (``config_entries`` before 2026.10, ``config_entry_id`` after)."""
    owners: set[str] = set()
    for device in devices:
        if hasattr(device, "config_entry_id"):
            owners.add(device.config_entry_id)
        else:
            owners |= set(device.config_entries)
    return owners


def rows_for(day: str, line: str, stop: StopKey = ("7009", "01")) -> list[str]:
    """``czas`` values (as served) of a line on the 'friday' or 'saturday' set."""
    return [kv(r)["czas"] for r in day_sets()[day].timetables[(stop, line)]]


def instants(czas_values: list[str], service_date: date) -> list[datetime]:
    """Wall-clock Warsaw instants of ``HH:MM:SS`` values, 24:xx and 28:xx rolling into the next date."""
    out = []
    for czas in czas_values:
        hours, minutes, _ = (int(x) for x in czas.split(":"))
        day = service_date + timedelta(days=hours // 24)
        wall = datetime(day.year, day.month, day.day, hours % 24, minutes, tzinfo=WARSAW)
        if wall.astimezone(UTC).astimezone(WARSAW).replace(tzinfo=None) != wall.replace(tzinfo=None):
            continue  # a label inside the hour the clock skips is no moment at all
        out.append(wall)
    return sorted(out)


def reference_next(czas_values: list[str], service_date: date, now: datetime) -> datetime | None:
    """The oracle: first listed departure strictly after ``now`` within ONE service day's schedule."""
    later = [t for t in instants(czas_values, service_date) if t > now]
    return later[0] if later else None


def local(dt: datetime | None) -> str | None:
    """A moment as 'YYYY-MM-DD HH:MM' Warsaw wall-clock, or None for None."""
    return dt.astimezone(WARSAW).strftime("%Y-%m-%d %H:%M") if dt else None


def log_blob(caplog) -> str:
    """Everything that was logged, as one string: messages, formatted args and rendered tracebacks."""
    formatter = logging.Formatter()
    parts = []
    for record in caplog.records:
        parts.append(record.getMessage())
        if record.exc_info:
            parts.append(formatter.formatException(record.exc_info))
        if record.exc_text:
            parts.append(record.exc_text)
        if record.stack_info:
            parts.append(record.stack_info)
    return "\n".join(parts)


def dumps(obj) -> str:
    """``obj`` as JSON text; values JSON cannot represent are written with ``str()``, so it never raises on them."""
    return json.dumps(obj, default=str, ensure_ascii=False)


def subentry_of(device, entry_id: str) -> str:
    """The subentry a device belongs to (Home Assistant 2026.10 has ``config_subentry_id``; the older ones a mapping)."""
    if hasattr(device, "config_subentry_id"):
        return device.config_subentry_id
    (subentry_id,) = device.config_entries_subentries[entry_id]
    return subentry_id
