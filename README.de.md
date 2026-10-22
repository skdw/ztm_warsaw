<h1 align="center">🚍 ZTM Warschau für Home Assistant</h1>

<p align="center">
  <strong>Fahrpläne des Warschauer Nahverkehrs in Home Assistant.<br>Die nächsten Abfahrten für Dashboards und Automationen. Einrichtung ohne YAML.</strong>
</p>

<p align="center">
  🇬🇧 <a href="README.md">English</a>
  &nbsp;·&nbsp;
  🇵🇱 <a href="README.pl.md">Polski</a>
  &nbsp;·&nbsp;
  🇺🇦 <a href="README.uk.md">Українська</a>
  &nbsp;·&nbsp;
  🇷🇺 <a href="README.ru.md">Русский</a>
  &nbsp;·&nbsp;
  🇩🇪 <strong>Deutsch</strong>
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
<summary><strong>Inhaltsverzeichnis</strong></summary>

- [Funktionen](#-funktionen)
- [Screenshots](#-screenshots)
- [Voraussetzungen](#-voraussetzungen)
- [Schlüssel oder Token besorgen](#-schlüssel-oder-token-besorgen)
- [Installation](#-installation)
- [Konfiguration](#-konfiguration)
- [Fehlerbehebung](#-fehlerbehebung)
- [Dokumentation](#-dokumentation)
- [Mitwirken und Sicherheit](#-mitwirken-und-sicherheit)
- [Daten und Danksagung](#-daten-und-danksagung)
- [Lizenz](#-lizenz)

</details>

Zeigt, **wann der nächste Bus, die nächste Straßenbahn oder der nächste Zug an deiner Haltestelle fährt**: ein Sensor für eine Linie an einer Halteposition, für dein Dashboard und für Automationen wie „sag mir, wann ich losgehen muss“. Er nutzt die offenen Daten der Stadt Warschau und braucht keine zusätzliche Hardware.

Angezeigt werden **planmäßige** Abfahrten: keine Verspätungen oder Störungsmeldungen, nur der aktuelle Betriebstag und keine Reiseplanung (dafür gibt es [wtp.waw.pl](https://wtp.waw.pl)). Das Fahrzeug der nächsten Abfahrt lässt sich auf der Karte zeigen (optional, ein Token ist nötig).

---

## 🔧 Funktionen

- ✅ Busse, Straßenbahnen, U-Bahn und S-Bahn (SKM), auch Nacht-, Express- und Lokallinien.
- ✅ Die nächste Abfahrt ist der Zustand des Sensors; die drei danach sowie die erste und die letzte Abfahrt des Tages sind Attribute.
- ✅ Ein *Status*-Sensor sagt in einfachen Worten, was los ist („Die letzte Abfahrt des Tages ist vorbei“).
- ✅ Einrichtung über die Suche nach dem Haltestellennamen, dann Halteposition und Linie wählen: keine Nummern nachschlagen.
- ✅ Mehrere Linien und Haltestellen, optional eine Gehzeit, optional ein Kalender und optional eine Markierung des Fahrzeugs auf der Karte.
- ✅ Acht Sprachen: Englisch, Polnisch, Ukrainisch, Russisch, Deutsch, Spanisch, Französisch und Italienisch. Die sechs neueren sind maschinell übersetzt; Korrekturen sind als Pull Request willkommen.

---

## 📸 Screenshots

### Einrichtung der Integration
*Das Einrichtungsformular für Zugangsdaten, Linie und Haltestelle.*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Darstellung der Entität

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Attribute
*Fahrplandetails mit Abfahrtszeiten und Fahrtrichtung.*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Voraussetzungen

- Home Assistant 2026.1 oder neuer
- Ein API-Schlüssel oder Token der Stadt Warschau (siehe unten)

---

## 🧭 Schlüssel oder Token besorgen

Ein kostenloses Token bekommst du unter [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api): Spitznamen eingeben, Bedingungen akzeptieren und das Token herunterladen. Es ist ein langer Text aus drei Teilen, die durch Punkte getrennt sind.

Ein alter API-Schlüssel (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, von [api.um.warszawa.pl](https://api.um.warszawa.pl)) funktioniert noch, aber dieser Server antwortet zeitweise nicht, die Stadt hat kein Abschaltdatum genannt und das Fahrzeug auf der Karte braucht ein Token. Zum Wechseln öffne den Hinweis unter **Reparaturen** oder wähle bei der Linie **Konfigurieren** und füge das Token ein. Deine Einstellungen bleiben erhalten.

---

## 📦 Installation

### Mit HACS

1. Öffne in Home Assistant **HACS → Integrationen**.
2. Suche nach **Öffentlicher Nahverkehr Warschau**.
3. Klicke auf **Herunterladen** und bestätige.
4. Starte Home Assistant neu.

### Manuell

1. Lade die neueste Version von [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases) herunter.
2. Kopiere den Ordner `ztm_warsaw` nach `/config/custom_components/`.
3. Starte Home Assistant neu.

---

## 🔌 Konfiguration

1. Öffne **Einstellungen → Geräte & Dienste**.
2. Klicke auf **+ Integration hinzufügen** und suche nach **Öffentlicher Nahverkehr Warschau**.
3. Füge dein Token ein und gib einen Teil des Haltestellennamens (zum Beispiel `Marcelin`) oder die ID ein.
4. Wähle die Halteposition (die Nummer steht auf dem Haltestellenschild, jede Richtung hat eine eigene) und die Linie. Aufgelistet sind nur Linien, die dort heute halten.

Der Sensor heißt zum Beispiel `sensor.line_151_from_7009_01`. Eine weitere Haltestelle der Linie fügst du mit **Haltestelle hinzufügen** hinzu. Kennst du die Nummern schon, setze auf dem ersten Bildschirm den Haken bei **Ich kenne die Nummern**. Gehzeit, Kalender, Fahrzeugmarkierung und das Entfernen einer Linie stehen im [Wiki](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration).

---

## 🩺 Fehlerbehebung

- **Der Sensor ist `unknown` und zeigt „No service“.** Die Linie fährt heute nicht, oder ihre letzte Abfahrt ist vorbei. Das ist normal. Welcher Fall es ist, sagt der *Status*-Sensor; den Fahrplan gibt es auf [wtp.waw.pl](https://wtp.waw.pl), oder ruf 19115 an.
- **Der Sensor ist `unavailable`.** Die Stadt hat keinen gültigen Fahrplan geliefert: ein abgelehntes Token oder eine Haltestelle, Halteposition oder Linie, die sie nicht kennt. Der Grund steht im Home-Assistant-Protokoll (Schlüssel und Token werden nie protokolliert).
- **Netzwerkfehler, und du nutzt einen alten Schlüssel.** Der alte Server der Stadt antwortet zeitweise nicht. Die Sensoren behalten ihren Fahrplan und fragen später erneut; der Wechsel zu einem Token behebt das.
- **Home Assistant verlangt einen neuen Schlüssel.** Die Stadt hat den Schlüssel dreimal hintereinander abgelehnt. Gib im Formular einen neuen Schlüssel oder ein Token ein; deine Einstellungen bleiben erhalten.
- **Ein Problem melden.** Wähle beim Eintrag *Diagnosedaten herunterladen* und hänge die Datei an dein Issue. Schlüssel oder Token sind darin durch `**REDACTED**` ersetzt.

Weitere Antworten stehen im [Wiki](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting).

---

## 📚 Dokumentation

Das [Wiki](https://github.com/solarssk/ztm_warsaw/wiki) ist das Benutzerhandbuch: [Konfiguration](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration) (Gehzeit, eine Linie entfernen), [Konzepte](https://github.com/solarssk/ztm_warsaw/wiki/2.-Concepts) (der Betriebstag, was jede Entität zeigt), [Beispiele](https://github.com/solarssk/ztm_warsaw/wiki/3.-Examples) (Karten und Automationen zum Kopieren) und [Fehlerbehebung](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting). Es ist auf Englisch; die Quelle liegt in [`docs/wiki/`](docs/wiki).

---

## 🧑‍💻 Mitwirken und Sicherheit

Ideen, Fehlermeldungen und Pull Requests sind willkommen. Hinweise zur Mitarbeit findest du in [CONTRIBUTING.md](CONTRIBUTING.md). Sicherheitslücken meldest du nach der Anleitung in [SECURITY.md](SECURITY.md).

---

## 🙌 Daten und Danksagung

Daten: Die Stadt Warschau (**Miasto Stołeczne Warszawa**) und die Warschauer Verkehrsbehörde (**Zarząd Transportu Miejskiego**, ZTM) über das Open-Data-Portal der Stadt ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), unter der Lizenz [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/deed.de).

Konzept, Funktionen, Struktur und die Anbindung an die öffentliche API der Stadt Warschau habe ich selbst entworfen. Ich bin kein professioneller Python-Entwickler, konnte aber mit meinen Grundkenntnissen die Funktionsweise des Projekts planen.

ChatGPT hat mich bei Syntax, Fehlersuche und Implementierungsdetails unterstützt. Die Entscheidungen zu Aufbau und Funktionsweise des Projekts habe ich selbst getroffen.

Vielen Dank an [@peetereczek](https://github.com/peetereczek/ztm), dessen früheres Projekt mich inspiriert hat. Diese Integration wurde als eigenständiges Projekt von Grund auf neu entwickelt.

Du kannst das Projekt mit Ideen, Fehlermeldungen und Verbesserungsvorschlägen unterstützen.

---

## 📄 Lizenz

MIT-Lizenz
