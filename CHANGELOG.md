# Changelog

Notable changes to this integration, grouped under `### Added`, `### Changed`, `### Fixed` and `### Removed` ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/)).

Each entry is one line that starts with a verb and links to the pull request with the details. This file is the source of the GitHub Release notes, and a published Release is what makes HACS offer an update. A beta (`X.Y.ZbN`) takes its notes from `[Unreleased]`.

A version that needs something from users starts with an `### Adopter action` list. Omit it when nothing is required.

Releases before 1.1.4 are described on the [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases) page.

## [Unreleased]

Upgrading from 1.1.4: update through HACS and restart Home Assistant. This is a beta: please report what you see in the [issues](https://github.com/solarssk/ztm_warsaw/issues).

### Adopter action

- Replace an old API key by a token in **Configure** on each entry; the old key still works, but its end has no date, and a notice in Repairs says so ([#69](https://github.com/solarssk/ztm_warsaw/pull/69))
- Expect extra attributes if you listed fewer than three departures: every sensor now lists `Next 1` to `Next 3` ([#69](https://github.com/solarssk/ztm_warsaw/pull/69))
- Remove one of two entries for the same stop, pole and line, as the notice in Repairs asks; the later one never had a sensor ([#65](https://github.com/solarssk/ztm_warsaw/pull/65))

### Added

- Support the City's new API with a token, and send each key only to its own host ([#56](https://github.com/solarssk/ztm_warsaw/pull/56), [#57](https://github.com/solarssk/ztm_warsaw/pull/57))
- Add a Polish translation of the setup screen ([#57](https://github.com/solarssk/ztm_warsaw/pull/57))
- Send a `User-Agent` with the integration's name, version and repository, and nothing about you ([#56](https://github.com/solarssk/ztm_warsaw/pull/56))
- Ask for a new key when the old API rejects the key three times in a row ([#64](https://github.com/solarssk/ztm_warsaw/pull/64))
- Add Download diagnostics, with the key or token redacted ([#66](https://github.com/solarssk/ztm_warsaw/pull/66))
- Change the key or token of an entry in Configure, and show a notice for entries that use an old key ([#69](https://github.com/solarssk/ztm_warsaw/pull/69))
- Publish the stop's position as `latitude` and `longitude`, so it shows as a pin on the map card ([#69](https://github.com/solarssk/ztm_warsaw/pull/69))
- Add a calendar entity per sensor with every departure as an event, off by default ([#70](https://github.com/solarssk/ztm_warsaw/pull/70))

### Changed

- Stop asking for the number of departures: every sensor lists the next departure and `Next 1` to `Next 3` ([#69](https://github.com/solarssk/ztm_warsaw/pull/69))
- Publish the user manual as the project wiki from `docs/wiki/`, and add the project badges and a code of conduct ([#68](https://github.com/solarssk/ztm_warsaw/pull/68))
- Rewrite the README: scheduled data, two kinds of key, what each state means ([#61](https://github.com/solarssk/ztm_warsaw/pull/61))
- Give each entry its own device on Home Assistant 2026.10 and newer, where a device belongs to one entry ([#65](https://github.com/solarssk/ztm_warsaw/pull/65))

### Fixed

- Compute departures from the City's service day, so times after midnight and the night tail stay right ([#62](https://github.com/solarssk/ztm_warsaw/pull/62))
- Retry the setup when the City does not answer, with a 30 s deadline, instead of waiting an hour ([#63](https://github.com/solarssk/ztm_warsaw/pull/63))
- Show a rejected key, an unknown stop or an unreadable answer as `unavailable`, not as "No service" ([#55](https://github.com/solarssk/ztm_warsaw/pull/55))
- Download the stops catalogue once for all entries, and accept it growing past 2 MB ([#67](https://github.com/solarssk/ztm_warsaw/pull/67))
- Refuse a second entry for the same stop, pole and line, and show a notice for existing pairs ([#65](https://github.com/solarssk/ztm_warsaw/pull/65))
- Stop reloading an entry when it is renamed ([#64](https://github.com/solarssk/ztm_warsaw/pull/64))
- Stop following redirects on requests that carry the key, and keep the key out of the log ([#56](https://github.com/solarssk/ztm_warsaw/pull/56))
- Strip pasted spaces from the setup fields, and refuse a key that is neither a UUID nor a token ([#57](https://github.com/solarssk/ztm_warsaw/pull/57))
- Use the sensor's client in the setup screen, so it says "line not found" instead of a raw error ([#57](https://github.com/solarssk/ztm_warsaw/pull/57))
- Write the sensor's state when it becomes unavailable or available again ([#55](https://github.com/solarssk/ztm_warsaw/pull/55))
- Remove `aiohttp` from `requirements`, which Home Assistant provides ([#39](https://github.com/solarssk/ztm_warsaw/pull/39))
- Use `asyncio.timeout`, so the integration loads on Home Assistant 2026.10 ([#50](https://github.com/solarssk/ztm_warsaw/pull/50))

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
