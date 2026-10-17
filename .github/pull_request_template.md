## Description

<!--
Cover two things, as separate paragraphs:
1. What problem this solves, in plain language. Skip only for pure internal
   maintenance (dependency bump, CI tweak) with no user-facing effect, and say
   so explicitly instead.
2. What changed in the code, grouped by area if it touches more than one.
   Describe the diff as shipped, not the original plan.
-->

## How to test

<!--
Concrete verification steps: the commands you ran (for example ruff, mypy, pytest) and,
for behavior changes, what you checked in a real Home Assistant. If something
was not run, say so plainly and why.
-->

## What stays / known limitations

<!--
Anything intentionally left out, deferred, or still transitional. State here
whether entity IDs, unique IDs, config entry data, attributes and sensor state
meanings are unchanged. If one changes, link the migration plan.
-->

## Documentation impact

<!--
Select exactly one. "Docs updated" means README.md, CHANGELOG.md, SECURITY.md,
CONTRIBUTING.md, AGENTS.md or docs/ changed in this PR. A test-only, CI-only or
code-only change with no user-visible effect is the case for "No doc update
needed", with a real reason after the colon.
-->

- [ ] Docs updated
- [ ] No doc update needed: <state the reason>

---

## Checklist

- [ ] No API keys, tokens or passwords in the diff, fixtures or logs
- [ ] Fixtures and tests use synthetic keys only (for example `00000000-0000-0000-0000-000000000000`)
- [ ] Lint, type check and tests that exist for the code I touched pass locally (`ruff check .`, `mypy custom_components/ztm_warsaw`, `pytest`)
- [ ] Domain, config entry keys, unique IDs, device identifiers and attribute names are unchanged, or a migration is included
- [ ] `CHANGELOG.md` has an entry under `[Unreleased]` for any user-visible change
