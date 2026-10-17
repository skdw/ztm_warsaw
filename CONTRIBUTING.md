# Contributing to ztm_warsaw

Thanks for your interest in contributing. This document covers the practical steps for proposing a
change. The rules the checks enforce, and the list of identifiers that must not change, are in
[AGENTS.md](AGENTS.md).

## Before you start

- For anything beyond a small fix, start a discussion or open an issue first, so we agree on the
  approach before you spend time on it.
- Search the existing issues and discussions first; someone may already be on it.
- Found a security vulnerability? Do **not** open a public issue. Follow [SECURITY.md](SECURITY.md).

## Ways to contribute

| Type | Where to start |
|---|---|
| Bug report | Use the [issue form](https://github.com/solarssk/ztm_warsaw/issues/new?template=bug.yml) ("Bug report / feature request") with Type: Bug. Say which Home Assistant and integration versions you run and what you expected. Remove your API key from every log and screenshot first. |
| Question or help with setup | Ask in [Discussions](https://github.com/solarssk/ztm_warsaw/discussions), for example how to find a stop ID or a pole number, or why a sensor shows "No service". |
| Feature request | Start a [Discussion](https://github.com/solarssk/ztm_warsaw/discussions) describing the goal and what "done" looks like, or, for a small and well-defined one, use the same issue form with Type: Feature request. |
| Code change | Branch, then open a pull request (see below). |
| Documentation | The user guide is [README.md](README.md). Release notes are written in [CHANGELOG.md](CHANGELOG.md). How the tests are organised is in [tests/README.md](tests/README.md). |

## Development setup

You need Python 3.13.2 or newer. The tests run a real Home Assistant, whose release and minimum Python are
pinned by `pytest-homeassistant-custom-component` in `requirements_test.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements_test.txt
```

The integration itself must stay valid for Home Assistant 2024.4 and Python 3.12, even though CI
runs newer versions.

## Running the checks

CI runs these on every pull request; run them before you open one.

```bash
ruff check .
mypy custom_components/ztm_warsaw
pytest
```

- `pytest` takes about ten seconds. It runs the integration inside a real Home Assistant against a
  fake City of Warsaw server on your own machine, so it needs no network and no API key. Add
  `--cov` for a coverage report.
- `mypy` reports a few known errors. CI compares them exactly with `.github/mypy-baseline.txt`: a
  new error fails the job, and so does a baseline entry that no longer occurs. The command that
  regenerates the entries after you fix or deliberately accept one is in the comment above the
  `mypy` step of `.github/workflows/ci.yml`.
- A test against the real API exists (`tests/live/`) but is opt-in. It makes a handful of requests,
  never prints the key, and never runs in CI:

  ```bash
  ZTM_LIVE_API_KEY=<your key> pytest -m live tests/live
  ```

- CI also runs hassfest and the HACS validation, a dependency audit of the pinned tooling,
  gitleaks, and actionlint and zizmor on the workflow files. One repository check is cheap to run
  yourself: `python scripts/release_check.py` (the `manifest.json` version has notes in
  `CHANGELOG.md`). The Documentation impact declaration is checked only in CI, against the
  description of your pull request (see below).

## Making a change

1. Branch from `main` with a prefix and a short slug:

   | Prefix | Use for |
   |---|---|
   | `feature/<slug>` | New functionality |
   | `fix/<slug>` | Bug fixes |
   | `chore/<slug>` | Maintenance, dependencies, tooling |
   | `docs/<slug>` | Documentation only |
   | `ci/<slug>` | Workflows and CI configuration |
   | `test/<slug>` | Tests only |
   | `release/vX.Y.Z` | A release commit |

2. Write Conventional Commit messages and pull request titles: `feat:`, `fix:`, `docs:`, `chore:`,
   `test:`, `ci(scope):`, and `release: vX.Y.Z` for a release commit.

3. **Changes to what the integration does come with tests.** A bug fix adds a test that fails
   without the fix, or, if the bug is already pinned by a `@known_bug(...)` test in `tests/e2e/`,
   removes that mark (strict mode turns a fix that forgets to red). A new feature is not done
   without a test of its behaviour. Documentation, CI and test-only changes need none.

4. Do not change an entity ID, a `unique_id`, a device identifier, an attribute name or a config
   entry key without a migration: see "The public contract is frozen" in [AGENTS.md](AGENTS.md).

5. Match the style of the file you are editing, and keep the diff to what the change needs.

## Using AI coding tools

AI-assisted contributions are welcome. The same bar applies as to any other contribution: you are
responsible for what you submit, not the tool that helped write it.

- Read and understand every line before you submit it.
- Run it: build, type-check and run the real test suite. "Looks correct" is not a result.
- Keep the diff scoped to the issue; do not let an agent "improve" adjacent code.
- Do not invent: no made-up APIs, no confident claims about behaviour you have not checked.

## Opening a pull request

Use the repository's [pull request template](.github/pull_request_template.md) and keep its
headings. Fill in "Documentation impact": a check compares your declaration with the files you
changed, and the pull request cannot merge while they disagree.

`main` is protected. A pull request needs these checks to pass, and its branch to be up to date
with `main` (use the "Update branch" button). The repository administrator can bypass the rule, so
that a broken CI can still be repaired; by habit, nothing is pushed to `main` directly.

The required checks:

- `Lint (ruff)`
- `Type check (mypy)`
- `Tests (pytest)`
- `Hassfest`
- `Dependency audit (pip-audit)`
- `Secret scan (gitleaks)`
- `Lint workflows (actionlint, zizmor)`
- `Release bookkeeping`
- `Documentation impact declaration`

`HACS validation` is not required to merge, because it depends on the network, but it must pass
before a release. The Codecov, SonarCloud and Scorecard results are signals, not gates.

This is a single-maintainer project. [@solarssk](https://github.com/solarssk) reviews and merges
every pull request, including their own, once the required checks are green, and sets the `type:`
label, the milestone of the release it lands in and the assignee. Automated reviewers (Codex, and
CodeRabbit on request) may comment on your pull request; their findings are input, not verdicts.

## Releases and maintenance

- A release is a version in `manifest.json`, its notes in `CHANGELOG.md`, and a tag; the procedure
  is in the header of [`.github/workflows/release.yml`](.github/workflows/release.yml). The
  workflow prepares a draft GitHub Release, and publishing it by hand is what makes HACS offer it.
- Once a month, run `gh workflow list --all` and check that no workflow shows as
  `disabled_inactivity`. GitHub disables a workflow that has a `schedule:` trigger after 60 days
  without repository activity, and a disabled workflow stops running on pull requests too; this is
  what happened to the old HACS and hassfest workflows. `ci.yml` has no `schedule:` for that reason,
  so today only `scorecard.yml` (and CodeQL's weekly run) can be hit.
- At every minor release, look at the triggers in [AGENTS.md](AGENTS.md) that would call for a
  review of the repository's tier.

## Questions

Open a [discussion](https://github.com/solarssk/ztm_warsaw/discussions), or reach [@solarssk](https://github.com/solarssk).
