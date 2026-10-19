# 🚍 Warsaw Public Transport (ztm_warsaw)

A Home Assistant integration that shows the next **scheduled** departures of one Warsaw public-transport line at one stop pole as a sensor. The data come from the City of Warsaw's open data portal. It is a timetable, not a live view: there are no vehicle positions, delays or disruptions.

This wiki is the user manual. The project's front page, with the features and screenshots, is the [README](https://github.com/solarssk/ztm_warsaw#readme).

## Pages

| Page | What is in it |
|---|---|
| [Installation](0.-Installation) | HACS or manual installation |
| [Configuration](1.-Configuration) | Getting a key or token, adding a sensor, the options |
| [Concepts](2.-Concepts) | Stop ID and pole, the service day, night lines, what the sensor shows |
| [Troubleshooting](3.-Troubleshooting) | States, messages, re-authentication, diagnostics, known behaviour |
| [Roadmap](4.-Roadmap) | Where plans and changes are written down |
| [Contributing](5.-Contributing) | Bug reports, pull requests, security reports |

## Quick start

1. Install **Warsaw Public Transport** with HACS and restart Home Assistant.
2. Get a token at [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) (an old API key also works for now).
3. **Settings → Devices & Services → Add Integration → Warsaw Public Transport**, then enter the key or token, the stop ID, the pole number and the line.

The wiki is published from the repository (`docs/wiki/`); edit the files there, not in the wiki's web interface.
