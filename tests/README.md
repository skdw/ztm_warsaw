# Tests

    python -m pip install -r requirements_test.txt
    python -m pytest tests            # everything except `live` (about 10 s)
    python -m pytest tests -n 2       # optional, pytest-xdist works; the gain is small at this size
    python -m pytest tests/e2e -k e2e_06 -q

## Layout

| Path | What |
|---|---|
| `e2e/` | The real integration inside a real in-process Home Assistant, talking real HTTP to a fake City of Warsaw on 127.0.0.1. One file per theme; scenarios are numbered `E2E-NN` and each has one to several `test_e2e_NN_*` tests (the number in a file name, `test_e2e_04_lifecycle.py`, is the file's index, not a scenario). |
| `e2e/fake_city/` | The fake: legacy GET contract, new POST contract, failure modes, request counting, a service day that flips at 03:00 on the frozen clock. `data/README.md` says what is captured and what is synthesized. |
| `e2e/test_harness.py` | Tests of the fake and of the routing seam. If one is red, do not trust a red scenario. |
| `contract_shapes.py` | Pure shape checks shared by the fake's self-tests and the live test. |
| `live/` | Optional. Same shape checks against the real API. Needs `ZTM_LIVE_API_KEY` and `-m live`; the live tests never run in CI (`test_key_redaction.py` there needs no key and does). |

## How the e2e suite works

* No production file is modified. `fake_city/routing.py` rewrites only the origin (scheme/host/port) of
  `api.um.warszawa.pl` and `dane.um.warszawa.pl` inside `aiohttp.ClientSession._request`; every connection (also the
  target of a redirect) is checked in `TCPConnector._resolve_host`, and only the fake city's two loopback ports are
  allowed, anything else fails the test. Two things do reach into production modules from the tests: the `sleeps`
  fixture replaces `asyncio` in the client and config-flow modules (to record and skip the back-off), and a few
  white-box tests patch `ZTMStopClient.get`.
* Time is simulated: `env.run_to("2026-10-17 02:31")` jumps from timer to timer and fires each at its own instant.
  `@pytest.mark.start(...)` sets where the clock starts (before Home Assistant is created).
* `env.hourly_tick()` fires one hourly refresh; with `hanging=True`, and `env.drive_timeouts(task)`, it lets the frozen clock run past the client timeout for the cases where the fake never answers.

## Known bugs are tests

A test that states the CORRECT behaviour of a confirmed bug carries
`@known_bug("<short-slug>", "<why>")`, i.e. `xfail(strict=True, raises=AssertionError)` (two tests widen `raises` to
also accept `UnknownStep` or `ImportError`). When the bug is fixed the test XPASSes, strict mode turns that red, and the
fix PR removes the mark. A failure of the harness itself is a `HarnessError`, not an `AssertionError`, so it stays red.
Keep the preconditions of a known-bug test out of the xfail where you can: an assertion that fails *before* the bug
assertion also counts as 'the bug is still there'. Tests that pin today's behaviour (for example that an entry loads
after a failed first refresh) are characterisations and are expected to change in the pull request that fixes it.
