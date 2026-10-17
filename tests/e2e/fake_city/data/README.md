# Fixture provenance

Every file here is either a **captured** response of the legacy City of Warsaw API
(`api.um.warszawa.pl`, no API key inside) or a **summary** derived from captures.
Anything the fake server invents on top of these is **synthesized** and labelled in
`fake_city/data.py`.

| File | Kind | Captured | What it is |
|---|---|---|---|
| `fri_7009_01_151.json` | captured | Fri 2026-10-16 23:50 +02:00 | Timetable, stop 7009/01, line 151, 81 rows (`result` envelope) |
| `fri_7009_01_523.json` | captured | Fri 2026-10-16 23:50 | Line 523, 139 rows, first 04:50 |
| `fri_7009_01_N25.json` | captured | Fri 2026-10-16 23:50 | Night line N25, 12 rows `23:24 ... 28:54` (identical on Sat) |
| `fri_7009_01_411.json` | captured | Fri 2026-10-16 00:50 | Line 411, 34 rows; **not running on Saturday** (`{"result":null}`) |
| `fri_lines_7009_01.json` | captured | Fri 2026-10-16 | Lines-at-stop for 7009/01 (13 lines) |
| `sat_7009_01_151.json` | captured | Sat 2026-10-17 03:00 +02:00 | Line 151, 53 rows (Saturday set) |
| `sat_7009_01_523.json` | captured | Sat 2026-10-17 03:00 | Line 523, 101 rows, first **05:15** (Friday: 04:50) |
| `summary_friday.json` | captured (summary) | Sat 2026-10-17 00:50 (still the Friday set) | 7 stops, 67 stop/line pairs: line list + `{n, first, last}` per timetable |
| `summary_saturday.json` | captured (summary) | Sat 2026-10-17 05:31 | same pairs on the Saturday set |
| `error_param_text.json` | captured | 2026-10-17 | `{"result":"Błędna metoda lub parametry wywołania"}` |

Facts the fake server reproduces (all measured on 2026-10-16/17):

* the service day flips between 02:55:51 and 03:00:51 Warsaw time, not at midnight;
* night lines carry hours up to 28:xx, some day lines carry 24:xx (max seen 24:38);
* a line that exists but does not run today answers `200 {"result":null}`;
* unknown stop/line/missing parameters answer `200 {"result":"Błędna metoda lub parametry wywołania"}`;
* a bad key answers `200 {"result":"false","error":"Błędny apikey lub jego brak"}`.

Rows for stop/line pairs that were only captured as a summary (everything except the
six timetable captures above) are **synthesized** from `{n, first, last}`: `n` times spread evenly
from `first` to `last`, deterministic order, so a day line like 520 still ends at `24:38`.
Only Friday 2026-10-16 and Saturday 2026-10-17 were captured: Monday-Friday are served from the
Friday set and Saturday/Sunday from the Saturday set (an approximation, not a measurement).

Stop names, street ids and coordinates in the stops catalogue are **synthetic** (generated,
deterministic, clearly labelled "Testowa ..."); only the record shape
(`zespol, slupek, nazwa_zespolu, id_ulicy, szer_geo, dlug_geo, kierunek, obowiazuje_od`) and the
size (~1.65 MB, 82% of the integration's 2 MB cap) are real; the live dataset has 6 986 records, the fake reaches the same
byte size with fewer, longer ones.

The new-host (`dane.um.warszawa.pl`) behaviour is **not captured at all**; it follows the city's own
example files (POST, raw `Authorization: <JWT>`, bare list) plus one observation (bogus token ->
HTTP 500 `{"message":"Service unavailable"}`). Every other new-host behaviour in the fake is a
placeholder and flagged `UNVERIFIED` in `server.py`.

## Licence of the captured data

The timetable rows are public data of the City of Warsaw (ZTM), obtained through its own API, which the
city's open-data portal (https://dane.um.warszawa.pl/) offered under CC BY terms with personal keys and no SLA when
these files were captured (October 2026). Attribution: data of the City of Warsaw / ZTM Warszawa. No API key,
token or account identifier appears in any file here.
