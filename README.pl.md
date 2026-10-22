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

Pokazuje, **kiedy odjedzie najbliższy autobus, tramwaj lub pociąg z Twojego przystanku**: jeden sensor dla linii na słupku, do pulpitu i do automatyzacji, na przykład „powiedz mi, kiedy wyjść”. Korzysta z otwartych danych m.st. Warszawy i nie wymaga żadnego dodatkowego sprzętu.

Pokazuje **planowane** odjazdy: bez opóźnień i utrudnień, tylko bieżącą dobę rozkładową i bez planowania podróży (do tego służy [wtp.waw.pl](https://wtp.waw.pl)). Pojazd najbliższego odjazdu można pokazać na mapie (opcjonalnie, wymaga tokenu).

---

## 🔧 Funkcje

- ✅ Autobusy, tramwaje, metro i SKM, także linie nocne, ekspresowe i lokalne.
- ✅ Stanem sensora jest najbliższy odjazd; trzy kolejne oraz pierwszy i ostatni odjazd doby są w atrybutach.
- ✅ Sensor *Status* mówi zwykłymi słowami, co się dzieje („Ostatni odjazd dzisiaj już był”).
- ✅ Konfiguracja przez wyszukanie przystanku po nazwie, potem wybór słupka i linii: nie trzeba szukać żadnych numerów.
- ✅ Wiele linii i przystanków, opcjonalny czas dojścia, opcjonalny kalendarz i opcjonalna pinezka pojazdu na mapie.
- ✅ Osiem języków: angielski, polski, ukraiński, rosyjski, niemiecki, hiszpański, francuski i włoski. Sześć nowszych przetłumaczono maszynowo; poprawki mile widziane jako pull requesty.

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

Bezpłatny token pobierzesz na stronie [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api): wpisz dowolny pseudonim, zaakceptuj regulamin i pobierz token. To długi tekst z trzech części oddzielonych kropkami.

Stary klucz API (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, ze strony [api.um.warszawa.pl](https://api.um.warszawa.pl)) nadal działa, ale ten serwer bywa nieczynny, miasto nie podało terminu jego wyłączenia, a pojazd na mapie wymaga tokenu. Aby przejść na token, otwórz powiadomienie w **Problemach** albo wybierz **Konfiguruj** przy linii i wklej token. Twoje ustawienia zostaną zachowane.

---

## 📦 Instalacja

### Przez HACS

1. W Home Assistancie otwórz **HACS → Integracje**.
2. Wyszukaj **Warszawski Transport Publiczny**.
3. Kliknij **Pobierz** i potwierdź.
4. Uruchom ponownie Home Assistanta.

### Ręcznie

1. Pobierz najnowszą wersję z [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Skopiuj folder `ztm_warsaw` do `/config/custom_components/`.
3. Uruchom ponownie Home Assistanta.

---

## 🔌 Konfiguracja

1. Przejdź do **Ustawienia → Urządzenia oraz usługi**.
2. Kliknij **+ Dodaj integrację** i wyszukaj **Warszawski Transport Publiczny**.
3. Wklej token i wpisz fragment nazwy przystanku (na przykład `Marcelin`) albo jego ID.
4. Wybierz słupek (numer jest na tabliczce przystanku, każdy kierunek ma swój) i linię. Na liście są tylko linie, które dziś tam zatrzymują się.

Sensor ma nazwę w rodzaju `sensor.line_151_from_7009_01`. Kolejny przystanek tej linii dodasz przez **Dodaj przystanek**. Jeśli znasz numery, zaznacz **Znam numery** na pierwszym ekranie. Czas dojścia, kalendarz, pinezkę pojazdu i usuwanie linii opisuje [wiki](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration).

---

## 🩺 Rozwiązywanie problemów

- **Sensor ma stan `unknown` i pokazuje „No service”.** Linia dziś nie kursuje albo jej ostatni odjazd już był. To normalne. Który to przypadek, mówi sensor *Status*; rozkład jest na [wtp.waw.pl](https://wtp.waw.pl), można też zadzwonić pod 19115.
- **Sensor ma stan `unavailable`.** Miasto nie zwróciło poprawnego rozkładu: odrzucony token albo przystanek, słupek lub linia, których nie zna. Przyczyna jest w logu Home Assistanta (klucze i tokeny nigdy tam nie trafiają).
- **Błędy sieci, a masz stary klucz.** Stary serwer miasta bywa nieczynny. Sensory zachowują rozkład, który mają, i pytają ponownie później; przejście na token rozwiązuje problem.
- **Home Assistant prosi o nowy klucz.** Miasto trzy razy z rzędu odrzuciło klucz. Wpisz nowy klucz lub token w formularzu; ustawienia zostaną zachowane.
- **Zgłaszanie problemu.** Wybierz przy wpisie *Pobierz diagnostykę* i dołącz plik do zgłoszenia. Klucz lub token jest w nim zastąpiony napisem `**REDACTED**`.

Więcej odpowiedzi jest w [wiki](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting).

---

## 📚 Dokumentacja

[Wiki](https://github.com/solarssk/ztm_warsaw/wiki) to instrukcja obsługi: [Konfiguracja](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration) (czas dojścia, usuwanie linii), [Pojęcia](https://github.com/solarssk/ztm_warsaw/wiki/2.-Concepts) (doba rozkładowa, co pokazuje każda encja), [Przykłady](https://github.com/solarssk/ztm_warsaw/wiki/3.-Examples) (karty i automatyzacje do skopiowania) i [Rozwiązywanie problemów](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting). Jest po angielsku; źródło leży w [`docs/wiki/`](docs/wiki).

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
