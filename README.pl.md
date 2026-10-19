<h1 align="center">🚍 ZTM Warszawa dla Home Assistanta</h1>

<p align="center">
  <strong>Najbliższe rozkładowe odjazdy linii autobusowej, tramwajowej, metra lub nocnej w Warszawie jako sensor.<br>Z otwartych danych miasta. Bez YAML-a i bez obietnic o pozycjach na żywo.</strong>
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
- [Jak zdobyć klucz lub token](#-jak-zdobyć-klucz-lub-token)
- [Instalacja](#-instalacja)
- [Konfiguracja](#-konfiguracja)
- [Rozwiązywanie problemów](#-rozwiązywanie-problemów)
- [Dokumentacja](#-dokumentacja)
- [Współpraca i bezpieczeństwo](#-współpraca-i-bezpieczeństwo)
- [Dane i podziękowania](#-dane-i-podziękowania)
- [Licencja](#-licencja)

</details>

Pokazuje najbliższe **rozkładowe** odjazdy jednej linii komunikacji miejskiej w Warszawie (autobusowej, tramwajowej, metra, kolejowej lub nocnej) z jednego słupka jako sensor w Home Assistancie, na podstawie otwartych danych miasta. Przydaje się do pulpitów i automatyzacji w rodzaju „wyjdź za osiem minut” bez zaglądania do aplikacji z rozkładem.

Pokazuje **rozkład**, a nie pojazdy na żywo. Czego **nie** robi:

- nie pokazuje pozycji na żywo, opóźnień ani utrudnień: miasto publikuje planowane odjazdy, odświeżane raz na dobę;
- nie pokazuje rozkładów na inne dni: API udostępnia tylko bieżącą dobę kursową;
- nie planuje podróży: do tego służy [wtp.waw.pl](https://wtp.waw.pl).

---

## 🔧 Funkcje

- ✅ Linie autobusowe, tramwajowe, metro, nocne, cmentarne, ekspresowe i lokalne.
- ✅ Wiele instancji: możesz śledzić tyle przystanków i linii, ile chcesz.
- ✅ Najbliższy odjazd jako znacznik czasu, do użycia w interfejsie i w automatyzacjach, oraz trzy kolejne jako atrybuty (`Next 1` ... `Next 3`).
- ✅ Czytelny stan „No service” w dni, gdy linia nie kursuje, i stan `unavailable`, gdy API miasta zawodzi (zob. [Rozwiązywanie problemów](#-rozwiązywanie-problemów)).
- ✅ Cała konfiguracja w interfejsie Home Assistanta, po angielsku, polsku, ukraińsku, rosyjsku, niemiecku, hiszpańsku, francusku lub włosku (teksty poza angielskim i polskim są tłumaczone maszynowo: poprawki mile widziane jako pull requesty).
- ✅ Atrybuty z przystankiem (nazwa i położenie, więc widać go jako pinezkę na karcie mapy), kierunkiem, linkiem do rozkładu i uwagami.
- ✅ Klucz API lub token wpisu możesz zmienić w dowolnej chwili w **Konfiguruj**, na przykład ze starego API miasta na nowe.
- ✅ Encja **kalendarza** przy każdym sensorze (domyślnie wyłączona: włącz ją w ustawieniach encji) z każdym odjazdem doby jako jednominutowym wydarzeniem: cały rozkład widać w widoku kalendarza Home Assistanta, a automatyzacje uruchamiasz wyzwalaczem kalendarza („8 minut przed odjazdem”) bez szablonów.

---

## 📸 Zrzuty ekranu

### Konfiguracja integracji
*Podaj klucz API i dane przystanku...*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Wygląd encji

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Atrybuty
*Przykładowa encja z odjazdami i atrybutami takimi jak czas, kierunek...*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Wymagania

- Home Assistant 2026.1 lub nowszy
- Klucz API lub token od miasta Warszawy (poniżej)

---

## 🧭 Jak zdobyć klucz lub token

Miasto prowadzi dwa portale, a integracja przyjmuje klucz z każdego z nich:

- **Nowy (zalecany):** na [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) wpisz pseudonim, zaakceptuj regulamin i pobierz własny token. To długi tekst w trzech częściach oddzielonych kropkami.
- **Stary:** klucz z [api.um.warszawa.pl](https://api.um.warszawa.pl) wygląda jak `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Dotychczasowe stare klucze nadal działają w chwili pisania, ale miasto nie podaje daty ani obietnicy, jak długo, więc przejdź na token, gdy możesz.

Integracja rozpoznaje, który z nich wkleiłeś, i rozmawia tylko z pasującym API. Aby przenieść istniejący wpis na token, użyj **Konfiguruj** przy tym wpisie i wpisz token (przystanek i linia zostają); nie dodawaj drugiego wpisu, bo dwa wpisy tego samego przystanku, słupka i linii nie mogą współistnieć, a kreator odrzuci drugi.

---

## 📦 Instalacja

### Przez HACS

1. W Home Assistancie wejdź w **HACS → Integracje**.
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
3. Uzupełnij:
   - **klucz API lub token** (zob. wyżej),
   - **ID przystanku** i **numer słupka** (na przykład 7009 i 01),
   - **numer linii** (na przykład 151).

Encja ma nazwę od przystanku i linii, na przykład `sensor.line_151_from_7009_01`. Aby zamienić klucz API lub token wpisu (np. ze starego klucza na token), użyj **Ustawienia → Urządzenia i usługi → Warsaw Public Transport → Konfiguruj** przy tym wpisie; przystanek i linia zostają. Wpis, który nadal używa starego klucza, pokazuje zamykane powiadomienie w **Ustawienia → Naprawy**.

**ID przystanku i numer słupka** to nie to samo: ID przystanku jest wspólne dla wszystkich słupków przystanku, a numer słupka (zwykle 01, 02, ...) to numer namalowany na tabliczce słupka. Przystanek z kilkoma kierunkami ma osobny numer dla każdego.

---

## 🩺 Rozwiązywanie problemów

- **Stan to `unknown`, a atrybut mówi „No service”.** Linia dziś nie kursuje albo jej ostatni odjazd już minął. To nie błąd: sprawdź [wtp.waw.pl](https://wtp.waw.pl) lub zadzwoń pod 19115.
- **Sensor jest `unavailable`.** API miasta odpowiedziało, ale nie rozkładem: klucz lub token został odrzucony, przystanek, słupek i linia nie są znane API albo odpowiedź miała format, którego integracja nie rozumie. Jeśli już pierwsze wczytanie się nie uda (nie z powodu odrzuconego klucza, zob. niżej), integracja pokazuje się jako *ponawianie konfiguracji*, a Home Assistant ponawia sam. Błąd jest w logu Home Assistanta (klucz nigdy się w nim nie pojawia), a sensor wraca sam, gdy API znów odpowiada poprawnie; jeśli nie, sprawdź w ustawieniach klucz oraz przystanek, słupek i linię.
- **Home Assistant prosi o nowy klucz (ponowne uwierzytelnienie).** Stare API trzy razy z rzędu odpowiedziało „klucz odrzucony” (liczą się też ponowienia konfiguracji; awaria w międzyczasie zaczyna liczenie od nowa). Wpisz nowy klucz lub token w oknie; przystanek i linia zostają, a klucz zostanie przyjęty nawet wtedy, gdy linia dziś nie kursuje. Dopóki tego nie zrobisz, sensor pozostaje `unavailable`. Nowe API odpowiada tak samo na każde odrzucone żądanie, więc odrzucony token nie da się tam odróżnić od awarii: sensor trzyma zapisany rozkład do końca swojej doby kursowej, potem staje się `unavailable`, a okno nie pojawia się; jeśli unieważniłeś token, wpisz nowy w **Konfiguruj** przy wpisie.
- **Zgłaszanie problemu.** Otwórz wpis integracji, użyj *Pobierz diagnostykę* i dołącz plik do zgłoszenia: pokazuje wpis i stan rozkładu, a klucz lub token jest zastąpiony przez `**REDACTED**`.
- **Dane wyglądają na nieaktualne podczas awarii.** Przekroczenie czasu, błąd sieci lub błąd serwera (HTTP 5xx) po udanym wczytaniu **nie** sprawia, że sensor staje się `unavailable`: zachowuje ostatni rozkład i próbuje co godzinę, bo rozkład to dane planowe, które nie zmieniają się w ciągu doby. Sensor diagnostyczny **Last update** (domyślnie wyłączony; włącz go w ustawieniach encji) pokazuje, kiedy dane ostatnio pobrano z powodzeniem.
- **Kreator mówi, że nie znaleziono linii.** API wymienia tylko linie kursujące dziś. Linii, która dziś nie kursuje (na przykład linii tylko robocze w niedzielę), nie da się dodać, dopóki nie dojdzie do dnia jej kursowania.
- **Linii z wtp.waw.pl tu brakuje.** Planer podróży ma więcej danych niż publiczne API. Tego nie da się naprawić w integracji.
- **Linie nocne** (`N01`, `N44` ...): miasto liczy całą noc do poprzedniej doby kursowej, więc autobus o `24:50` lub `26:20` jest jeszcze w rozkładzie tej doby. Integracja czyta te godziny poprawnie, więc odjazd o `02:15` (`26:15` w API) o 02:00 jest pokazany jako za 15 minut.

---

## 📚 Dokumentacja

[Wiki](https://github.com/solarssk/ztm_warsaw/wiki) to podręcznik użytkownika: instalacja, konfiguracja, jak działają rozkład i doba kursowa oraz rozwiązywanie problemów. Jest publikowane z [`docs/wiki/`](docs/wiki) w tym repozytorium (po angielsku).

---

## 🧑‍💻 Współpraca i bezpieczeństwo

Pomysły, zgłoszenia błędów i pull requesty są mile widziane: zob. [CONTRIBUTING.md](CONTRIBUTING.md). Aby zgłosić lukę w zabezpieczeniach, zob. [SECURITY.md](SECURITY.md).

---

## 🙌 Dane i podziękowania

Dane: Miasto Stołeczne Warszawa i Zarząd Transportu Miejskiego (ZTM), z portalu otwartych danych miasta ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), na licencji [Creative Commons Uznanie autorstwa](https://creativecommons.org/licenses/by/4.0/deed.pl).

Ten projekt został w całości zaplanowany i zaprojektowany przeze mnie, od koncepcji i oczekiwanego działania integracji po sposób, w jaki współpracuje z publicznym API miasta Warszawy. Nie jestem zawodowym programistą Pythona, ale rozumiem podstawy na tyle, by określić strukturę, logikę i funkcje, które integracja miała oferować.

Do realizacji użyłem wsparcia AI, które pomagało mi głównie ze składnią, debugowaniem i szczegółami implementacji. Ogólny projekt, zachowanie i przepływ pracy wyszły jednak z mojej strony.

Specjalne podziękowania dla [@peetereczek](https://github.com/peetereczek/ztm), którego wcześniejszy projekt zainspirował mnie na początku. Choć ta wersja powstała od zera, samodzielnie, jego praca dała mi pierwszy impuls, by podejść do rzeczy po swojemu.

Jeśli chcesz ulepszyć lub rozszerzyć projekt, śmiało! Wkład, pomysły i pull requesty są zawsze mile widziane.

---

## 📄 Licencja

Licencja MIT
