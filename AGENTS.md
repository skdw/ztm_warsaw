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
(`sonar.qualitygate.wait=true`) and earning the OpenSSF Best Practices badge. DAST, a wiki and
auditor documentation do not apply to an integration without a running service.

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

- the domain `ztm_warsaw`, the config entry version, and the config entry data keys `api_key`,
  `busstop_id`, `busstop_nr`, `line` and `departures`;
- the entity `unique_id` `line_<LINE>_from_<STOP>_<POLE>` and the entity ID
  `sensor.line_<line in lower case>_from_<STOP>_<POLE>`, and the diagnostic sensor's `_last_update`
  suffix;
- one device per line, with the identifier `("ztm_warsaw", "line_<LINE>")`;
- the names of the state attributes (for example `Line, Number`, `Stop, ID`,
  `Next 1, Departure Time`) and the shape of the "no service" state.

Changing any of them needs a migration, an `### Adopter action` entry in `CHANGELOG.md`, and a
deliberate edit of the golden tests in the same pull request. The `unique_id` format has already
changed once without a migration; do not repeat that.

### Compatibility and dependencies

- The integration must stay valid for Home Assistant 2024.4 and Python 3.12 (`hacs.json`, the ruff
  `target-version`). CI runs newer: the Home Assistant release and the Python version that
  `pytest-homeassistant-custom-component` in `requirements_test.txt` pins. Do not use an API that
  Home Assistant 2024.4 lacks without checking.
- `manifest.json` has `"requirements": []` on purpose: Home Assistant provides aiohttp, and hassfest
  rejects it as a requirement. Do not add a runtime requirement without discussing it first.

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
- A user-visible change without a `CHANGELOG.md` entry.

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
| `custom_components/ztm_warsaw/` | The integration |
| `tests/e2e/` | The real integration in a real in-process Home Assistant against a fake City of Warsaw ([tests/README.md](tests/README.md)) |
| `tests/live/` | An opt-in check of the real API (not run in CI); `test_key_redaction.py` there needs no key and runs in every pytest run |
| `scripts/` | `check_mypy_baseline.py`, `release_check.py`, `release_preflight.py` and `check_pr_docs_impact.py`, tested under `tests/` |
| `.github/workflows/` | `ci.yml`, `docs-impact.yml`, `release.yml`, `scorecard.yml`. A job's `name:` is its status-check name: branch protection and `REQUIRED` in `scripts/release_preflight.py` list the jobs by it |
| `CHANGELOG.md` | The source of the GitHub Release notes |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to run the checks and open a pull request |
| [SECURITY.md](SECURITY.md) | How to report a vulnerability, and the controls that run |
