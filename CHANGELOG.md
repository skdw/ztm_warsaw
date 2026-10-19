# Changelog

What changed, written for the people who use the integration. Entries are grouped under `### Added`, `### Changed`, `### Fixed` and `### Removed` ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/)), and each is a bold title with one short, friendly sentence: what you can do now, not how it was built. The details are in the pull requests.

This file is the source of the GitHub Release notes, and a published Release is what makes HACS offer an update. A beta (`X.Y.ZbN`) takes its notes from `[Unreleased]`. A version that needs something from you starts with an `### Adopter action` list.

Releases before 1.1.4 are described on the [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases) page.

## [Unreleased]

Upgrading from 1.1.4: update through HACS and restart Home Assistant. Nothing has to be set up again.

### Adopter action

- **Home Assistant 2026.1 or newer**: this version needs it, and HACS will not offer the update on an older one, so you stay on 1.1.4 until you upgrade Home Assistant.
- **Switch to a token**: your old API key still works, but the City has set no end date. Get a token at [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) and paste it in **Configure** on each entry (until then a notice in Repairs reminds you).
- **More departures on every sensor**: each sensor now lists the next departure and the three after it, so the "number of departures" choice is gone.
- **Two entries for the same stop and line?** The second one never had a sensor, so remove it when Repairs tells you.

### Added

- **Works with the City's new API**: log in with a token from the new portal, and each key goes only to the right server.
- **Change your key any time**: **Configure** on an entry swaps the key or token, so there is nothing to remove and add again.
- **A calendar of departures** (off by default): switch it on in the entity settings to see the whole day in Home Assistant's calendar, or start an automation "8 minutes before the bus".
- **The stop on the map**: the sensor has `latitude` and `longitude`, so it shows as a pin on the map card.
- **A badge with the line number**: on the map card the pin shows the line (colour by kind of line) instead of odd initials like "L1M", and the same badge replaces the bus or tram icon in your cards.
- **Download diagnostics**: one click gives you a file for bug reports, with your key hidden.
- **A nudge when your key stops working**: if the old API keeps rejecting it, Home Assistant asks for a new one instead of quietly failing.
- **Polish setup screen**: the setup is now also in Polish.
- **A real manual**: the wiki is rewritten and published from the repository, so it stays up to date.

### Changed

- **A shorter setup**: one question less when you add a sensor, and pasted spaces are cleaned up for you.
- **Proper credits**: the sensor names the City of Warsaw, ZTM and the licence.
- **A clearer README**: it says plainly that these are scheduled departures, not live positions.
- **One device per entry on Home Assistant 2026.10**, which no longer lets entries share a device.

### Fixed

- **Night lines and midnight**: times after midnight follow the City's own timetable day, so no more "No service" gaps or yesterday's times.
- **Errors look like errors**: a rejected key or an unreadable answer shows as `unavailable`, not as a misleading "No service".
- **Slow start-up**: if the City does not answer when Home Assistant starts, the integration tries again instead of waiting an hour.
- **Lighter on the City**: the stop list is downloaded once for all your sensors, not once each.
- **No duplicate entries**: you can no longer add the same stop, pole and line twice.
- **Under the hood**: no reload when you rename an entry, keys are never logged or sent through redirects, and the integration loads on Home Assistant 2026.10.

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
