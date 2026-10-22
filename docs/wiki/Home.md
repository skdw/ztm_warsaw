# 🚍 Warsaw Public Transport (ztm_warsaw)

A Home Assistant integration that shows when the next bus, tram or train of **one line leaves one stop pole in Warsaw**. It reads the City of Warsaw's open data, so it needs no extra hardware. You get a sensor for your dashboard and for automations such as "tell me when to leave".

| You get | How |
|---|---|
| The next departure and the three after it | a sensor per stop |
| What is going on, in words | a *Status* sensor ("The last departure of the day has gone") |
| The first and the last departure of the day | attributes of the sensor |
| The bus on the map (optional) | a *Vehicle* entity, needs a token |
| The whole day in the calendar (optional) | a calendar entity |

It shows **scheduled** departures. There are no delays or disruption alerts.

## Quick start

1. Install **Warsaw Public Transport** with HACS and restart Home Assistant.
2. Get a free token at [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api).
3. **Settings → Devices & Services → Add Integration → Warsaw Public Transport.**
4. Paste the token, type a part of your stop's name, pick the pole, pick the line. Done.

Details: [Installation](0.-Installation) and [Configuration](1.-Configuration).

## Pages

| Page | What is in it |
|---|---|
| [Installation](0.-Installation) | HACS or manual installation, updating |
| [Configuration](1.-Configuration) | Token, adding a line and stops, walking time, changing the token, removing things |
| [Concepts](2.-Concepts) | Stop ID and pole, the service day, what each entity shows |
| [Examples](3.-Examples) | Dashboard cards, automations and ideas to copy |
| [Troubleshooting](4.-Troubleshooting) | Questions people ask, states, messages, diagnostics |
| [Roadmap](5.-Roadmap) | Where plans and changes are written down |
| [Contributing](6.-Contributing) | Bug reports, pull requests, security reports |

The front page of the project, with screenshots, is the [README](https://github.com/solarssk/ztm_warsaw#readme). This wiki is published from the repository (`docs/wiki/`); edit the files there, not in the wiki's web interface.
