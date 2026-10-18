# Changelog

All notable changes to this integration are documented here, grouped under `### Added`, `### Changed`, `### Fixed` and `### Removed`, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This file is the source of the GitHub Release notes. A GitHub Release is also what makes HACS offer an update. Notes for a beta (`X.Y.ZbN`) are taken from `[Unreleased]`.

A version that needs something from users has an `### Adopter action` list at the top of its section, written for someone who has not read the rest of the entry. Omit it when nothing is required.

Releases before 1.1.4 are described on the [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases) page.

## [Unreleased]

### Added

- The integration can use the new City of Warsaw API (dane.um.warszawa.pl) with a token. A key that looks like the old one (a UUID) is sent only to the old API, any other key only to the new one, and a key never goes to the other host. The setup screen accepts either kind of key.
- A Polish translation of the setup screen.
- Requests to the City of Warsaw API now carry a `User-Agent` with the integration's name, version and repository address, so the operator can see which software asks. It contains nothing about you or your installation.

### Changed

- The README is rewritten: it says that the data are scheduled departures, not live positions, and explains both kinds of key and what each sensor state means. The attribution shown on the sensors now names the City of Warsaw (Miasto Stołeczne Warszawa), the Zarząd Transportu Miejskiego (ZTM) and the licence (CC BY) instead of a host name.

### Fixed

- Requests that carry the API key no longer follow redirects (a redirect is an error now), and a network error is logged by its class only. The API key can no longer reach the log through a redirect loop or an error text.
- The setup screen strips pasted spaces and newlines from every field, and refuses a key that is neither an API key (a UUID) nor a token before anything is sent. A crafted key can no longer add parameters to the request.
- The setup screen uses the same client as the sensor, so it also stops following redirects and keeps the key out of its log. An unknown stop or line is reported as "line not found" (the old message had no text and showed a raw error name).
- A rejected API key, a stop, pole and line that the City of Warsaw API does not know, and an answer the integration does not understand no longer show as "No service". The sensor becomes unavailable, one error is logged (it never contains the API key), and the sensor recovers by itself when the API answers properly again. A line that really does not run today still shows "No service". If a sensor of yours turns unavailable after this update, check the API key and the stop, pole and line in the integration's settings.
- The sensor writes its state when it becomes unavailable or available again, also when the departure it shows has not changed.
- `manifest.json` no longer lists `aiohttp` under `requirements`. Home Assistant provides it and hassfest rejects the entry. Behavior does not change.
- The integration no longer imports `async_timeout`. Home Assistant 2026.10 does not install that package any more, so on an installation where nothing else provides it the integration failed to load with `ModuleNotFoundError: No module named 'async_timeout'`. The request timeout now uses `asyncio.timeout` from the standard library, which every supported Home Assistant version has (Python 3.11 or later). Behavior does not change.

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
