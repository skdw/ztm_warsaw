<h1 align="center">🚍 ZTM Warszawa w Home Assistancie</h1>

<p align="center">
  <strong>Rozkłady jazdy warszawskiej komunikacji miejskiej w Home Assistancie.<br>Najbliższe odjazdy na pulpicie i w automatyzacjach. Konfiguracja bez YAML-a.</strong>
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

Integracja wyświetla **planowane odjazdy** warszawskiej komunikacji miejskiej na podstawie otwartych danych m.st. Warszawy. Każdy sensor pokazuje odjazdy jednej linii z wybranego słupka przystankowego. Możesz umieścić je na pulpicie Home Assistanta lub wykorzystać w automatyzacjach, np. do przypomnienia o wyjściu z domu przed odjazdem autobusu.

Dane pochodzą z rozkładu jazdy. Integracja ma następujące ograniczenia:

- nie pokazuje opóźnień, utrudnień ani bieżącej pozycji pojazdów — korzysta z planowanych odjazdów, aktualizowanych w API raz na dobę;
- udostępnia rozkład tylko na bieżącą dobę — publiczne API nie zwraca rozkładów na inne dni;
- nie planuje tras ani przesiadek — do tego służy [wtp.waw.pl](https://wtp.waw.pl).

---

## 🔧 Funkcje

- ✅ Obsługa autobusów, tramwajów, metra i SKM, w tym linii nocnych, cmentarnych, ekspresowych i lokalnych.
- ✅ Możliwość dodania wielu linii i przystanków.
- ✅ Godzina najbliższego odjazdu jako stan sensora, dostępna na pulpicie i w automatyzacjach. Trzy kolejne odjazdy są zapisane w atrybutach (`Next 1`–`Next 3`).
- ✅ Informacja „No service”, gdy nie ma już odjazdów, oraz stan `unavailable`, gdy nie można uzyskać poprawnego rozkładu (zob. [Rozwiązywanie problemów](#-rozwiązywanie-problemów)).
- ✅ Konfiguracja w interfejsie Home Assistanta w ośmiu językach: angielskim, polskim, ukraińskim, rosyjskim, niemieckim, hiszpańskim, francuskim i włoskim. Sześć nowych wersji językowych przygotowano maszynowo; propozycje poprawek można zgłaszać w pull requestach.
- ✅ Nazwa i współrzędne przystanku, kierunek jazdy, link do rozkładu oraz uwagi w atrybutach sensora. Współrzędne pozwalają wyświetlić przystanek na mapie.
- ✅ Możliwość zmiany klucza API lub tokenu za pomocą przycisku **Konfiguruj**, również przy przejściu na nowe API miasta.
- ✅ Osobna encja **kalendarza** dla każdego sensora, domyślnie wyłączona. Po włączeniu jej w ustawieniach encji zobaczysz odjazdy z danej doby jako jednominutowe wydarzenia. Wyzwalacz kalendarza pozwala uruchomić automatyzację np. osiem minut przed odjazdem, bez tworzenia szablonów.

---

## 📸 Zrzuty ekranu

### Konfiguracja integracji
*Formularz z danymi dostępu, linią i przystankiem.*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Wygląd encji

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Atrybuty
*Szczegóły rozkładu, w tym godziny odjazdów i kierunek jazdy.*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Wymagania

- Home Assistant 2026.1 lub nowszy
- Klucz API lub token z portalu danych miasta (opis poniżej)

---

## 🧭 Klucz i token

Integracja obsługuje dane dostępu do obu API m.st. Warszawy:

- **Token do nowego API (zalecany):** na stronie [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) podaj pseudonim, zaakceptuj regulamin i pobierz swój token. To długi ciąg znaków z trzech części oddzielonych kropkami.
- **Klucz do starego API:** klucz ze strony [api.um.warszawa.pl](https://api.um.warszawa.pl) wygląda tak: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Stare API nadal działa, ale miasto nie ogłosiło terminu jego wyłączenia. Zalecamy przejście na nowe API.

Integracja rozpoznaje rodzaj danych dostępu i wysyła je wyłącznie do odpowiedniego API. Aby zastąpić stary klucz tokenem, wybierz **Konfiguruj** przy danej linii i wklej token. Ustawienia linii i przystanków zostaną zachowane. Nie trzeba dodawać integracji ponownie — kreator nie pozwoli drugi raz dodać tej samej linii dla tego samego słupka przystankowego.

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

1. Otwórz **Ustawienia → Urządzenia i usługi**.
2. Kliknij **+ Dodaj integrację** i wyszukaj **Warsaw Public Transport**.
3. Wypełnij pola:
   - **klucz API lub token** (zob. [Klucz i token](#-klucz-i-token)),
   - **ID przystanku** i **numer słupka** (np. 7009 i 01),
   - **numer linii** (np. 151).

Identyfikator encji zawiera numer linii, ID przystanku i numer słupka, np. `sensor.line_151_from_7009_01`. Klucz API lub token możesz zmienić w **Ustawienia → Urządzenia i usługi → Warsaw Public Transport**, wybierając **Konfiguruj** przy danej linii. Zmiana nie wpływa na ustawienia linii ani przystanków. Jeśli konfiguracja nadal korzysta ze starego klucza, w sekcji **Naprawy** pojawi się powiadomienie z instrukcją przejścia na token. Możesz je zignorować.

**ID przystanku** (numer zespołu przystankowego) jest wspólne dla wszystkich słupków należących do tego przystanku. **Numer słupka** wskazuje konkretne miejsce odjazdu, zwykle dla jednego kierunku. Ma zazwyczaj dwie cyfry, np. 01 lub 02, i znajduje się na tabliczce przystankowej.

---

## 🩺 Rozwiązywanie problemów

- **Sensor ma stan `unknown`, a w atrybutach widnieje „No service”.** Linia nie kursuje w danym dniu lub wszystkie odjazdy już się odbyły. Jest to prawidłowe działanie. Rozkład możesz sprawdzić na [wtp.waw.pl](https://wtp.waw.pl) lub pod numerem 19115.
- **Sensor ma stan `unavailable` (niedostępny).** API nie zwróciło poprawnego rozkładu. Przyczyną może być odrzucony klucz, nieprawidłowy numer przystanku, słupka lub linii albo nieobsługiwany format odpowiedzi. Jeśli nie powiedzie się pierwsze pobranie danych z przyczyny innej niż odrzucenie klucza, Home Assistant automatycznie ponowi konfigurację. Sposób obsługi odrzuconego klucza opisano poniżej. Szczegóły błędu znajdziesz w dzienniku Home Assistanta; klucze i tokeny nie są w nim zapisywane. Sensor odzyska dostępność po otrzymaniu poprawnych danych. Jeśli problem się utrzymuje, sprawdź dane dostępu, przystanek, słupek i linię.
- **Home Assistant prosi o nowy klucz.** Dzieje się tak, gdy stare API odrzuci klucz trzy razy z rzędu. Uwzględniane są również próby podczas konfiguracji; błąd sieci lub serwera przerywa tę serię. Podaj nowy klucz API lub token w wyświetlonym formularzu. Ustawienia linii i przystanków zostaną zachowane, a poprawny klucz zostanie zaakceptowany również wtedy, gdy linia nie kursuje w danym dniu. Do czasu zmiany danych dostępu sensor pozostaje niedostępny. W nowym API nie można odróżnić odrzuconego tokenu od awarii usługi. Jeśli rozkład został wcześniej pobrany, sensor korzysta z niego do końca doby, a potem staje się niedostępny. Formularz zmiany danych dostępu nie pojawi się automatycznie. Jeśli token został unieważniony, podaj nowy za pomocą przycisku **Konfiguruj** przy danej linii.
- **Zgłaszanie problemu.** Otwórz konfigurację danej linii, wybierz *Pobierz diagnostykę* i dołącz plik do zgłoszenia. Plik zawiera informacje o konfiguracji i rozkładzie. Klucz API lub token jest w nim zastąpiony tekstem `**REDACTED**`.
- **Sensor nadal pokazuje odjazdy mimo awarii API.** Po udanym pobraniu rozkładu przekroczenie czasu oczekiwania, błąd sieci lub błąd serwera (HTTP 5xx) nie powoduje od razu utraty dostępności sensora. Integracja korzysta z zapisanego rozkładu do końca doby i ponawia pobieranie co godzinę. Rozkład zawiera planowane odjazdy, które nie zmieniają się w ciągu dnia. Czas ostatniego udanego pobrania wskazuje sensor diagnostyczny **Last update**, który można włączyć w ustawieniach encji.
- **Podczas konfiguracji pojawia się komunikat o braku linii.** API udostępnia tylko linie kursujące w danym dniu. Jeśli linia kursuje wyłącznie w dni robocze, nie dodasz jej w niedzielę. Spróbuj ponownie w dniu, w którym ma zaplanowane odjazdy.
- **Linia jest dostępna na wtp.waw.pl, ale nie w integracji.** Planer podróży korzysta z szerszego zestawu danych niż publiczne API. Integracja może wyświetlić tylko dane udostępnione przez API.
- **Godziny odjazdów linii nocnych** (`N01`, `N44` itd.). W rozkładzie doba może trwać dłużej niż do północy: zapis `24:50` oznacza 00:50 następnego dnia, a `26:20` — 02:20. Integracja prawidłowo przelicza te godziny. Na przykład odjazd zapisany w API jako `26:15` oznacza 02:15 następnego dnia; o 02:00 zostanie wyświetlony jako odjazd za 15 minut.

---

## 📚 Dokumentacja

[Podręcznik w wiki](https://github.com/solarssk/ztm_warsaw/wiki) zawiera instrukcje instalacji i konfiguracji, wyjaśnienie sposobu obsługi rozkładów i doby rozkładowej oraz pomoc w rozwiązywaniu problemów. Dokumentacja jest dostępna po angielsku, a jej pliki źródłowe znajdują się w katalogu [`docs/wiki/`](docs/wiki).

---

## 🧑‍💻 Współpraca i bezpieczeństwo

Chcesz zgłosić błąd, zaproponować funkcję lub przesłać poprawkę? Zasady współpracy znajdziesz w [CONTRIBUTING.md](CONTRIBUTING.md). Luki w zabezpieczeniach zgłaszaj zgodnie z instrukcją w [SECURITY.md](SECURITY.md).

---

## 🙌 Dane i podziękowania

Dane: Miasto Stołeczne Warszawa i Zarząd Transportu Miejskiego (ZTM), z portalu otwartych danych ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), na licencji [Creative Commons Uznanie autorstwa](https://creativecommons.org/licenses/by/4.0/deed.pl).

Sam opracowałem koncepcję integracji, jej funkcje, strukturę i sposób korzystania z publicznego API Warszawy. Nie jestem zawodowym programistą Pythona, ale znajomość jego podstaw pozwoliła mi zaplanować działanie projektu.

Podczas pisania kodu korzystałem z pomocy ChatGPT, przede wszystkim przy składni, diagnozowaniu błędów i szczegółach implementacji. Decyzje dotyczące projektu i jego działania podejmowałem sam.

Dziękuję [@peetereczek](https://github.com/peetereczek/ztm), którego wcześniejszy projekt był dla mnie inspiracją. Ta integracja powstała od podstaw jako niezależny projekt.

Zapraszam do rozwijania projektu — zgłaszania pomysłów, błędów i propozycji poprawek.

---

## 📄 Licencja

Licencja MIT
