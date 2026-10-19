<h1 align="center">🚍 ZTM Warszawa w Home Assistancie</h1>

<p align="center">
  <strong>Kiedy odjedzie najbliższy autobus, tramwaj albo metro? Odjazdy według rozkładu, z otwartych danych Warszawy, jako sensor.<br>Bez YAML-a i bez obietnic, że zobaczysz pojazdy na żywo.</strong>
</p>

<p align="center">
  🇬🇧 <a href="README.md">English</a>
  &nbsp;·&nbsp;
  🇵🇱 <strong>Polski</strong>
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
<summary><strong>Spis treści</strong></summary>

- [Funkcje](#-funkcje)
- [Zrzuty ekranu](#-zrzuty-ekranu)
- [Wymagania](#-wymagania)
- [Klucz i token](#-klucz-i-token)
- [Instalacja](#-instalacja)
- [Konfiguracja](#-konfiguracja)
- [Rozwiązywanie problemów](#-rozwiązywanie-problemów)
- [Dokumentacja](#-dokumentacja)
- [Współpraca i bezpieczeństwo](#-współpraca-i-bezpieczeństwo)
- [Dane i podziękowania](#-dane-i-podziękowania)
- [Licencja](#-licencja)

</details>

Sensor pokazuje najbliższe odjazdy jednej linii (autobusowej, tramwajowej, metra, SKM lub nocnej) z wybranego słupka, **według rozkładu jazdy**, na podstawie otwartych danych m.st. Warszawy. Przyda się na pulpicie i w automatyzacjach w stylu „wyjdź za osiem minut”, bez zaglądania do aplikacji z rozkładem.

To rozkład, a nie pojazdy na żywo. Czego integracja **nie** robi:

- nie pokazuje opóźnień, utrudnień ani pozycji pojazdów: miasto publikuje tylko planowane odjazdy i odświeża je raz na dobę;
- nie pokazuje rozkładów na inne dni: API podaje tylko bieżącą dobę;
- nie planuje podróży: do tego służy [wtp.waw.pl](https://wtp.waw.pl).

---

## 🔧 Funkcje

- ✅ Linie autobusowe, tramwajowe, metro, kolejowe, nocne, cmentarne, ekspresowe i lokalne.
- ✅ Dowolnie wiele przystanków i linii.
- ✅ Najbliższy odjazd jako znacznik czasu, który wykorzystasz w interfejsie i w automatyzacjach, a trzy kolejne jako atrybuty (`Next 1` ... `Next 3`).
- ✅ Czytelny stan „No service”, gdy linia danego dnia nie kursuje, i `unavailable`, gdy API miasta nie działa (zob. [Rozwiązywanie problemów](#-rozwiązywanie-problemów)).
- ✅ Cała konfiguracja w interfejsie Home Assistanta, po angielsku, polsku, ukraińsku, rosyjsku, niemiecku, hiszpańsku, francusku i włosku (poza angielskim i polskim to tłumaczenia maszynowe, poprawki mile widziane jako pull requesty).
- ✅ Atrybuty z nazwą i położeniem przystanku (dzięki nim widać go jako pinezkę na mapie), kierunkiem, linkiem do rozkładu i uwagami.
- ✅ Klucz lub token zmienisz w dowolnej chwili w **Konfiguruj**, na przykład przechodząc ze starego API miasta na nowe.
- ✅ Osobna encja **kalendarza** przy każdym sensorze (domyślnie wyłączona, włączysz ją w ustawieniach encji): każdy odjazd z danej doby jako jednominutowe wydarzenie. Cały rozkład zobaczysz w kalendarzu Home Assistanta, a automatyzację uruchomisz wyzwalaczem kalendarza („8 minut przed odjazdem”), bez szablonów.

---

## 📸 Zrzuty ekranu

### Konfiguracja integracji
*Podaj klucz API i dane przystanku...*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Wygląd encji

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Atrybuty
*Przykładowa encja z odjazdami i atrybutami, takimi jak czas czy kierunek...*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Wymagania

- Home Assistant 2026.1 lub nowszy
- Klucz API lub token z portalu danych miasta (opis poniżej)

---

## 🧭 Klucz i token

Miasto ma dwa portale, a integracja przyjmuje klucz z każdego z nich:

- **Nowy (zalecany):** na [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) podaj pseudonim, zaakceptuj regulamin i pobierz swój token. To długi ciąg znaków z trzech części oddzielonych kropkami.
- **Stary:** klucz z [api.um.warszawa.pl](https://api.um.warszawa.pl) wygląda tak: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Na razie działa, ale miasto nie podało, jak długo jeszcze, więc przejdź na token, gdy tylko będziesz mógł.

Integracja sama rozpozna, co wkleiłeś, i połączy się tylko z pasującym API. Żeby przenieść istniejący wpis na token, wybierz **Konfiguruj** przy tym wpisie i wpisz token (przystanek i linia zostają). Nie dodawaj drugiego wpisu: dwa wpisy tego samego przystanku, słupka i linii nie mogą istnieć obok siebie, więc kreator odrzuci drugi.

---

## 📦 Instalacja

### Przez HACS

1. W Home Assistancie otwórz **HACS → Integracje**.
2. Wyszukaj **Warsaw Public Transport**.
3. Kliknij **Pobierz** i potwierdź.
4. Uruchom ponownie Home Assistanta.

### Ręcznie

1. Pobierz najnowszą wersję z [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Skopiuj folder `ztm_warsaw` do `/config/custom_components/`.
3. Uruchom ponownie Home Assistanta.

---

## 🔌 Konfiguracja

1. Wejdź w **Ustawienia → Urządzenia i usługi**.
2. Kliknij **+ Dodaj integrację** i wyszukaj **Warsaw Public Transport**.
3. Wypełnij pola:
   - **klucz API lub token** (zob. wyżej),
   - **ID przystanku** i **numer słupka** (np. 7009 i 01),
   - **numer linii** (np. 151).

Encja dostaje nazwę od przystanku i linii, np. `sensor.line_151_from_7009_01`. Klucz lub token zmienisz w **Ustawienia → Urządzenia i usługi → Warsaw Public Transport → Konfiguruj** przy danym wpisie (przystanek i linia zostają). Jeśli wpis nadal używa starego klucza, w **Ustawienia → Naprawy** zobaczysz powiadomienie, które możesz zamknąć.

**ID przystanku** i **numer słupka** to nie to samo: ID jest wspólne dla wszystkich słupków przystanku, a numer słupka (zwykle 01, 02, ...) znajdziesz na tabliczce przy słupku. Przystanek z kilkoma kierunkami ma osobny numer dla każdego z nich.

---

## 🩺 Rozwiązywanie problemów

- **Stan to `unknown`, a atrybut mówi „No service”.** Linia dziś nie kursuje albo ostatni odjazd już był. To nie błąd. Sprawdź [wtp.waw.pl](https://wtp.waw.pl) albo zadzwoń pod 19115.
- **Sensor jest `unavailable`.** API miasta odpowiedziało, ale nie rozkładem: odrzuciło klucz lub token, nie zna takiego przystanku, słupka lub linii albo odesłało odpowiedź w formacie, którego integracja nie rozumie. Jeśli nie uda się już pierwsze wczytanie (z innego powodu niż odrzucony klucz, zob. niżej), integracja pokaże się jako *ponawianie konfiguracji*, a Home Assistant spróbuje ponownie sam. Błąd znajdziesz w logu Home Assistanta (klucz nigdy się w nim nie pojawia), a sensor wróci do normy, gdy tylko API znów odpowie poprawnie. Jeśli nie wróci, sprawdź w ustawieniach klucz, przystanek, słupek i linię.
- **Home Assistant prosi o nowy klucz.** Stare API trzy razy z rzędu odrzuciło klucz (liczą się też ponowienia podczas konfiguracji, a awaria w międzyczasie zeruje licznik). Wpisz nowy klucz lub token w oknie, które się pojawi: przystanek i linia zostają, a klucz zostanie przyjęty nawet wtedy, gdy linia dziś nie kursuje. Do tego czasu sensor pozostanie `unavailable`. Nowe API na każde odrzucone żądanie odpowiada tak samo, więc odrzuconego tokenu nie da się tam odróżnić od awarii: sensor trzyma zapamiętany rozkład do końca doby, potem staje się `unavailable`, a okno się nie pojawia. Jeśli unieważniłeś token, wpisz nowy w **Konfiguruj** przy wpisie.
- **Zgłaszanie problemu.** Otwórz wpis integracji, wybierz *Pobierz diagnostykę* i dołącz plik do zgłoszenia. Zawiera stan wpisu i rozkładu, a klucz lub token jest w nim zastąpiony napisem `**REDACTED**`.
- **Dane wyglądają na stare podczas awarii.** Przekroczenie czasu, błąd sieci lub serwera (HTTP 5xx) po udanym wczytaniu **nie** zmienia sensora w `unavailable`: zachowuje ostatni rozkład i ponawia próbę co godzinę, bo rozkład to dane planowe, które nie zmieniają się w ciągu doby. Sensor diagnostyczny **Last update** (domyślnie wyłączony, włączysz go w ustawieniach encji) pokazuje, kiedy dane udało się pobrać ostatnio.
- **Kreator pisze, że nie znaleziono linii.** API wymienia tylko linie, które kursują dzisiaj. Linii, która dziś nie jeździ (np. kursuje tylko w dni robocze, a jest niedziela), nie da się dodać, dopóki nie wyjedzie na trasę.
- **Linii z wtp.waw.pl tu nie ma.** Planer podróży ma więcej danych niż publiczne API i integracja tego nie zmieni.
- **Linie nocne** (`N01`, `N44` ...): miasto liczy całą noc do poprzedniej doby, więc autobus o `24:50` albo `26:20` figuruje w rozkładzie tamtej doby. Integracja czyta te godziny poprawnie: odjazd o `02:15` (w API `26:15`) o 02:00 pokaże się jako „za 15 minut”.

---

## 📚 Dokumentacja

[Wiki](https://github.com/solarssk/ztm_warsaw/wiki) to podręcznik użytkownika: instalacja, konfiguracja, jak działają rozkład i doba oraz rozwiązywanie problemów. Źródła są w [`docs/wiki/`](docs/wiki) w tym repozytorium (po angielsku).

---

## 🧑‍💻 Współpraca i bezpieczeństwo

Pomysły, zgłoszenia błędów i pull requesty są mile widziane, zob. [CONTRIBUTING.md](CONTRIBUTING.md). Lukę w zabezpieczeniach zgłosisz według [SECURITY.md](SECURITY.md).

---

## 🙌 Dane i podziękowania

Dane: Miasto Stołeczne Warszawa i Zarząd Transportu Miejskiego (ZTM), z portalu otwartych danych ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), na licencji [Creative Commons Uznanie autorstwa](https://creativecommons.org/licenses/by/4.0/deed.pl).

Projekt w całości wymyśliłem i zaprojektowałem sam: od pomysłu i tego, jak ma działać, po sposób współpracy z publicznym API Warszawy. Nie jestem zawodowym programistą Pythona, ale znam podstawy na tyle, żeby określić strukturę, logikę i funkcje, które chciałem mieć.

Przy pisaniu pomagała mi sztuczna inteligencja (ChatGPT), głównie ze składnią, debugowaniem i szczegółami implementacji. Całość projektu, jego działanie i sposób pracy to jednak moje decyzje.

Szczególnie dziękuję [@peetereczek](https://github.com/peetereczek/ztm), którego wcześniejszy projekt zainspirował mnie na początku. Choć ta wersja powstała od zera i niezależnie, jego praca dała mi pierwszy impuls, żeby zrobić to po swojemu.

Jeśli chcesz coś poprawić albo rozwinąć, śmiało! Wkład, pomysły i pull requesty zawsze są mile widziane.

---

## 📄 Licencja

Licencja MIT
