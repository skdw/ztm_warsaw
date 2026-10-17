# Changelog

All notable changes to this integration are documented here, grouped under `### Added`, `### Changed`, `### Fixed` and `### Removed`, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This file is the source of the GitHub Release notes. A GitHub Release is also what makes HACS offer an update. Notes for a beta (`X.Y.ZbN`) are taken from `[Unreleased]`.

A version that needs something from users has an `### Adopter action` list at the top of its section, written for someone who has not read the rest of the entry. Omit it when nothing is required.

Releases before 1.1.4 are described on the [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases) page.

## [Unreleased]

### Fixed

- `manifest.json` no longer lists `aiohttp` under `requirements`. Home Assistant provides it and hassfest rejects the entry. Behavior does not change.

## [1.1.4] - 2026-05-19

Upgrading from 1.1.3: update through HACS and restart Home Assistant. No reconfiguration is needed.

### Fixed

- Changing the number of departures in the options no longer crashes the reload.
- Every coordinator called the City of Warsaw API twice on startup; each line now fetches once.
- New entities always get a numeric entity ID such as `sensor.line_28_from_5161_03`, never one derived from the stop name. An existing entity with a name-based ID can be renamed in Settings > Devices & Services.
- The hourly refresh timer is cancelled when the integration is unloaded instead of leaking on every reload.

### Changed

- Connection errors are retried like timeouts; the sensor keeps the last known data during a short outage.
- API responses larger than 2 MB are refused.
- A sensor writes its state only when something changed, and schedules its own update at the next departure time instead of ticking every minute.
