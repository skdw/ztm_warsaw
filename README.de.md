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

Die Integration zeigt **planmäßige Abfahrten** auf Grundlage der offenen Daten der Stadt Warschau. Jeder Sensor zeigt die Abfahrten einer Linie an einer bestimmten Halteposition. Du kannst sie auf deinem Home-Assistant-Dashboard anzeigen oder in Automationen verwenden, etwa für eine Erinnerung, rechtzeitig zum Bus loszugehen.

Die Daten stammen aus veröffentlichten Fahrplänen. Dabei gelten folgende Einschränkungen:

- keine Verspätungen oder Störungsmeldungen — die API liefert planmäßige Abfahrten, die einmal täglich aktualisiert werden. Das Fahrzeug der nächsten Abfahrt lässt sich als optionale Entität auf der Karte zeigen (braucht ein Token, siehe Wiki);
- Fahrpläne nur für den aktuellen Betriebstag — die öffentliche API stellt keine anderen Tage bereit;
- keine Routen- oder Umsteigeplanung — nutze dafür [wtp.waw.pl](https://wtp.waw.pl).

---

## 🔧 Funktionen

- ✅ Busse, Straßenbahnen, U-Bahn und SKM-Züge, einschließlich Nacht-, Friedhofs-, Express- und lokaler Linien.
- ✅ Unterstützung für mehrere Linien und Haltestellen.
- ✅ Die nächste Abfahrtszeit als Sensorzustand für Dashboards und Automationen. Die drei folgenden Abfahrten stehen als Attribute zur Verfügung (`Next 1`–`Next 3`).
- ✅ Der Hinweis „No service“, wenn keine Abfahrten mehr anstehen, und der Zustand `unavailable`, wenn kein gültiger Fahrplan abgerufen werden kann (siehe [Fehlerbehebung](#-fehlerbehebung)).
- ✅ Einrichtung in der Home-Assistant-Oberfläche auf Englisch, Polnisch, Ukrainisch, Russisch, Deutsch, Spanisch, Französisch und Italienisch. Die sechs neuen Sprachfassungen wurden maschinell übersetzt; Korrekturen sind als Pull Requests willkommen.
- ✅ Sensorattribute mit Name und Koordinaten der Haltestelle, Fahrtrichtung, Fahrplanlink und Hinweisen. Mit den Koordinaten lässt sich die Haltestelle auf einer Karte anzeigen.
- ✅ API-Schlüssel oder Token unter **Konfigurieren** ändern, auch beim Wechsel zur neuen API der Stadt.
- ✅ Eine eigene **Kalenderentität** für jeden Sensor, standardmäßig deaktiviert. Nach dem Aktivieren in den Entitätseinstellungen erscheint jede Abfahrt des Betriebstags als einminütiger Termin. Mit einem Kalender-Trigger kannst du eine Automation beispielsweise acht Minuten vor der Abfahrt starten, ohne Templates zu erstellen.

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

Die Integration unterstützt Zugangsdaten für beide APIs der Stadt Warschau:

- **Token für die neue API (empfohlen):** Gib auf [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) einen Nicknamen ein, akzeptiere die Bedingungen und lade dein Token herunter. Es besteht aus einer langen Zeichenfolge mit drei durch Punkte getrennten Teilen.
- **Schlüssel für die alte API:** Ein Schlüssel von [api.um.warszawa.pl](https://api.um.warszawa.pl) hat das Format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Die alte API funktioniert weiterhin, die Stadt hat aber noch keinen Abschalttermin bekannt gegeben. Wir empfehlen den Wechsel zur neuen API.

Die Integration erkennt die Art der Zugangsdaten und sendet sie ausschließlich an die passende API. Um einen alten Schlüssel durch ein Token zu ersetzen, wähle bei der Linie **Konfigurieren** und füge das Token ein. Die Einstellungen für Linie und Haltestellen bleiben erhalten. Du musst die Integration nicht erneut hinzufügen: Eine doppelte Konfiguration derselben Linie an derselben Halteposition wird abgelehnt.

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

1. Gehe zu **Einstellungen → Geräte & Dienste**.
2. Klicke auf **+ Integration hinzufügen** und suche nach **Öffentlicher Nahverkehr Warschau**.
3. Fülle aus:
   - **API-Schlüssel oder Token** (siehe oben),
   - **Haltestellen-ID** und **Nummer der Halteposition** (zum Beispiel 7009 und 01),
   - **Liniennummer** (zum Beispiel 151).

Die Entitäts-ID enthält Liniennummer, Haltestellen-ID und Nummer der Halteposition, zum Beispiel `sensor.line_151_from_7009_01`. Um API-Schlüssel oder Token zu ändern, öffne **Einstellungen → Geräte & Dienste → Öffentlicher Nahverkehr Warschau** und wähle bei der Linie **Konfigurieren**. Die Einstellungen für Linie und Haltestellen bleiben erhalten. Wird noch ein alter Schlüssel verwendet, erscheint unter **Reparaturen** ein Hinweis zum Wechsel auf ein Token. Du kannst den Hinweis ignorieren.

Die **Haltestellen-ID** gilt für alle Haltepositionen einer Haltestelle. Die **Nummer der Halteposition** bezeichnet den konkreten Einstiegsort, meist für eine Fahrtrichtung. Sie besteht üblicherweise aus zwei Ziffern wie 01 oder 02 und steht auf dem Haltestellenschild. Auf Polnisch heißt diese nummerierte Halteposition *słupek*.

---

## 🩺 Fehlerbehebung

- **Der Sensorzustand ist `unknown`, die Attribute zeigen „No service“.** Die Linie fährt heute nicht oder alle Abfahrten sind bereits vorbei. Das ist das erwartete Verhalten. Prüfe den Fahrplan auf [wtp.waw.pl](https://wtp.waw.pl) oder unter der Telefonnummer 19115.
- **Der Sensor ist `unavailable` (nicht verfügbar).** Die API hat keinen gültigen Fahrplan geliefert. Mögliche Ursachen sind ein abgelehnter Schlüssel, falsche Angaben zu Haltestelle, Halteposition oder Linie oder ein nicht unterstütztes Antwortformat. Scheitert der erste Datenabruf aus einem anderen Grund als einem abgelehnten Schlüssel, wiederholt Home Assistant die Einrichtung automatisch. Für abgelehnte Schlüssel gilt der folgende Abschnitt. Details stehen im Home-Assistant-Protokoll; Schlüssel und Tokens werden dort nicht gespeichert. Sobald gültige Daten vorliegen, ist der Sensor wieder verfügbar. Prüfe bei anhaltenden Problemen die Zugangsdaten und Haltestellenangaben.
- **Home Assistant fordert einen neuen Schlüssel an.** Die alte API hat den Schlüssel dreimal in Folge abgelehnt. Wiederholungsversuche während der Einrichtung zählen mit; ein Netzwerk- oder Serverfehler unterbricht die Folge. Gib im Formular einen neuen API-Schlüssel oder ein Token ein. Die Einstellungen bleiben erhalten. Ein gültiger Schlüssel wird auch akzeptiert, wenn die Linie heute nicht fährt. Bis zur Änderung bleibt der Sensor nicht verfügbar. Bei der neuen API lässt sich ein abgelehntes Token nicht von einem Dienstausfall unterscheiden. Ein bereits geladener Fahrplan wird bis zum Ende des Betriebstags weiterverwendet, danach ist der Sensor nicht verfügbar. Es erscheint kein automatisches Formular zum Ändern der Zugangsdaten. Hast du dein Token widerrufen, gib unter **Konfigurieren** bei der Linie ein neues ein.
- **Ein Problem melden.** Öffne die Konfiguration der Linie, wähle *Diagnosedaten herunterladen* und füge die Datei deiner Fehlermeldung bei. Sie enthält Informationen zur Konfiguration und zum Fahrplan. Der API-Schlüssel oder das Token wird durch `**REDACTED**` ersetzt.
- **Trotz API-Ausfall werden weiterhin Abfahrten angezeigt.** Nach einem erfolgreichen Abruf führen Zeitüberschreitungen, Netzwerk- oder Serverfehler (HTTP 5xx) nicht sofort dazu, dass der Sensor nicht verfügbar ist. Die Integration verwendet den gespeicherten Fahrplan bis zum Ende des Betriebstags und versucht den Abruf stündlich erneut. Planmäßige Abfahrten ändern sich im Tagesverlauf nicht. Der standardmäßig deaktivierte Diagnosesensor **Last update** zeigt den letzten erfolgreichen Abruf an; du kannst ihn in den Entitätseinstellungen aktivieren.
- **Bei der Einrichtung wird die Linie nicht gefunden.** Die API liefert nur Linien, die am jeweiligen Tag fahren. Eine reine Werktagslinie lässt sich beispielsweise nicht an einem Sonntag hinzufügen. Versuche es an einem Tag mit planmäßigen Abfahrten erneut.
- **Eine Linie wird auf wtp.waw.pl angezeigt, fehlt aber in der Integration.** Der Routenplaner verwendet mehr Daten als die öffentliche API. Die Integration kann nur die von der API bereitgestellten Daten anzeigen.
- **Abfahrtszeiten von Nachtlinien** (`N01`, `N44` usw.). Ein Betriebstag kann über Mitternacht hinausgehen: `24:50` bedeutet 00:50 Uhr am Folgetag, `26:20` bedeutet 02:20 Uhr. Die Integration rechnet diese Angaben korrekt um. Eine Abfahrt mit der API-Zeit `26:15` findet am Folgetag um 02:15 Uhr statt und wird um 02:00 Uhr als „in 15 Minuten“ angezeigt.

---

## 📚 Dokumentation

Das [Benutzerhandbuch im Wiki](https://github.com/solarssk/ztm_warsaw/wiki) erklärt Installation, Einrichtung, Fahrpläne, Betriebstage und Fehlerbehebung. Es ist auf Englisch verfügbar; die Quelldateien liegen unter [`docs/wiki/`](docs/wiki).

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
