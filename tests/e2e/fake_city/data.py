"""Payloads served by the fake City of Warsaw server.

Captured real responses are loaded from ``data/`` (see ``data/README.md`` for provenance); the
rest is generated deterministically. Nothing here talks to the network.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# Dataset ids of the legacy ``dbtimetable_get`` endpoint (same ids the integration hard-codes).
LEGACY_TIMETABLE_ID = "e923fa0e-d96c-43f9-ae6e-60518c9f3238"
LEGACY_LINES_ID = "88cd555f-6f31-43ca-9de4-66c479ad5942"
LEGACY_STOPS_ID = "ab75c33d-3a26-4342-b36a-6e5fef0a3ac3"

# Actions of the NEW dane.um.warszawa.pl API (measured on 2026-10-18, see data/README.md).
NEW_ACTION_TIMETABLE = "get_ztm_odjazdy_linii_z_przystanku"
NEW_ACTION_LINES = "get_ztm_lista_linii_na_przystanku"
NEW_ACTION_STOPS = "get_ztm_przystanki_komunikacji_miejskiej"

PARAM_ERROR_TEXT = "Błędna metoda lub parametry wywołania"
BAD_KEY_PAYLOAD = {"result": "false", "error": "Błędny apikey lub jego brak"}
# The new host's answer to EVERY rejected request, HTTP 500 (measured 2026-10-18): a missing or bad token, an unknown
# stop or line, a missing or non-string parameter. Nothing in it says which.
SERVICE_UNAVAILABLE_PAYLOAD = {"message": "Service unavailable"}

StopKey = tuple[str, str]  # ("7009", "01")
Row = list[dict]  # [{"key": "czas", "value": "23:24:00"}, ...] in the API's key order


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def czas_of(row: Row) -> str:
    return next(e["value"] for e in row if e["key"] == "czas")


def make_row(czas: str, kierunek: str, trasa: str, brygada: str) -> Row:
    # Key order as captured from the live API.
    return [
        {"key": "symbol_2", "value": None},
        {"key": "symbol_1", "value": None},
        {"key": "brygada", "value": brygada},
        {"key": "kierunek", "value": kierunek},
        {"key": "trasa", "value": trasa},
        {"key": "czas", "value": czas},
    ]


def _hms_to_min(hms: str) -> int:
    h, m, _ = hms.split(":")
    return int(h) * 60 + int(m)


def _min_to_hms(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def synthesize_rows(stop: StopKey, line: str, n: int, first: str, last: str) -> list[Row]:
    """SYNTHESIZED: ``n`` departures spread evenly from ``first`` to ``last`` (both exact)."""
    rng = random.Random(f"{stop[0]}/{stop[1]}/{line}/{n}/{first}/{last}")
    a, b = _hms_to_min(first), _hms_to_min(last)
    minutes = [a] if n <= 1 else [round(a + (b - a) * i / (n - 1)) for i in range(n)]
    minutes[0], minutes[-1] = a, b
    directions = [f"Synthetic {line} A", f"Synthetic {line} B"]
    rows = [
        make_row(_min_to_hms(m), directions[i % 2], f"TS-{line}", f"{rng.randint(1, 40):02d}")
        for i, m in enumerate(minutes)
    ]
    rng.shuffle(rows)  # the real API does not return rows sorted
    return rows


@dataclass
class DaySet:
    """Everything the API serves during one service day."""

    name: str
    # lines running on this service day, per stop pole (order = API order)
    lines: dict[StopKey, list[str]] = field(default_factory=dict)
    # (stop, line) -> rows; a pair absent here (but known to the other day) answers null
    timetables: dict[tuple[StopKey, str], list[Row]] = field(default_factory=dict)
    # provenance per (stop, line): "captured" | "synthesized"
    provenance: dict[tuple[StopKey, str], str] = field(default_factory=dict)


def _split_key(key: str) -> StopKey:
    stop_id, nr = key.split("/")
    return stop_id, nr


@lru_cache(maxsize=1)
def day_sets() -> dict[str, DaySet]:
    """``{"friday": DaySet, "saturday": DaySet}`` built from captures + summaries."""
    captured = {
        "friday": {
            (("7009", "01"), "151"): _load("fri_7009_01_151.json")["result"],
            (("7009", "01"), "523"): _load("fri_7009_01_523.json")["result"],
            (("7009", "01"), "N25"): _load("fri_7009_01_N25.json")["result"],
            (("7009", "01"), "411"): _load("fri_7009_01_411.json")["result"],
        },
        "saturday": {
            (("7009", "01"), "151"): _load("sat_7009_01_151.json")["result"],
            (("7009", "01"), "523"): _load("sat_7009_01_523.json")["result"],
            # N25 is identical on both days (hash-compared over the whole night of measurements)
            (("7009", "01"), "N25"): _load("fri_7009_01_N25.json")["result"],
        },
    }
    summaries = {"friday": _load("summary_friday.json"), "saturday": _load("summary_saturday.json")}
    out: dict[str, DaySet] = {}
    for name, summary in summaries.items():
        ds = DaySet(name=name)
        for key, info in summary.items():
            stop = _split_key(key)
            ds.lines[stop] = list(info["lines"])
            for line, t in info["tt"].items():
                pair = (stop, line)
                if pair in captured[name]:
                    ds.timetables[pair] = captured[name][pair]
                    ds.provenance[pair] = "captured"
                else:
                    ds.timetables[pair] = synthesize_rows(stop, line, t["n"], t["first"], t["last"])
                    ds.provenance[pair] = "synthesized"
        out[name] = ds
    _add_survey(out["saturday"])
    return out


def _add_survey(ds: DaySet) -> None:
    """Real shapes of the whole network (``survey_2026-10-18.json``, the timetable of a Sunday) as weekend lines."""
    for key, times in _load("survey_2026-10-18.json")["timetables"].items():
        line, pole = key.split("@")
        stop = _split_key(pole)
        rows = [make_row(czas, f"Survey {line}", f"TR-{line}", f"{i % 40 + 1:02d}") for i, czas in enumerate(times)]
        ds.timetables[(stop, line)] = rows
        ds.provenance[(stop, line)] = "captured"
        if line not in ds.lines.setdefault(stop, []):
            ds.lines[stop].append(line)


def all_known_pairs() -> set[tuple[StopKey, str]]:
    sets = day_sets()
    return {pair for ds in sets.values() for pair in ds.timetables}


def all_known_stops() -> set[StopKey]:
    sets = day_sets()
    return {stop for ds in sets.values() for stop in ds.lines}


# --------------------------------------------------------------------------------------
# Stops catalogue (dataset ab75c33d-...): realistic shape and size, SYNTHETIC content.
# --------------------------------------------------------------------------------------
SMALL_CATALOGUE = 40_000  # bytes; enough for the 7 real stop poles + filler, fast
FULL_CATALOGUE = 1_645_692  # bytes measured on the live dataset (6 986 records, 82% of 2 MB)
FULL_NEW_CATALOGUE = 1_584_188  # bytes measured on the new host on 2026-10-18 (6 789 records, 79% of 2 MB)
OVER_CAP_CATALOGUE = 2_150_000  # bigger than the integration's 2 MB response cap

_SYLLABLES = [
    "Ko",
    "wal",
    "ska",
    "Mi",
    "ło",
    "sna",
    "Pra",
    "ga",
    "Zie",
    "le",
    "nia",
    "Woj",
    "ci",
    "ech",
    "Ba",
    "rtyc",
    "ka",
]
_DIRECTIONS = ["Centrum", "Metro Testowe", "Pętla Testowa", "Rondo Syntetyczne", "al.Wymyślona", "Dw.Fikcyjny"]


def _stop_record(
    stop_id: str, nr: str, name: str, street: str, lat: str, lon: str, direction: str, *, legacy: bool = True
) -> dict:
    values = [
        {"value": stop_id, "key": "zespol"},
        {"value": nr, "key": "slupek"},
        {"value": name, "key": "nazwa_zespolu"},
        {"value": street, "key": "id_ulicy"},
        {"value": lat, "key": "szer_geo"},
        {"value": lon, "key": "dlug_geo"},
    ]
    if legacy:  # the new host's records stop after the six keys above (measured on all 6 789 records)
        values += [
            {"value": direction, "key": "kierunek"},
            {"value": "2026-10-10 00:00:00.0", "key": "obowiazuje_od"},
        ]
    return {"values": values}


def stop_name_for(stop_id: str) -> str:
    """The synthetic (diacritics included) name the fake catalogue gives a core stop."""
    return f"Testowa Łąka {stop_id}"


@lru_cache(maxsize=8)
def stops_catalogue_bytes(
    target_bytes: int = SMALL_CATALOGUE, *, ensure_ascii: bool = False, new_host: bool = False
) -> bytes:
    """The serialized catalogue, of at least ``target_bytes`` bytes (deterministic).

    Legacy host: ``{"result": [...]}`` with eight keys per record. New host (measured 2026-10-18): a BARE list of
    records with six keys, in compact JSON.
    """
    rng = random.Random(20261017)
    core_ids = {s for s, _ in all_known_stops()}
    used = set(all_known_stops())
    core = [
        _stop_record(
            sid,
            nr,
            stop_name_for(sid),
            str(2000 + int(sid) % 997),
            f"52.{rng.randint(100000, 299999)}",
            f"21.{rng.randint(10000, 199999)}",
            rng.choice(_DIRECTIONS),
            legacy=not new_host,
        )
        for sid, nr in sorted(all_known_stops())
    ]

    def new_filler() -> dict:
        while True:
            sid = str(rng.randint(1000, 9999))
            nr = f"{rng.randint(1, 8):02d}"
            if (sid, nr) not in used and sid not in core_ids:
                used.add((sid, nr))
                break
        name = "Testowa " + "".join(rng.choice(_SYLLABLES) for _ in range(3)) + f" {sid}"
        return _stop_record(
            sid,
            nr,
            name,
            str(rng.randint(1000, 9999)),
            f"52.{rng.randint(100000, 299999)}",
            f"21.{rng.randint(10000, 199999)}",
            rng.choice(_DIRECTIONS),
            legacy=not new_host,
        )

    def dump(obj) -> str:
        if new_host:
            return json.dumps(obj, ensure_ascii=ensure_ascii, separators=(",", ":"))
        return json.dumps(obj, ensure_ascii=ensure_ascii)

    def serialize(records: list[dict]) -> bytes:
        return dump(records if new_host else {"result": records}).encode("utf-8")

    def size(records: list[dict]) -> int:
        return len(serialize(records))

    filler: list[dict] = []
    per_record = len(dump(new_filler())) + 2
    # Pad in batches sized from the measured gap; two or three passes converge.
    while True:
        records = filler[: len(filler) // 2] + core + filler[len(filler) // 2 :]  # core stops mid-list
        gap = target_bytes - size(records)
        if gap <= 0:
            break
        filler.extend(new_filler() for _ in range(max(1, gap // per_record)))
    return serialize(records)
