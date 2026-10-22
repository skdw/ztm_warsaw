<h1 align="center">🚍 ZTM Warsaw for Home Assistant</h1>

<p align="center">
  <strong>Warsaw public transport timetables in Home Assistant.<br>Upcoming departures for your dashboards and automations. No YAML required.</strong>
</p>

<p align="center">
  🇬🇧 <strong>English</strong>
  &nbsp;·&nbsp;
  🇵🇱 <a href="README.pl.md">Polski</a>
  &nbsp;·&nbsp;
  🇺🇦 <a href="README.uk.md">Українська</a>
  &nbsp;·&nbsp;
  🇷🇺 <a href="README.ru.md">Русский</a>
  &nbsp;·&nbsp;
  🇩🇪 <a href="README.de.md">Deutsch</a>
  &nbsp;·&nbsp;
  🇪🇸 <a href="README.es.md">Español</a>
  &nbsp;·&nbsp;
  🇫🇷 <a href="README.fr.md">Français</a>
  &nbsp;·&nbsp;
  🇮🇹 <a href="README.it.md">Italiano</a>
</p>

<p align="center">
  <a href="https://github.com/solarssk/ztm_warsaw/actions/workflows/ci.yml"><img src="https://github.com/solarssk/ztm_warsaw/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  &nbsp;
  <a href="https://codecov.io/gh/solarssk/ztm_warsaw"><img src="https://codecov.io/gh/solarssk/ztm_warsaw/graph/badge.svg" alt="Codecov"></a>
  &nbsp;
  <a href="https://sonarcloud.io/summary/new_code?id=solarssk_ztm_warsaw"><img src="https://sonarcloud.io/api/project_badges/measure?project=solarssk_ztm_warsaw&metric=alert_status" alt="Quality Gate Status"></a>
  &nbsp;
  <a href="https://securityscorecards.dev/viewer/?uri=github.com/solarssk/ztm_warsaw"><img src="https://api.securityscorecards.dev/projects/github.com/solarssk/ztm_warsaw/badge" alt="OpenSSF Scorecard"></a>
</p>

<p align="center">
  <a href="https://github.com/solarssk/ztm_warsaw/releases"><img src="https://img.shields.io/github/v/release/solarssk/ztm_warsaw?include_prereleases&label=release&color=066fd1" alt="release"></a>
  &nbsp;
  <a href="https://hacs.xyz/"><img src="https://img.shields.io/badge/HACS-Default-41BDF5" alt="HACS Default"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/Home%20Assistant-2026.1%2B-41BDF5?logo=homeassistant&logoColor=white" alt="Home Assistant 2026.1+">
  &nbsp;
  <a href="LICENSE"><img src="https://img.shields.io/github/license/solarssk/ztm_warsaw" alt="License: MIT"></a>
</p>

<details>
<summary><strong>Table of contents</strong></summary>

