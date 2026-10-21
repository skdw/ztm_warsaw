# Changelog

What changed, written for the people who use the integration. Entries are grouped under `### Added`, `### Changed`, `### Fixed` and `### Removed` ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/)), and each is a bold title with one short, friendly sentence: what you can do now, not how it was built. The details are in the pull requests.

This file is the source of the GitHub Release notes, and a published Release is what makes HACS offer an update. A beta (`X.Y.ZbN`) takes its notes from `[Unreleased]`. A version that needs something from you starts with an `### Adopter action` list.

Releases before 1.1.4 are described on the [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases) page.

## [Unreleased]

Upgrading from 1.1.4: update through HACS and restart Home Assistant. Nothing has to be set up again.

### Adopter action

- **Your stops are grouped by line**: each line becomes one entry with its stops under it, and your sensors keep their names, IDs and settings. An automation or card that points at the old *device* needs choosing again, and there is no way back to 1.1.4, so take a backup first.
- **Home Assistant 2026.1 or newer**: this version needs it, and HACS will not offer the update on an older one, so you stay on 1.1.4 until you upgrade Home Assistant.
- **Switch to a token**: your old API key still works, but the City has set no end date. Get a token at [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) and paste it in the notice in Repairs or in **Configure** on each entry.
- **More departures on every sensor**: each sensor now lists the next departure and the three after it, so the "number of departures" choice is gone.
- **Two entries for the same stop and line?** The second one never had a sensor, so remove it when Repairs tells you.

### Added

- **Works with the City's new API**: log in with a token from the new portal, and each key goes only to the right server.
- **Change your key any time**: **Configure** on an entry swaps the key or token, so there is nothing to remove and add again.
- **A calendar of departures** (off by default): switch it on in the entity settings to see the whole day in Home Assistant's calendar, or start an automation "8 minutes before the bus".
- **The stop on the map**: the sensor has `latitude` and `longitude`, so it shows as a pin on the map card.
- **A badge with the line number**: on the map card the pin shows the line instead of odd initials like "L1M", in the colours of ZTM's own signs: ordinary lines light with a purple ring, fast ones red, night ones blue, trams light yellow. The same badge replaces the bus or tram icon in your cards.
- **Download diagnostics**: one click gives you a file for bug reports, with your key hidden.
- **Paste the token in the notice itself**: the notice in Repairs about an old key has a *Submit* step where you paste a token, so you do not have to look for **Configure**.
- **A walking time for every stop**: set how many minutes it takes you to walk to a stop (*Reconfigure* on the stop), and its sensor skips the departures you could not catch any more.
- **Next departures as their own entities** (off by default): switch on *Next 1*, *Next 2* or *Next 3* in the entity settings to get each following departure as a time you can use in a card or an automation.
- **Its own logo in Home Assistant**: the integration carries its icon and logo, so Home Assistant 2026.3 and newer shows them without fetching anything.
- **Delete a stop's old device**: when a stop is gone from a line, its leftover device now has a *Delete* button on its page, while a device that is still in use cannot be deleted by mistake.
- **Proper icons**: Next 1 to 3, Last update and the calendar have icons of their own (numbers, an update arrow, a calendar with a clock) instead of Home Assistant's default eye.
- **Error messages in your language**: when the City does not answer, is updating its timetables or refuses a request, the message in the Home Assistant log and in the entry's state is in your language too.
- **A status in words**: every stop has a *Status* sensor that says what is going on (running, the last departure has gone, no service today, timetables are being updated, the timetable could not be fetched ...) in your language, so "unknown" after the last bus is no longer a puzzle.
- **One token for all your lines**: the notice about an old key can reuse the token you already entered for another line, and pasting a token there can give it to every line that still has an old key, so you do not paste it once per line.
- **Reconfigure the key from Home Assistant's own menu**: *Reconfigure* on a line replaces its API key or token, like *Configure* does, and an old key is nudged to a token.
- **Lines say which stops they have**: a line is titled like "Line 176 · Marcelin 01, Marcelin 02", so the list of lines (for example when you add a stop) shows which is which. A title you chose yourself stays.
- **When the first and the last bus is**: every sensor has `Timetable, First Departure` and `Timetable, Last Departure` for the day, so a card can still say "the last bus left at 23:41" when the state is *unknown* after the last departure, after a restart or for a sensor added late.
- **Releases you can check**: each release has the integration as a zip with a signature, so you can verify that what you download is what was built here. The steps are in SECURITY.md.
- **A nudge when your key stops working**: if the old API keeps rejecting it, Home Assistant asks for a new one instead of quietly failing.
- **Polish setup screen**: the setup is now also in Polish.
- **More languages**: setup, notices and dialogs now also in Ukrainian, Russian, German, Spanish, French and Italian, and the README in all eight languages, with a language switch at the top. The new languages are machine-translated, so corrections are welcome.
- **A real manual**: the wiki is rewritten and published from the repository, so it stays up to date.

### Changed

- **Clearer instructions in every language**: the README and setup messages now explain configuration, API keys and errors more naturally across all eight languages.

- **A shorter setup**: one question less when you add a sensor, and pasted spaces are cleaned up for you.
- **Proper credits**: the sensor names the City of Warsaw, ZTM and the licence.
- **A clearer README**: it says plainly that these are scheduled departures, not live positions.
- **Configure fits your key**: an entry with an old key is nudged to a token with the steps to get one, while an entry that already has a token is just asked for the new one.
- **Every stop of a line under one entry**: add another stop with **Add stop**, or by adding the line again, and the line stays one entry, with every stop as a device of its own, instead of one entry per stop. Entries you already have are grouped for you.
- **The stop's name where you look for it**: entries are titled "Line 176 from Marcelin 15" (a title you chose yourself stays), and the notices in Repairs name the line and the stop, so nine of them are no longer nine identical rows.

### Fixed

- **Round badges for every line**: the metro, the urban rail and the trams had square or rounded-rectangle badges that Home Assistant cropped into ugly shapes; now all are circles, still told apart by colour.
- **You can ignore the old-key notice**: its window now asks whether to paste a token or keep the old key and ignore the notice, because a notice that can be fixed had no Ignore button; an ignored one stays ignored after a restart.
- **An empty stop ID field**: the stop ID in the setup and in *Add stop* starts empty instead of with 0, and anything that is not a number is refused with a clear message.
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
