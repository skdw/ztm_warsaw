"""Builds ``custom_components/ztm_warsaw/line_stops.json``: for every line, the stops it serves.

The City of Warsaw's open data has the stops and the lines at a stop pole, but no list of the stops of a line. The setup
wants to start from the line, so this script asks the City for the lines at every pole once (about 7 000 requests, a minute
at five at a time) and turns the answers around. The result (about 75 KB) ships with the integration; run this script again
at each release, because the City changes its lines a few times a year.

    ZTM_LIVE_API_KEY=<token> python scripts/build_line_index.py

The token is read from the environment, sent only to the City's host and never printed or written.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://dane.um.warszawa.pl/api/action/"
STOPS = "get_ztm_przystanki_komunikacji_miejskiej"
LINES_AT = "get_ztm_lista_linii_na_przystanku"
TARGET = Path(__file__).resolve().parent.parent / "custom_components" / "ztm_warsaw" / "line_stops.json"
WORKERS = 5  # the City answered about 100 requests a second at this rate without a single refusal
ATTEMPTS = 3


class Inconclusive(Exception):
    """The City could not be asked or did not answer in a readable way: not the same as "there is nothing"."""


def call(token: str, action: str, body: dict[str, str] | None = None) -> list[dict[str, list[dict[str, str]]]] | None:
    """One request to the City's new host: the answer's list, or None when the City refuses (an HTTP 500 is also what a pole
    without public lines gets, and is a conclusive answer). ``Inconclusive`` after ``ATTEMPTS`` tries when it cannot be reached or
    answers with something else. Nothing of the request, the token included, is reported."""
    request = Request(API + action, data=json.dumps(body or {}).encode(), method="POST")
    request.add_header("Authorization", token)
    request.add_header("Content-Type", "application/json")
    for attempt in range(ATTEMPTS):
        try:
            with urlopen(request, timeout=40) as response:
                answer = json.loads(response.read())
            if isinstance(answer, list):
                return answer
        except HTTPError as error:
            if error.code == 500:
                return None
        except (URLError, TimeoutError, ValueError):
            pass
        time.sleep(1 + attempt)
    raise Inconclusive


def values_of(row: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    """A record of the City ``{"values": [{"key", "value"}, ...]}`` as a plain dictionary."""
    return {item["key"]: item["value"] for item in row.get("values", [])}


def poles_of(token: str) -> list[tuple[str, str]]:
    """Every ``(stop ID, pole number)`` of the City's catalogue (SystemExit when it cannot be read: nothing can be built)."""
    try:
        rows = call(token, STOPS)
    except Inconclusive:
        rows = None
    if not rows:
        raise SystemExit("The City's list of stops could not be read (is the token valid?).")
    found = [values_of(row) for row in rows]
    return sorted({(v["zespol"], v["slupek"]) for v in found if "zespol" in v and "slupek" in v})


def invert(lines_at_pole: dict[tuple[str, str], list[str]]) -> dict[str, list[str]]:
    """``{line: sorted stop IDs}`` from ``{(stop ID, pole): lines}``: a stop is listed once however many poles the line serves there."""
    stops: dict[str, set[str]] = defaultdict(set)
    for (stop_id, _pole), lines in lines_at_pole.items():
        for line in lines:
            stops[line].add(stop_id)
    return {line: sorted(ids, key=int) for line, ids in sorted(stops.items())}


def render(lines: dict[str, list[str]], today: date) -> str:
    """The text of the data file: compact, sorted, with the day it was built."""
    return json.dumps({"generated": today.isoformat(), "lines": lines}, ensure_ascii=False, separators=(",", ":")) + "\n"


def lines_at(token: str, pole: tuple[str, str]) -> list[str]:
    """The lines that stop at one pole today (empty when the City says there are none; ``Inconclusive`` when it did not answer)."""
    rows = call(token, LINES_AT, {"busstopId": pole[0], "busstopNr": pole[1]}) or []
    return [v["linia"] for v in (values_of(row) for row in rows) if "linia" in v]


def build(token: str, poles: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    """Ask the City for the lines at every pole and turn the answers around. ``Inconclusive`` when any pole could not be answered:
    an index with a hole in it is worse than the old one."""
    poles = list(poles)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        answers = list(pool.map(lambda pole: lines_at(token, pole), poles))
    return invert(dict(zip(poles, answers, strict=True)))


def main() -> int:
    """Read the token from ``ZTM_LIVE_API_KEY``, build the index and write the data file."""
    token = os.environ.get("ZTM_LIVE_API_KEY", "").strip()
    if not token:
        print("Set ZTM_LIVE_API_KEY to a token of dane.um.warszawa.pl.", file=sys.stderr)
        return 2
    poles = poles_of(token)
    print(f"{len(poles)} poles; asking for their lines...")
    try:
        lines = build(token, poles)
    except Inconclusive:
        print("The City did not answer for some poles: not writing the file. Run the script again.", file=sys.stderr)
        return 1
    if len(lines) < 100:  # the network has about 330 lines: far fewer means the City did not answer
        print(f"Only {len(lines)} lines came back: not writing the file.", file=sys.stderr)
        return 1
    TARGET.write_text(render(lines, date.today()), encoding="utf-8")
    print(f"{len(lines)} lines written to {TARGET.relative_to(TARGET.parents[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