- [Features](#-features)
- [Screenshots](#-screenshots)
- [Requirements](#-requirements)
- [Getting a key or token](#-getting-a-key-or-token)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Troubleshooting](#-troubleshooting)
- [Documentation](#-documentation)
- [Contributing and security](#-contributing-and-security)
- [Data and acknowledgments](#-data-and-acknowledgments)
- [License](#-license)

</details>

The integration displays **scheduled departures** using the City of Warsaw’s open data. Each sensor shows departures for one line at a selected stop point. Add them to your Home Assistant dashboard or use them in automations, such as a reminder to leave home before your bus departs.

The data come from published timetables. The integration has these limitations:

- no live vehicle locations, delays or disruption alerts — the API provides scheduled departures, updated once a day;
- timetables are available only for the current service day — the public API does not provide other dates;
- no route or transfer planning — use [wtp.waw.pl](https://wtp.waw.pl) for this.

---

## 🔧 Features

- ✅ Buses, trams, metro and SKM trains, including night, cemetery, express and local services.
- ✅ Support for multiple lines and stops.
- ✅ The next departure time as the sensor’s state, ready to use in dashboards and automations. The following three departures are stored as attributes (`Next 1`–`Next 3`).
- ✅ A “No service” message when there are no departures left, and an `unavailable` state when a valid timetable cannot be obtained (see [Troubleshooting](#-troubleshooting)).
- ✅ Setup in the Home Assistant interface in eight languages: English, Polish, Ukrainian, Russian, German, Spanish, French and Italian. The six new language versions were machine-translated; corrections are welcome as pull requests.
- ✅ Sensor attributes with the stop’s name and coordinates, direction of travel, timetable link and notes. The coordinates let you display the stop on a map.
- ✅ API key or token changes through **Configure**, including when switching to the City’s new API.
- ✅ A separate **calendar** entity for each sensor, disabled by default. Enable it in the entity settings to see each departure of the service day as a one-minute event. A calendar trigger can start an automation, for example eight minutes before departure, without templates.

---

## 📸 Screenshots

### Integration Setup
*The setup form for API credentials, line and stop details.*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Entity Display

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Attributes
*Timetable details, including departure times and direction of travel.*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Requirements

- Home Assistant 2026.1 or newer
- An API key or token from the City of Warsaw (below)

---

## 🧭 Getting a key or token

The integration supports credentials for both City of Warsaw APIs:

- **Token for the new API (recommended):** at [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api), enter a nickname, accept the terms and download your token. It is a long string with three parts separated by dots.
- **Key for the old API:** a key from [api.um.warszawa.pl](https://api.um.warszawa.pl) has the format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. The old API has stopped answering at times, and the City has not announced when it will be switched off. We recommend switching to the new API.

The integration recognises the credential type and sends it only to the matching API. To replace an old key with a token, choose **Configure** for the line and paste the token. Your line and stop settings will be preserved. You do not need to add the integration again: setup will reject a duplicate configuration for the same line and stop point.

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

## 🔌 Configuration

1. Go to **Settings → Devices & services**.
2. Click **+ Add Integration** and search for **Warsaw Public Transport**.
3. Fill in:
   - **API key or token** (see above),
   - **Stop ID** and **stop point number** (for example 7009 and 01),
   - **Line number** (for example 151).

The entity ID includes the line number, stop ID and stop point number, for example `sensor.line_151_from_7009_01`. To change an API key or token, open **Settings → Devices & services → Warsaw Public Transport** and choose **Configure** for the line. Your line and stop settings will be preserved. Configurations that still use an old key show a notice in **Repairs** explaining how to switch to a token. You can ignore the notice.

The **stop ID** is shared by all stop points belonging to the same stop. The **stop point number** identifies a specific boarding location, usually for one direction. It is normally two digits, such as 01 or 02, and appears on the stop sign. In Polish, this numbered stop point is called a *słupek*.

---

## 🩺 Troubleshooting

- **The sensor is `unknown` and its attributes show “No service”.** The line does not run today, or all departures have passed. This is expected behaviour. Check the timetable at [wtp.waw.pl](https://wtp.waw.pl) or call 19115.
- **The sensor is `unavailable`.** The API did not return a valid timetable. Possible causes include a rejected key, incorrect stop, stop point or line details, or an unsupported response format. If the first data fetch fails for a reason other than a rejected key, Home Assistant retries setup automatically. Rejected keys are handled as described below. See the Home Assistant log for details; API keys and tokens are not logged. The sensor becomes available again when it receives valid data. If the problem persists, check the credentials, stop, stop point and line.
- **Home Assistant asks for a new key.** This happens when the old API rejects the key three times in a row. Setup retries also count; a network or server error breaks the sequence. Enter a new API key or token in the form. Your line and stop settings will be preserved, and a valid key will be accepted even if the line does not run today. The sensor remains unavailable until you update the credentials. The new API does not distinguish a rejected token from a service outage. If a timetable has already been downloaded, the sensor uses it until the service day ends, then becomes unavailable. No credential-change form appears automatically. If you revoked the token, enter a new one through **Configure** for the line.
- **Reporting a problem.** Open the line’s configuration, choose *Download diagnostics* and attach the file to your issue. It contains configuration and timetable information. The API key or token is replaced with `**REDACTED**`.
- **Departures are still shown during an API outage.** After a successful download, a timeout, network error or server error (HTTP 5xx) does not immediately make the sensor unavailable. The integration uses the saved timetable until the service day ends and retries every hour. Scheduled departures do not change during the day. The diagnostic sensor **Last update**, available in the entity settings and disabled by default, shows the last successful download time.
- **Setup reports that the line was not found.** The API lists only lines running that day. For example, a weekday-only line cannot be added on a Sunday. Try again on a day when the line has scheduled departures.
- **A line appears on wtp.waw.pl but not in the integration.** The journey planner uses a larger dataset than the public API. The integration can display only data provided by the API.
- **Night-line departure times** (`N01`, `N44`, etc.). A service day can extend past midnight: `24:50` means 00:50 the following day, and `26:20` means 02:20. The integration converts these times correctly. A departure recorded as `26:15` means 02:15 the following day; at 02:00 it appears as a departure in 15 minutes.

---

## 📚 Documentation

The [wiki user manual](https://github.com/solarssk/ztm_warsaw/wiki) covers installation, configuration, timetables, service days and troubleshooting. It is available in English, with source files in [`docs/wiki/`](docs/wiki).

---

## 🧑‍💻 Contributing and security

Ideas, bug reports and pull requests are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). To report a vulnerability, see [SECURITY.md](SECURITY.md).

---

## 🙌 Data and acknowledgments

Data: the City of Warsaw (**Miasto Stołeczne Warszawa**) and the Warsaw Public Transport Authority (**Zarząd Transportu Miejskiego**, ZTM), via the City's open data portal ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), under the [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/) licence.

I developed the integration’s concept, features, structure and approach to the City of Warsaw’s public API. I am not a professional Python developer, but my understanding of the basics allowed me to plan how the project should work.

I used ChatGPT to help with syntax, debugging and implementation details. I made the decisions about the project’s design and behaviour myself.

Thanks to [@peetereczek](https://github.com/peetereczek/ztm), whose earlier project inspired me. This integration was built from scratch as an independent project.

You are welcome to help develop the project by suggesting ideas, reporting bugs or submitting improvements.

---

## 📄 License

MIT License
