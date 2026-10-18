# Fixture provenance

Every file here is either a **captured** response of the legacy City of Warsaw API
(`api.um.warszawa.pl`, no API key inside), a **summary** derived from captures, or the **log** of one
capture run against the new host (`dane.um.warszawa.pl`, no token inside).
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
| `new_host_2026-10-18.json` | captured (log) | Sun 2026-10-18 01:09 +02:00 | The 18 requests of one run against the new host: request, status, content type, size, the small bodies whole and a description of the large ones |

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

## The new host (`dane.um.warszawa.pl`)

Measured once, on Sunday 2026-10-18 between 01:09 and 01:11 (+02:00), with the maintainer's own token (HS256, claims
`jti` and `iat` only, no `exp`); the token is in no file of this repository. 18 requests, logged in
`new_host_2026-10-18.json`. What the fake reproduces, all measured:

* `POST https://dane.um.warszawa.pl/api/action/<action>` with a raw `Authorization: <JWT>` (a `Bearer ` prefix is
  refused) and a JSON body whose values are **strings** (numbers are refused);
* the actions `get_ztm_lista_linii_na_przystanku`, `get_ztm_odjazdy_linii_z_przystanku` and
  `get_ztm_przystanki_komunikacji_miejskiej` (called without a body);
* answers are **bare lists**, with no `{"result": ...}` envelope, in compact JSON, UTF-8, `Content-Type:
  application/json` without a charset and with no rate-limit headers; the rows are the legacy ones: line 151 at 7009/01
  gave the same 53 rows as the legacy host in the same minute, and the lines at the stop were the same 12;
* a line that exists but does not run on the service day answers `200` with the body `null` (line 411 on a Saturday);
* **every rejected request is the same HTTP 500 `{"message":"Service unavailable"}`** (33 bytes): a missing token, `x.y.z`,
  a token with a wrong signature, the right token with a `Bearer ` prefix, an unknown stop, an unknown line, a missing
  parameter, `{}`, numbers instead of strings. Nothing in the answer says which, so a client cannot tell a rejected
  token from a bad stop from an outage;
* `GET` on an action: `405 {"detail":"Method Not Allowed"}`; an unknown action: `404 {"message":"Resource not found"}`;
* the stops catalogue: 6 789 records, 1 584 188 bytes (79% of the integration's 2 MB cap), every record with exactly
  the six keys `zespol, slupek, nazwa_zespolu, id_ulicy, szer_geo, dlug_geo` (the legacy catalogue also has `kierunek`
  and `obowiazuje_od`; the integration reads only the six);
* latency of the successful answers 30 to 110 ms, the catalogue 1.3 s.

On the night of Saturday to Sunday, lines 151, 411 and 523 at 7009/01 were polled on both hosts every 20 seconds from
02:56 to 03:04 (and at 02:50 and 03:10): **nothing changed on either host**, and the hosts agreed at every poll. That
night therefore says nothing about when the new host flips its service day (the Sunday set equals the Saturday set for
those lines, or the flip is not at 03:00).

Still **unverified**, and marked `UNVERIFIED` in `server.py` where the fake has to pick an answer: rate limits and quotas;
what a revoked or expired token gets; when the service day flips on the new host; behaviour across the DST change of
2026-10-25; the order in which the new host checks action, method and token; a line that exists but is not served at the
stop; a known stop with no line on a service day; a lines or departures request without a body; gzip.

## Licence of the captured data

The timetable rows are public data of the City of Warsaw (ZTM), obtained through its own API, which the
city's open-data portal (https://dane.um.warszawa.pl/) offered under CC BY terms with personal keys and no SLA when
these files were captured (October 2026). Attribution: data of the City of Warsaw / ZTM Warszawa. No API key,
token or account identifier appears in any file here.
