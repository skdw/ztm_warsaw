"""Shape checks for City of Warsaw API payloads.

One definition, two users: the e2e suite runs these against the FAKE city (so the fake cannot drift
from what we believe the API looks like) and the optional live test runs the very same checks against
the REAL API (so a belief that stopped being true is noticed). Pure functions, no I/O, no pytest.
"""

from __future__ import annotations

import re
from typing import Any

CZAS_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})$")
LEGACY_KEY_RE = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.IGNORECASE)
TIMETABLE_KEYS = {"symbol_2", "symbol_1", "brygada", "kierunek", "trasa", "czas"}
# The six keys of a stop record that the integration reads; both hosts have them. The legacy catalogue also
# has "kierunek" and "obowiazuje_od"; the new one has neither (measured 2026-10-18, all 6 789 records).
STOP_KEYS = {"zespol", "slupek", "nazwa_zespolu", "id_ulicy", "szer_geo", "dlug_geo"}
LEGACY_ONLY_STOP_KEYS = {"kierunek", "obowiazuje_od"}
SERVICE_UNAVAILABLE = {"message": "Service unavailable"}  # the new host's answer to EVERY rejected request (HTTP 500)
MAX_SERVICE_HOUR = 29  # measured: night lines reach 28:58; the 24:xx day lines stop at 24:38
RESPONSE_CAP_BYTES = 2_000_000  # the integration's own limit


def is_legacy_key(key: str) -> bool:
    return bool(LEGACY_KEY_RE.match(key.strip()))


def classify_legacy(payload: Any) -> str:
    """What a legacy ``{"result": ...}`` body means, as measured against the live API (see fake_city/data/README.md)."""
    if not isinstance(payload, dict) or "result" not in payload:
        return "unknown_shape"
    result = payload["result"]
    if result == "false":
        return "bad_key" if "apikey" in str(payload.get("error", "")).lower() else "error"
    if result is None:
        return "null"  # line exists but does not run today
    if isinstance(result, str):
        return "param_error"
    if isinstance(result, list):
        return "rows" if result else "empty"
    return "unknown_shape"


def classify_new(status: int, payload: Any) -> str:
    """What a response of the new host means, as measured on 2026-10-18 (see fake_city/data/README.md).

    The point of the measurement: "failure" covers a rejected token, an unknown stop or line, a missing or
    non-string parameter and (as far as is known) a real outage alike, so a client cannot tell them apart.
    """
    if status == 200:
        if payload is None:
            return "null"  # the line exists but does not run today
        if isinstance(payload, list):
            return "rows" if payload else "empty"
        return "unknown_shape"
    if status == 500 and payload == SERVICE_UNAVAILABLE:
        return "failure"
    if status == 404:
        return "not_found"
    if status == 405:
        return "method_not_allowed"
    return "unknown_shape"


def unwrap(payload: Any) -> list:
    """Rows of either envelope (legacy ``{"result": [...]}`` or the new bare list)."""
    if isinstance(payload, list):
        return payload
    assert isinstance(payload, dict) and isinstance(payload.get("result"), list), f"no rows in {str(payload)[:120]}"
    return payload["result"]


def kv(row: Any) -> dict[str, Any]:
    """``[{key, value}, ...]`` (departure) or ``{"values": [...]}`` (line, stop) as a dict."""
    items = row["values"] if isinstance(row, dict) else row
    return {item["key"]: item["value"] for item in items}


def czas_to_minutes(czas: str) -> int:
    m = CZAS_RE.match(czas)
    assert m, f"czas {czas!r} is not HH:MM:SS"
    hours, minutes, seconds = (int(x) for x in m.groups())
    assert minutes < 60 and seconds < 60, czas
    assert hours < MAX_SERVICE_HOUR, f"czas {czas!r} beyond the {MAX_SERVICE_HOUR}h service-day window"
    return hours * 60 + minutes


def assert_timetable_rows(payload: Any) -> list[dict[str, Any]]:
    """Departures: a list of rows, every row a list of ``{key, value}`` with the six known keys."""
    rows = unwrap(payload)
    out = []
    for row in rows:
        assert isinstance(row, list), f"row is {type(row).__name__}"
        for item in row:
            assert set(item) == {"key", "value"}, item
        fields = kv(row)
        assert set(fields) == TIMETABLE_KEYS, f"unexpected keys {sorted(fields)}"
        czas_to_minutes(fields["czas"])
        out.append(fields)
    return out


def assert_lines_rows(payload: Any) -> list[str]:
    """Lines at a stop: ``[{"values": [{"key": "linia", "value": "151"}]}]``."""
    lines = []
    for row in unwrap(payload):
        assert isinstance(row, dict) and "values" in row, row
        fields = kv(row)
        assert set(fields) == {"linia"}, sorted(fields)
        assert isinstance(fields["linia"], str) and fields["linia"], fields
        lines.append(fields["linia"])
    return lines


def assert_stops_rows(payload: Any) -> int:
    """The stops catalogue: every record carries the six keys the integration reads; returns the record count."""
    rows = unwrap(payload)
    for row in rows[:50] + rows[-50:]:  # the live dataset has ~7000 records: spot-check head and tail
        fields = kv(row)
        assert set(fields) >= STOP_KEYS, f"missing {sorted(STOP_KEYS - set(fields))}"
    return len(rows)
