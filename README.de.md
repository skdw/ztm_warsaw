<h1 align="center">🚍 ZTM Warschau für Home Assistant</h1>

<p align="center">
  <strong>Die nächsten planmäßigen Abfahrten einer Warschauer Bus-, Straßenbahn-, U-Bahn- oder Nachtlinie als Sensor.<br>Aus den offenen Daten der Stadt. Ohne YAML, ohne Echtzeit-Versprechen.</strong>
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

Zeigt die nächsten **planmäßigen Abfahrten** einer Linie des Warschauer Nahverkehrs (Bus, Straßenbahn, U-Bahn, S-Bahn oder Nachtlinie) an einem Haltestellenmast als Sensor in Home Assistant, aus den offenen Daten der Stadt Warschau. Nützlich für Dashboards und Automationen wie „geh in acht Minuten los“, ohne eine Fahrplan-App zu öffnen.

Es zeigt den **Fahrplan**, keine Fahrzeuge in Echtzeit. Was es **nicht** tut:

- keine Echtzeit-Positionen, Verspätungen oder Störungen: Die Stadt veröffentlicht geplante Abfahrten, die einmal am Tag aktualisiert werden;
- keine Fahrpläne für andere Tage: Die API liefert nur den aktuellen Betriebstag;
- keine Reiseplanung: Dafür gibt es [wtp.waw.pl](https://wtp.waw.pl).

---

## 🔧 Funktionen

- ✅ Bus-, Straßenbahn-, U-Bahn-, Nacht-, Friedhofs-, Express- und lokale Linien.
- ✅ Mehrere Instanzen: Überwache so viele Haltestellen und Linien, wie du möchtest.
- ✅ Die nächste Abfahrt als Zeitstempel für Oberfläche und Automationen und die drei folgenden als Attribute (`Next 1` ... `Next 3`).
- ✅ Ein klarer Zustand „No service“ an Tagen, an denen eine Linie nicht fährt, und `unavailable`, wenn die API der Stadt ausfällt (siehe [Fehlerbehebung](#-fehlerbehebung)).
- ✅ Vollständige Einrichtung in der Home-Assistant-Oberfläche, auf Englisch, Polnisch, Ukrainisch, Russisch, Deutsch, Spanisch, Französisch oder Italienisch (die Texte außer Englisch und Polnisch sind maschinell übersetzt: Korrekturen sind als Pull Request willkommen).
- ✅ Attribute mit der Haltestelle (Name und Position, sodass sie als Pin auf der Kartenkarte erscheint), der Richtung, einem Fahrplanlink und Hinweisen.
- ✅ Den API-Schlüssel oder das Token eines Eintrags kannst du jederzeit unter **Konfigurieren** ändern, zum Beispiel von der alten API der Stadt auf die neue.
- ✅ Eine **Kalender**-Entität pro Sensor (standardmäßig aus: aktiviere sie in den Entitätseinstellungen) mit jeder Abfahrt des Tages als Ein-Minuten-Termin: den ganzen Fahrplan siehst du in der Kalenderansicht von Home Assistant und startest Automationen mit dem Kalender-Trigger („8 Minuten vor einer Abfahrt“) ohne Templates.

---

## 📸 Screenshots

### Einrichtung der Integration
*Gib deinen API-Schlüssel und die Haltestellendaten an...*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Darstellung der Entität

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Attribute
*Beispiel-Entität mit Abfahrten und Attributen wie Zeit, Richtung...*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Voraussetzungen

- Home Assistant 2026.1 oder neuer
- Ein API-Schlüssel oder Token der Stadt Warschau (siehe unten)

---

## 🧭 Schlüssel oder Token besorgen

Die Stadt betreibt zwei Portale, und die Integration akzeptiert den Schlüssel von beiden:

- **Neu (empfohlen):** Gib auf [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) einen Nicknamen ein, akzeptiere die Bedingungen und lade dein eigenes Token herunter. Es ist ein langer Text aus drei durch Punkte getrennten Teilen.
- **Alt:** Ein Schlüssel von [api.um.warszawa.pl](https://api.um.warszawa.pl) sieht aus wie `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Bestehende alte Schlüssel funktionieren zum Zeitpunkt des Schreibens noch, aber die Stadt nennt weder ein Datum noch ein Versprechen, wie lange, also wechsle zu einem Token, sobald du kannst.

Die Integration erkennt, welchen du eingefügt hast, und spricht nur mit der passenden API. Um einen bestehenden Eintrag auf ein Token umzustellen, nutze **Konfigurieren** bei diesem Eintrag und gib das Token ein (Haltestelle und Linie bleiben); füge keinen zweiten Eintrag hinzu, denn zwei Einträge für dieselbe Haltestelle, denselben Mast und dieselbe Linie können nicht nebeneinander bestehen, und die Einrichtung lehnt den zweiten ab.

---

## 📦 Installation

### Mit HACS

1. Öffne in Home Assistant **HACS → Integrationen**.
2. Suche nach **Warsaw Public Transport**.
3. Klicke auf **Herunterladen** und bestätige.
4. Starte Home Assistant neu.

### Manuell

1. Lade die neueste Version von [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases) herunter.
2. Kopiere den Ordner `ztm_warsaw` nach `/config/custom_components/`.
3. Starte Home Assistant neu.

---

## 🔌 Konfiguration

1. Gehe zu **Einstellungen → Geräte & Dienste**.
2. Klicke auf **+ Integration hinzufügen** und suche nach **Warsaw Public Transport**.
3. Fülle aus:
   - **API-Schlüssel oder Token** (siehe oben),
   - **Haltestellen-ID** und **Mastnummer** (zum Beispiel 7009 und 01),
   - **Liniennummer** (zum Beispiel 151).

Die Entität ist nach Haltestelle und Linie benannt, zum Beispiel `sensor.line_151_from_7009_01`. Um den API-Schlüssel oder das Token eines Eintrags zu ersetzen (etwa vom alten Schlüssel auf ein Token), nutze **Einstellungen → Geräte & Dienste → Warsaw Public Transport → Konfigurieren** bei diesem Eintrag; Haltestelle und Linie bleiben. Ein Eintrag, der noch einen alten Schlüssel nutzt, zeigt einen schließbaren Hinweis unter **Einstellungen → Reparaturen**.

**Haltestellen-ID und Mastnummer** sind nicht dasselbe: Die Haltestellen-ID gilt für alle Masten einer Haltestelle, und die Mastnummer (meist 01, 02, ...) ist die Nummer auf dem Schild des Mastes (*słupek*). Eine Haltestelle mit mehreren Richtungen hat für jede eine andere Nummer.

---

## 🩺 Fehlerbehebung

- **Der Zustand ist `unknown`, und das Attribut sagt „No service“.** Die Linie fährt heute nicht, oder ihre letzte Abfahrt ist vorbei. Das ist kein Fehler: Prüfe [wtp.waw.pl](https://wtp.waw.pl) oder ruf 19115 an.
- **Der Sensor ist `unavailable`.** Die API der Stadt hat geantwortet, aber nicht mit einem Fahrplan: Schlüssel oder Token wurde abgelehnt, Haltestelle, Mast und Linie sind der API nicht bekannt, oder die Antwort hatte ein Format, das die Integration nicht versteht. Schlägt schon das erste Laden fehl (nicht wegen eines abgelehnten Schlüssels, siehe unten), erscheint die Integration als *Einrichtung wird wiederholt*, und Home Assistant versucht es von selbst erneut. Der Fehler steht im Home-Assistant-Log (der Schlüssel wird nie protokolliert), und der Sensor erholt sich von selbst, wenn die API wieder richtig antwortet; falls nicht, prüfe in den Einstellungen Schlüssel sowie Haltestelle, Mast und Linie.
- **Home Assistant fragt nach einem neuen Schlüssel (erneute Authentifizierung).** Die alte API hat dreimal hintereinander „Schlüssel abgelehnt“ geantwortet (auch die Wiederholungen einer Einrichtung zählen; ein Ausfall dazwischen beginnt die Zählung neu). Gib in der Abfrage einen neuen Schlüssel oder ein Token ein; Haltestelle und Linie bleiben, und ein Schlüssel wird auch akzeptiert, wenn die Linie heute nicht fährt. Bis dahin bleibt der Sensor `unavailable`. Die neue API antwortet auf jede abgelehnte Anfrage gleich, deshalb lässt sich ein abgelehntes Token dort nicht von einem Ausfall unterscheiden: Der Sensor behält den gespeicherten Fahrplan bis zum Ende seines Betriebstags, wird dann `unavailable`, und es erscheint keine Abfrage; wenn du das Token widerrufen hast, gib unter **Konfigurieren** beim Eintrag ein neues ein.
- **Ein Problem melden.** Öffne den Eintrag der Integration, nutze *Diagnose herunterladen* und hänge die Datei an das Issue an: Sie zeigt den Eintrag und den Zustand des Fahrplans, Schlüssel oder Token sind durch `**REDACTED**` ersetzt.
- **Die Daten wirken bei einem Ausfall veraltet.** Eine Zeitüberschreitung, ein Netzwerkfehler oder ein Serverfehler (HTTP 5xx) nach einem erfolgreichen Laden macht den Sensor **nicht** `unavailable`: Er behält den letzten Fahrplan und versucht es jede Stunde erneut, weil der Fahrplan geplante Daten sind, die sich innerhalb eines Tages nicht ändern. Der Diagnosesensor **Last update** (standardmäßig aus; aktiviere ihn in den Entitätseinstellungen) zeigt, wann die Daten zuletzt erfolgreich geladen wurden.
- **Die Einrichtung sagt, die Linie wurde nicht gefunden.** Die API listet nur Linien auf, die heute fahren. Eine Linie, die heute nicht fährt (zum Beispiel eine Werktagslinie an einem Sonntag), kann erst an dem Tag hinzugefügt werden, an dem sie fährt.
- **Eine Linie von wtp.waw.pl fehlt hier.** Der Reiseplaner hat mehr Daten als die öffentliche API. Das lässt sich in der Integration nicht beheben.
- **Nachtlinien** (`N01`, `N44` ...): Die Stadt rechnet die ganze Nacht zum vorherigen Betriebstag, ein Bus um `24:50` oder `26:20` steht also noch im Fahrplan dieses Tages. Die Integration liest diese Zeiten richtig, eine Abfahrt um `02:15` (`26:15` in der API) wird um 02:00 als „in 15 Minuten“ angezeigt.

---

## 📚 Dokumentation

Das [Wiki](https://github.com/solarssk/ztm_warsaw/wiki) ist das Benutzerhandbuch: Installation, Konfiguration, wie Fahrplan und Betriebstag funktionieren, und Fehlerbehebung. Es wird aus [`docs/wiki/`](docs/wiki) in diesem Repository veröffentlicht (auf Englisch).

---

## 🧑‍💻 Mitwirken und Sicherheit

Ideen, Fehlerberichte und Pull Requests sind willkommen: siehe [CONTRIBUTING.md](CONTRIBUTING.md). Eine Sicherheitslücke meldest du laut [SECURITY.md](SECURITY.md).

---

## 🙌 Daten und Danksagung

Daten: Die Stadt Warschau (**Miasto Stołeczne Warszawa**) und die Warschauer Verkehrsbehörde (**Zarząd Transportu Miejskiego**, ZTM) über das Open-Data-Portal der Stadt ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), unter der Lizenz [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/deed.de).

Dieses Projekt wurde vollständig von mir geplant und entworfen: vom Konzept und dem erwarteten Verhalten der Integration bis zur Art, wie sie mit der öffentlichen API der Stadt Warschau zusammenarbeitet. Ich bin kein professioneller Python-Entwickler, verstehe die Grundlagen aber gut genug, um Struktur, Logik und Funktionen festzulegen, die ich mir von dieser Integration wünschte.

Zur Umsetzung habe ich KI-Unterstützung (ChatGPT) genutzt, die mir vor allem bei Syntax, Fehlersuche und Implementierungsdetails half. Das Gesamtdesign, das Verhalten und der Arbeitsablauf stammen jedoch von mir.

Besonderer Dank gilt [@peetereczek](https://github.com/peetereczek/ztm), dessen früheres Projekt mich anfangs inspiriert hat. Obwohl diese endgültige Version unabhängig von Grund auf entstand, gab mir seine Arbeit den ersten Anstoß, die Dinge auf meine Weise anzugehen.

Wenn du das Projekt verbessern oder erweitern möchtest: nur zu! Beiträge, Ideen und Pull Requests sind jederzeit willkommen.

---

## 📄 Lizenz

MIT-Lizenz
