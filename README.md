# 🚍 ZTM Warsaw Integration for Home Assistant

[![GitHub release](https://img.shields.io/github/v/release/solarssk/ztm_warsaw)](https://github.com/solarssk/ztm_warsaw/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%F0%9F%A7%A1-blue)](https://www.home-assistant.io)

ZTM Warsaw Integration brings real-time public transport departure data from the City of Warsaw API directly into Home Assistant. Whether you're tracking buses, trams, or metro lines, this integration allows you to view live departures at a glance.

> Powered by data from [api.um.warszawa.pl](https://api.um.warszawa.pl) – the official public transport data provider.

---

## 🔧 Features

- ✅ Get real-time departures for buses, trams, metro, night and local lines.
- ✅ Supports multiple instances (multiple stops/lines).
- ✅ Shows current departure in minutes or time (HH:MM).
- ✅ Select how many upcoming departures to display.
- ✅ Recognizes special cases: unavailable schedules, night-only lines, weekend gaps.
- ✅ Fully integrated with Home Assistant UI – easy to set up, no YAML required.

---

## 📸 Screenshots

### Integration Setup

*Add your API key and stop info...*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

---

### Entity Display

*Example entity showing departures with attributes like time, direction...*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/71121bef-8b58-4245-8f07-9366390262d1" /></div>

---

## ⚙️ Requirements

- Home Assistant 2024.4+
- API key from [City of Warsaw](https://api.um.warszawa.pl)

---

## 🧭 How to Get API Key?

1. Go to [https://api.um.warszawa.pl](https://api.um.warszawa.pl)
2. Register or log in
3. Copy your key and paste it into the integration setup

---

## 📦 Installation

1. Manual installation:
   - Download the latest version from GitHub Releases.
   - Copy the `ztm_warsaw` folder to `/config/custom_components/`
   - Restart Home Assistant

2. Install using [HACS](https://hacs.xyz/):
   - Will be available in HACS once the integration is reviewed.

---

## ⚙️ Configuration

Once installed:

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for **Warsaw Public Transport**
4. Fill in:
   - **API key**: You can get it at [https://api.um.warszawa.pl](https://api.um.warszawa.pl)
   - **Stop ID** and **Stop number** (e.g., 7009 / 01)
   - **Line number** (e.g., 151)
   - **Number of departures to show**

The entity name will be generated automatically, e.g., `sensor.line_151_from_7009_01`.

## 🔄 Reconfiguration

You can change the number of upcoming departures at any time by going to Settings → Devices & Services → Warsaw Public Transport → Configure of specific entity.

## 🧾 Notes

This integration depends on the official City of Warsaw public API, which has several known limitations:

- **🧭 Stop ID (busstopId) vs. Stop Pole (busstopNr)**
  These are not the same — both are required for a valid query:
  - `busstopId`: The ID of the stop (shared by all poles at that stop).
  - `busstopNr`: The specific pole number — typically 01, 02, etc.
  It’s the number painted on the physical bus/tram stop sign (słupek).
  If a stop has multiple directions or platforms, each usually has a different pole number.

- **📅 Schedule data availability is limited to the current day only**  
  The API does not provide access to schedules for the upcoming days. This means:
  - If a bus line (e.g., `E-2`) does not operate today (e.g., during weekends), it **won’t appear in the API at all**, even if it normally runs on weekdays. As a result, you won’t be able to add the integration for such a line on a day when it doesn’t operate, because the validation will fail with a `no_departures` error.
  - If you add an entity when the line is active, it will work correctly.  
    On days when the line is inactive, the entity will show a `60+ min` state and the following attribute will appear:
    ```
    note: "No upcoming schedule available. Please verify on wtp.waw.pl or call 19115 for more information."
    ```

- **🔍 Some lines visible on wtp.waw.pl are not available in the API**  
  The official journey planner (wtp.waw.pl) uses internal ZTM/WTP systems, not the public API. If a line exists on the website but not in the integration, that’s due to API limitations — **i cannot fix this**.

- **🌙 Night line schedules can disappear after midnight**  
  Some night buses (e.g., `N31`) may disappear temporarily from the API after their last departure near midnight. Upcoming departures may be restored only later during the night.

**Important Reminder**
These limitations are caused by the official API and are **out of scope of this integration**. I always recommend checking the official journey planner: [wtp.waw.pl](https://wtp.waw.pl)

---

## 🙌 Acknowledgments

Data provided by **Miasto Stołeczne Warszawa** and **Warszawski Transport Publiczny** via [api.um.warszawa.pl](https://api.um.warszawa.pl)

This project was fully planned and designed by me — from the concept and expected behavior of the integration, to how it interacts with the City of Warsaw’s public API. While I’m not a professional Python developer, I understand the essentials well enough to define the structure, logic, and features I wanted this integration to offer.

To bring it all to life, I used AI support (ChatGPT), which assisted me mainly with syntax, debugging, and implementation details. However, the overall design, behavior, and workflow were all thoughtfully laid out on my end.

Special thanks to [@peetereczek](https://github.com/peetereczek/ztm), whose previous project inspired me at the beginning. Although this final version was built independently from scratch, his work gave me the initial push to approach things in my own way.

If you’re interested in improving or extending the project — go ahead! Contributions, ideas, and pull requests are always welcome.

---

## 📄 License

MIT License
