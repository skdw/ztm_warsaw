# Tests

    python -m pip install -r requirements_test.txt
    python -m pytest tests            # everything except `live` (about 10 s)
    python -m pytest tests -n 2       # optional, pytest-xdist works; the gain is small at this size
    python -m pytest tests/e2e -k e2e_06 -q

## Layout

| Path | What |
|---|---|
| `e2e/` | The real integration inside a real in-process Home Assistant, talking real HTTP to a fake City of Warsaw on 127.0.0.1. One file per theme, one `test_e2e_NN_*` per scenario. |
| `e2e/fake_city/` | The fake: legacy GET contract, new POST contract, failure modes, request counting, a service day that flips at 03:00 on the frozen clock. `data/README.md` says what is captured and what is synthesized. |
| `e2e/test_harness.py` | Tests of the fake and of the routing seam. If one is red, do not trust a red scenario. |
| `contract_shapes.py` | Pure shape checks shared by the fake's self-tests and the live test. |
| `live/` | Optional. Same shape checks against the real API. Needs `ZTM_LIVE_API_KEY` and `-m live`; never run in CI. |

## How the e2e suite works

* No production code is patched. `fake_city/routing.py` rewrites only the origin (scheme/host/port) of
  `api.um.warszawa.pl` and `dane.um.warszawa.pl` inside `aiohttp.ClientSession._request`; any other host fails the test.
* Time is simulated: `env.run_to("2026-10-17 02:31")` jumps from timer to timer and fires each at its own instant.
  `@pytest.mark.start(...)` sets where the clock starts (before Home Assistant is created).
* `env.hourly_tick()` / `env.drive_timeouts(task)` exist for the cases where the fake never answers.

## Known bugs are tests

A test that states the CORRECT behaviour of a confirmed bug carries
`@known_bug("<short-slug>", "<why>")`, i.e. `xfail(strict=True, raises=AssertionError)`. When the bug is fixed the test
XPASSes, strict mode turns that red, and the fix PR removes the mark. A harness error (any other exception) stays red.
