# 🚍 ZTM Warsaw Integration for Home Assistant

[![GitHub release](https://img.shields.io/github/v/release/solarssk/ztm_warsaw)](https://github.com/solarssk/ztm_warsaw/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%F0%9F%A7%A1-blue)](https://www.home-assistant.io)
[![HACS](https://img.shields.io/badge/HACS-Default-blue.svg)](https://hacs.xyz/)
[![CI](https://github.com/solarssk/ztm_warsaw/actions/workflows/ci.yml/badge.svg)](https://github.com/solarssk/ztm_warsaw/actions/workflows/ci.yml)
[![custom_component](https://img.shields.io/badge/type-custom_component-red.svg)](https://github.com/solarssk/ztm_warsaw)

Shows the next **scheduled** departures of one Warsaw public-transport line (bus, tram, metro, rail or night line) at one stop pole as a sensor in Home Assistant, from the City of Warsaw's open data. Use it for dashboards and automations such as "leave in eight minutes" without opening a timetable app.

It shows the **timetable**, not live vehicles. What it does **not** do:

- no live positions, delays or disruptions: the City publishes planned departures, refreshed once a day;
- no timetables for other days: the API serves the current service day only;
- no journey planning: use [wtp.waw.pl](https://wtp.waw.pl) for that.

---

## 🔧 Features

- ✅ Buses, trams, metro, night, cemetery, express and local lines.
- ✅ Several instances: monitor as many stops and lines as you like.
- ✅ The next departure as a timestamp, usable in the UI and in automations; optionally up to 3 more.
- ✅ A clear "No service" state on days when a line does not run, and an `unavailable` state when the City's API fails (see [Troubleshooting](#-troubleshooting)).
- ✅ Set up entirely in the Home Assistant UI, in English or Polish.
- ✅ Attributes with the stop, the direction, a timetable link and notes.

---

## 📸 Screenshots

### Integration Setup
*Add your API key and stop info...*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Entity Display

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Attributes
*Example entity showing departures with attributes like time, direction...*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## ⚙️ Requirements

- Home Assistant 2024.4 or newer
- An API key or token from the City of Warsaw (below)

---

## 🧭 Getting a key or token

The City runs two portals, and the integration accepts the key of either one:

- **New (recommended):** on [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) enter a nick, accept the terms and download your own token. It is a long text in three parts separated by dots.
- **Old:** a key from [api.um.warszawa.pl](https://api.um.warszawa.pl) looks like `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Existing old keys still work when this was written, but the City publishes no date or promise for how long, so move to a token when you can.

The integration recognises which one you pasted and talks only to the matching API. To move an existing entry to a token, **remove the old entry first** and then add the integration again with the token: two entries for the same stop, pole and line cannot coexist, and the second one would silently have no sensor.

---

## 📦 Installation

### With HACS

1. In Home Assistant, go to **HACS → Integrations**.
2. Search for **Warsaw Public Transport**.
3. Click **Download** and confirm.
4. Restart Home Assistant.

### Manually

1. Download the latest version from [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Copy the `ztm_warsaw` folder to `/config/custom_components/`.
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. Go to **Settings → Devices & Services**.
2. Click **+ Add Integration** and search for **Warsaw Public Transport**.
3. Fill in:
   - **API key or token** (see above),
   - **Stop ID** and **stop number** (for example 7009 and 01),
   - **Line number** (for example 151),
   - **Number of departures to show**.

The entity is named after the stop and the line, for example `sensor.line_151_from_7009_01`. You can change the number of upcoming departures at any time in **Settings → Devices & Services → Warsaw Public Transport → Configure**.

**Stop ID and stop number** are not the same thing: the stop ID is shared by all poles of a stop, and the stop number (usually 01, 02, ...) is the number painted on the sign of the pole (*słupek*). A stop with several directions has a different number for each.

---

## 🩺 Troubleshooting

- **The state is empty and the attribute says "No service".** The line does not run today, or its last departure has passed. This is not an error: check [wtp.waw.pl](https://wtp.waw.pl) or call 19115.
- **The sensor is `unavailable`.** The City's API answered, but not with a timetable: the key or token was rejected, the stop, pole and line are not known to the API, or the answer was in a format the integration does not understand. The same happens if the very first load fails. The error is in the Home Assistant log (the key is never logged), and the sensor recovers by itself when the API answers properly again; if it does not, check the key and the stop, pole and line in the settings.
- **The data look stale during an outage.** A timeout, a network error or a server error (HTTP 5xx) after a successful load does **not** make the sensor `unavailable`: it keeps the last timetable it got and tries again every hour, because the timetable is planned data that does not change within a day. The diagnostic sensor **Last update** (disabled by default; enable it in the entity settings) shows when the data were last fetched successfully.
- **Setup says the line was not found.** The API lists only the lines that run today. A line that does not run today (for example a weekday-only line on a Sunday) cannot be added until the day it runs.
- **A line on wtp.waw.pl is missing here.** The journey planner has more data than the public API. That cannot be fixed in the integration.
- **Night lines** (`N01`, `N44` ...): the City counts the whole night as part of the previous service day, so a bus at `24:50` or `26:20` is still in that day's timetable. The integration reads these hours correctly, so a departure at `02:15` (`26:15` in the API) is shown at 02:00 as in 15 minutes.

---

## 🧑‍💻 Contributing and security

Ideas, bug reports and pull requests are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). To report a vulnerability, see [SECURITY.md](SECURITY.md).

---

## 🙌 Data and acknowledgments

Data: the City of Warsaw (**Miasto Stołeczne Warszawa**) and the Warsaw Public Transport Authority (**Zarząd Transportu Miejskiego**, ZTM), via the City's open data portal ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), under the [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/) licence.

This project was fully planned and designed by me — from the concept and expected behavior of the integration, to how it interacts with the City of Warsaw’s public API. While I’m not a professional Python developer, I understand the essentials well enough to define the structure, logic, and features I wanted this integration to offer.

To bring it all to life, I used AI support (ChatGPT), which assisted me mainly with syntax, debugging, and implementation details. However, the overall design, behavior, and workflow were all thoughtfully laid out on my end.

Special thanks to [@peetereczek](https://github.com/peetereczek/ztm), whose previous project inspired me at the beginning. Although this final version was built independently from scratch, his work gave me the initial push to approach things in my own way.

If you’re interested in improving or extending the project — go ahead! Contributions, ideas, and pull requests are always welcome.

---

## 📄 License

MIT License
