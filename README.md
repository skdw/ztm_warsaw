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

Shows **when the next bus, tram or train leaves your stop**: one sensor for a line at a stop pole, for your dashboard and for automations such as "tell me when to leave". It reads the City of Warsaw's open data and needs no extra hardware.

It shows **scheduled** departures: no delays or disruption alerts, no day other than today's service day, and no journey planning (use [wtp.waw.pl](https://wtp.waw.pl) for that). The vehicle of the next departure can be shown on the map (optional, token required).

---

## 🔧 Features

- ✅ Buses, trams, metro and urban rail (SKM), including night, express and local lines.
- ✅ The next departure is the state of the sensor; the three after it, and the first and the last departure of the day, are attributes.
- ✅ A *Status* sensor says in plain words what is going on ("The last departure of the day has gone").
- ✅ Setup by searching for the stop's name, then picking the pole and the line: no numbers to look up.
- ✅ Several lines and stops, an optional walking time, an optional calendar and an optional pin for the vehicle on the map.
- ✅ Eight languages: English, Polish, Ukrainian, Russian, German, Spanish, French and Italian. The six newer ones are machine-translated; corrections are welcome as pull requests.

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

Get a free token at [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api): enter a nickname, accept the terms and download it. It is a long text in three parts separated by dots.

An old API key (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, from [api.um.warszawa.pl](https://api.um.warszawa.pl)) still works, but that server stops answering at times, the City has given no end date and the vehicle on the map needs a token. To switch, open the notice in **Repairs**, or choose **Configure** on the line, and paste the token. Your settings stay.

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
3. Paste your token and type a part of the stop's name (for example `Marcelin`) or its ID.
4. Pick the pole (its number is on the stop sign, one per direction) and the line. Only lines that stop there today are listed.

The sensor is named like `sensor.line_151_from_7009_01`. Add another stop of the line with **Add stop**. If you already know the numbers, tick **I know the numbers** on the first screen. The walking time, the calendar, the vehicle pin and removing a line are in the [wiki](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration).

---

## 🩺 Troubleshooting

- **The sensor is `unknown` and says "No service".** The line does not run today, or its last departure has gone. That is expected. The *Status* sensor says which; the timetable is at [wtp.waw.pl](https://wtp.waw.pl), or call 19115.
- **The sensor is `unavailable`.** The City did not return a valid timetable: a rejected token, or a stop, pole or line it does not know. The Home Assistant log has the reason (keys and tokens are never logged).
- **Network errors, and you use an old key.** The City's old server stops answering at times. The sensors keep the timetable they have and ask again later; switching to a token fixes it.
- **Home Assistant asks for a new key.** The City rejected the key three times in a row. Enter a new key or token in the form; your settings stay.
- **Reporting a problem.** Choose *Download diagnostics* on the entry and attach the file to your issue. The key or token is replaced with `**REDACTED**`.

More answers are in the [wiki](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting).

---

## 📚 Documentation

The [wiki](https://github.com/solarssk/ztm_warsaw/wiki) is the user manual: [Configuration](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration) (walking time, removing a line), [Concepts](https://github.com/solarssk/ztm_warsaw/wiki/2.-Concepts) (the service day, what each entity shows), [Examples](https://github.com/solarssk/ztm_warsaw/wiki/3.-Examples) (cards and automations to copy) and [Troubleshooting](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting). It is in English; the source is in [`docs/wiki/`](docs/wiki).

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
