# AGENTS.md

This file is for AI coding agents, and for anyone who wants the rules of this repository as a
checklist. If you are looking for what the integration does, read [README.md](README.md); how to
propose a change, run the checks and open a pull request is in
[CONTRIBUTING.md](CONTRIBUTING.md). This file assumes both and goes straight to the rules.

## What this repository is

`ztm_warsaw` is a Home Assistant custom integration, installed through HACS, that shows the next
departures of one Warsaw public-transport line at one stop pole as a sensor. It reads the City of
Warsaw open-data API. The integration is in `custom_components/ztm_warsaw/`, its tests in `tests/`,
the repository tooling in `scripts/` and `.github/`. There is one maintainer
([@solarssk](https://github.com/solarssk)).

## Repository standard

This repository follows the solarssk engineering standard: https://github.com/solarssk/playbook
Tier: 2 (see playbook/docs/tiers.md)

It is Tier 2, not Tier 1, because people other than the maintainer depend on it: it is in the
default HACS list and runs in their Home Assistant with their own API key, and a regression
silently changes their automations. Tier 3 is not claimed. It is earned by operating at flagship
scale, not picked.

### When to review the tier

Check this list at every minor release. A trigger means "review the tier", not "promote":

| Trigger | What to do |
|---|---|
| 500 or more installations in the Home Assistant analytics (opt-in, so a lower bound) | Review. Promote at 1,000 or more for three months in a row |
| A second maintainer with write access | Require reviews and revisit CONTRIBUTING.md |
| Another repository or integration depends on this one's entities, attributes or workflows | Review |
| The integration handles more sensitive data, takes actions (buying tickets, controlling devices) or stores additional credentials | Review |
| A third party asks for an audit or a security review | Review |
| Two or more user-visible regressions in a quarter that the end-to-end tests should have caught | Review |

A promotion would mean turning the Codecov and SonarCloud signals into required checks
(`sonar.qualitygate.wait=true`) and earning the OpenSSF Best Practices badge. DAST and auditor
documentation do not apply to an integration without a running service. The wiki is the user manual and a
build output of `docs/wiki/` (see the map below); a Tier 3 formal docs site is not claimed.

### Accepted `verify-tier` warnings

Two warnings of the playbook's `verify-tier` are accepted, not overlooked:

- `sast`: CodeQL runs as GitHub's default setup (in the repository's security settings, CodeQL
  analysis), which has no workflow file for a file scan to find.
- `readme-opens-well`: it needs a human. The README will be rewritten together with the API
  migration planned for 1.2.0 (#29, #30).

## Rules for changes

### The public contract is frozen

Automations and dashboards depend on these, and the tests
`test_e2e_02_golden_public_contract` and `test_e2e_02_golden_attributes_when_there_is_no_service`
(in `tests/e2e/test_e2e_01_install.py`) pin them:

- `migration.py` converts the entries of 1.1.x into lines at startup (before any entry is set up); every change of the contract below needs a step there, a test in `tests/e2e/test_e2e_08_migration.py` and an `### Adopter action`;
- the domain `ztm_warsaw`, the config entry version, and the config entry data keys: a version 1 entry (1.1.x, one stop)
  has `api_key`, `busstop_id`, `busstop_nr`, `line` and `departures`; a version 2 entry is a line with `api_key`, `line` and
  `departures` (no longer asked: a new entry stores 3, an old value is ignored, the key stays so that the shape does not
  change) and every stop is a subentry of type `stop` with `busstop_id` and `busstop_nr` and the unique ID `<id>_<nr>`;
- the entity `unique_id` `line_<LINE>_from_<STOP>_<POLE>` and the entity ID
  `sensor.line_<line in lower case>_from_<STOP>_<POLE>`, and the diagnostic sensor's `_last_update`
  suffix; the calendar's unique_id suffix `_calendar` and entity ID `calendar.line_<line in lower case>_from_<STOP>_<POLE>_timetable`;
- the device: an entry of 1.1.x (version 1, one stop) has the line's device with the identifier `("ztm_warsaw", "line_<LINE>")` (on Home Assistant 2026.10 and newer a device belongs to one config entry, so the same line at two poles has one device per entry there, with the same identifier; `test_e2e_25_two_entries_of_one_line_share_one_device_where_home_assistant_allows_it` pins both); every stop of a line entry (version 2) has a device of its own with the identifier `("ztm_warsaw", "line_<LINE>_<id>_<nr>")`, because a device belongs to one subentry;
- the names of the state attributes (for example `Line, Number`, `Stop, ID`,
  `Next 1, Departure Time`) and the shape of the "no service" state.

Changing any of them (a rename, a removal, a new meaning) needs a migration, an `### Adopter action` entry in
`CHANGELOG.md`, and a deliberate edit of the golden tests in the same pull request. Adding to them does not: a new
attribute that only a configured stop has, or an optional key with a default in a stop's subentry (`walking_time`, absent
meaning none), changes nothing an existing installation has, so it needs a test and a `CHANGELOG.md` line, not a migration. The `unique_id` format has already
changed once without a migration; do not repeat that.

### Compatibility and dependencies

- The integration must stay valid for Home Assistant 2026.1 and Python 3.13 (`hacs.json`, the ruff
  `target-version`). CI runs newer: the Home Assistant release and the Python version that
  `pytest-homeassistant-custom-component` in `requirements_test.txt` pins. Do not use an API that
  Home Assistant 2026.1 lacks without checking.
  The minimum moves once a year: it is the first release of the current year (2026.1 now), raised in
  January's first minor release together with `hacs.json`, `.github/compat/`, the docs and an
  `### Adopter action` entry. Home Assistant itself calls a Core older than 24 months unsupported, so the
  minimum is never older than that.
  The job `Compat smoke (minimum Home Assistant)` runs the whole suite on 2026.1 and Python 3.13 (pin in
  `.github/compat/`); it is not required to merge, but a release needs it.
- `manifest.json` has `"requirements": []` on purpose: Home Assistant provides aiohttp, and hassfest
  rejects it as a requirement. Do not add a runtime requirement without discussing it first.

### Docstrings

- Every module, class, function and method of `custom_components/`, `scripts/` and `tests/` has a docstring, private and
  nested ones too (`test_*` functions and dunder methods other than `__init__` are the only exceptions). It says what the thing
  is **for** and what it promises, not what its name already says: the project is picked up again after months, by its one
  maintainer or by someone (or an agent) who has none of the context, and the code is what has to remember why.
  `scripts/check_docstrings.py` (also run by pytest) fails when one is missing; whether it is any good is for the review.

### Secrets

- An API key, token or password never goes into a commit, a fixture, a log line, an exception
  message or an issue. Tests use clearly synthetic keys. The real-API check in `tests/live/` reads
  its key from `ZTM_LIVE_API_KEY`, redacts it in failure output, and does not run in CI (only
  `test_key_redaction.py` there, which needs no key, does).
- gitleaks scans every pull request. See [SECURITY.md](SECURITY.md) for the controls that run.

### Tests

- A change to what the integration does comes with a test that fails without the change. A
  documentation-only, CI-only or test-only change does not need one.
- A confirmed bug is a test: `@known_bug("<slug>", "<why>")` in `tests/e2e/` is a strict xfail that
  states the correct behaviour. The pull request that fixes the bug removes the mark; strict mode
  turns a fix that lands without it red. Keep preconditions out of the xfail: an assertion that
  fails before the bug assertion also counts as "the bug is still there".
- The harness reports its own failures as `HarnessError`, which is not an `AssertionError`, so it
  can never pass as a known bug.
- No test in the default run touches the network. `pytest-socket` blocks it, and the test seam in
  `tests/e2e/fake_city/routing.py` allows only the fake city's loopback ports. What is known about
  the real API, and what is only a placeholder, is written in `tests/e2e/fake_city/data/README.md`.
- Coverage is a signal, not a gate. Do not write tests to move a number.

### Pull requests

- Branch from `main`: `feature/`, `fix/`, `chore/`, `docs/`, `ci/`, `test/` or `release/vX.Y.Z`
  plus a short slug. Titles use Conventional Commit prefixes (`feat:`, `fix:`, `docs:`, `chore:`,
  `test:`, `ci(scope):`, `release: vX.Y.Z`).
- Use the pull request template, including the Documentation impact section: CI checks it against
  the diff.
- Labels `type: bug`, `type: chore`, `type: docs` or `type: feature` (plus `security` where it
  applies), the milestone of the release it lands in, and the assignee are set when the pull
  request is created.
- `main` is protected: a pull request and the required checks listed in CONTRIBUTING.md, with the
  branch up to date. Never push to `main`, and agents do not merge: the maintainer does.
- Codex usually reviews pull requests (and again on `@codex review`); CodeRabbit reviews only on request
  (`@coderabbitai review`, automatic reviews are off in `.coderabbit.yaml`). Verify each finding
  against the code before acting on it, and answer it with the commit that fixed it or with why it
  is not a defect.

## Review guidelines

For automated reviewers. Treat these as the highest priority:

- An API key or token that can reach a log line, an exception message, a fixture or a workflow.
- An API error that is shown as an empty timetable or "No service" instead of as a failure
  (fail-open handling).
- A change to an identifier or attribute name listed above without a migration.
- A test that can pass for the wrong reason: an assertion before the bug assertion inside an xfail,
  a loop over nothing, a harness error that is also an `AssertionError`.
- Network access from a test, or an `allow` that widens the test seam.
- A workflow that gains permissions, runs untrusted input through `${{ }}` in a `run:` block, or
  uses an action that is not pinned to a commit SHA.
- A user-visible change without a `CHANGELOG.md` entry, or an entry written for developers. The changelog is the release
  notes of a Home Assistant integration, so it is for the people who use it: one line with a bold title and one short,
  friendly sentence about what the user gets (not how it was built, no pull request numbers).
  `tests/test_changelog_style.py` checks the newest section.

Do not suggest Tier 3 tooling, widening the ruff rule set outside a change that fixes what it
finds, or style changes that ruff does not enforce.

## Releasing

The header of `.github/workflows/release.yml` is the procedure: set the version in
`manifest.json`, move the notes under their heading in `CHANGELOG.md`, merge, tag the merge commit,
and publish the draft Release that the workflow prepares. A version that needs something from
users has an `### Adopter action` list at the top of its `CHANGELOG.md` section.

## Map of this repository

| Path | Purpose |
|---|---|
| `custom_components/ztm_warsaw/` | The integration; `entity.py` has what every entity of a stop shares (the device, the stop's record, the base class) |
| `tests/e2e/` | The real integration in a real in-process Home Assistant against a fake City of Warsaw ([tests/README.md](tests/README.md)) |
| `tests/live/` | An opt-in check of the real API (not run in CI); `test_key_redaction.py` there needs no key and runs in every pytest run |
| `scripts/` | `check_mypy_baseline.py`, `release_check.py`, `release_preflight.py` and `check_pr_docs_impact.py`, tested under `tests/` |
| `.github/workflows/` | `ci.yml`, `docs-impact.yml`, `publish-wiki.yml`, `release.yml`, `scorecard.yml`, `verify-standard.yml` (the playbook's `verify-tier`, report only). A job's `name:` is its status-check name: branch protection and `REQUIRED` in `scripts/release_preflight.py` list the jobs by it |
| `custom_components/ztm_warsaw/vehicles.py`, `vehicle_sensor.py`, `geo_location.py` | The shared feed of the City's vehicle positions (one poll per token), the optional `Vehicle distance` sensor of a stop, and the map layer: one `geo_location` pin per stop pole (hosted by one of the lines that stop there) and one per vehicle of a line that shows its vehicles |
| `custom_components/ztm_warsaw/runtime.py` | The typed `runtime_data` of a loaded entry (`StopRuntime`, `LineRuntime`) and `ZtmConfigEntry`, the config entry with it |
| `custom_components/ztm_warsaw/quality_scale.yaml` | Where the integration stands on Home Assistant's Integration Quality Scale, rule by rule (`done`, `exempt` with the reason, `todo`); change a status in the pull request that changes the code. `tests/test_quality_scale.py` checks every rule is there |
| `scripts/check_docstrings.py` | Fails when a module, class or function has no docstring (also run by pytest; see Docstrings above) |
| `docs/wiki/` | The source of the GitHub Wiki: edit the pages here, never in the wiki's web interface. `publish-wiki.yml` copies them on a push to `main`; `scripts/check_wiki_docs.py` (also run by pytest) checks that every page exists and every link resolves |
| `CHANGELOG.md` | The source of the GitHub Release notes |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to run the checks and open a pull request |
| [SECURITY.md](SECURITY.md) | How to report a vulnerability, and the controls that run |
