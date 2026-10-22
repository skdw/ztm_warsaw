<h1 align="center">🚍 ZTM Варшава для Home Assistant</h1>

<p align="center">
  <strong>Расписания общественного транспорта Варшавы в Home Assistant.<br>Ближайшие отправления на панелях и в автоматизациях. Настройка без YAML.</strong>
</p>

<p align="center">
  🇬🇧 <a href="README.md">English</a>
  &nbsp;·&nbsp;
  🇵🇱 <a href="README.pl.md">Polski</a>
  &nbsp;·&nbsp;
  🇺🇦 <a href="README.uk.md">Українська</a>
  &nbsp;·&nbsp;
  🇷🇺 <strong>Русский</strong>
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
<summary><strong>Содержание</strong></summary>

- [Возможности](#-возможности)
- [Скриншоты](#-скриншоты)
- [Требования](#-требования)
- [Как получить ключ или токен](#-как-получить-ключ-или-токен)
- [Установка](#-установка)
- [Настройка](#-настройка)
- [Решение проблем](#-решение-проблем)
- [Документация](#-документация)
- [Участие и безопасность](#-участие-и-безопасность)
- [Данные и благодарности](#-данные-и-благодарности)
- [Лицензия](#-лицензия)

</details>

Показывает, **когда отправится ближайший автобус, трамвай или поезд с вашей остановки**: один сенсор для маршрута на посадочной площадке, для панели и автоматизаций вроде «скажи мне, когда выходить». Использует открытые данные города Варшавы и не требует дополнительного оборудования.

Показывает **плановые** отправления: без задержек и сообщений о нарушениях движения, только текущие расписательные сутки и без планирования поездок (для этого есть [wtp.waw.pl](https://wtp.waw.pl)). Транспорт ближайшего отправления можно показать на карте (по желанию, нужен токен).

---

## 🔧 Возможности

- ✅ Автобусы, трамваи, метро и городская электричка (SKM), в том числе ночные, экспресс- и местные маршруты.
- ✅ Состояние сенсора — ближайшее отправление; следующие три, а также первое и последнее отправление суток — атрибуты.
- ✅ Сенсор *Статус* простыми словами объясняет, что происходит («Последнее отправление сегодня уже было»).
- ✅ Настройка через поиск остановки по названию, затем выбор посадочной площадки и маршрута: искать номера не нужно.
- ✅ Несколько маршрутов и остановок, необязательное время на дорогу пешком, необязательный календарь и необязательная отметка транспорта на карте.
- ✅ Восемь языков: английский, польский, украинский, русский, немецкий, испанский, французский и итальянский. Шесть новых переведены машинным способом; исправления приветствуются в виде pull request.

---

## 📸 Скриншоты

### Настройка интеграции
*Форма настройки данных доступа, маршрута и остановки.*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Вид сущности

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Атрибуты
*Данные расписания, включая время отправления и направление движения.*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Требования

- Home Assistant 2026.1 или новее
- Ключ API или токен от города Варшавы (ниже)

---

## 🧭 Как получить ключ или токен

Бесплатный токен можно получить на [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api): введите любой псевдоним, примите условия и скачайте токен. Это длинный текст из трёх частей, разделённых точками.

Старый ключ API (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, с [api.um.warszawa.pl](https://api.um.warszawa.pl)) ещё работает, но этот сервер временами не отвечает, город не объявил дату его отключения, а транспорт на карте требует токена. Чтобы перейти на токен, откройте уведомление в разделе **Устранение проблем** или выберите **Настроить** у маршрута и вставьте токен. Ваши настройки сохранятся.

---

## 📦 Установка

### Через HACS

1. В Home Assistant откройте **HACS → Интеграции**.
2. Найдите **Общественный транспорт Варшавы**.
3. Нажмите **Скачать** и подтвердите.
4. Перезапустите Home Assistant.

### Вручную

1. Скачайте последнюю версию с [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Скопируйте папку `ztm_warsaw` в `/config/custom_components/`.
3. Перезапустите Home Assistant.

---

## 🔌 Настройка

1. Откройте **Настройки → Устройства и службы**.
2. Нажмите **+ Добавить интеграцию** и найдите **Общественный транспорт Варшавы**.
3. Вставьте токен и введите часть названия остановки (например, `Marcelin`) или её ID.
4. Выберите посадочную площадку (номер указан на табличке остановки, у каждого направления свой) и маршрут. В списке только маршруты, которые сегодня там останавливаются.

Сенсор получит имя вроде `sensor.line_151_from_7009_01`. Ещё одну остановку этого маршрута добавьте через **Добавить остановку**. Если вы знаете номера, отметьте **Я знаю номера** на первом экране. О времени на дорогу пешком, календаре, отметке транспорта и удалении маршрута читайте в [вики](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration).

---

## 🩺 Решение проблем

- **Сенсор в состоянии `unknown` и показывает «No service».** Маршрут сегодня не ходит или его последнее отправление уже было. Это нормально. Какой это случай, подскажет сенсор *Статус*; расписание есть на [wtp.waw.pl](https://wtp.waw.pl), можно и позвонить по номеру 19115.
- **Сенсор в состоянии `unavailable`.** Город не вернул корректное расписание: токен отклонён либо остановка, посадочная площадка или маршрут ему неизвестны. Причина указана в журнале Home Assistant (ключи и токены туда никогда не попадают).
- **Сетевые ошибки, а у вас старый ключ.** Старый сервер города временами не отвечает. Сенсоры сохраняют имеющееся расписание и позже спрашивают снова; переход на токен решает проблему.
- **Home Assistant просит новый ключ.** Город трижды подряд отклонил ключ. Введите новый ключ или токен в форме; настройки сохранятся.
- **Сообщение о проблеме.** Выберите у записи *Скачать диагностические данные* и приложите файл к обращению. Ключ или токен в нём заменён на `**REDACTED**`.

Больше ответов есть в [вики](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting).

---

## 📚 Документация

[Вики](https://github.com/solarssk/ztm_warsaw/wiki) — руководство пользователя: [Настройка](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration) (время на дорогу пешком, удаление маршрута), [Понятия](https://github.com/solarssk/ztm_warsaw/wiki/2.-Concepts) (расписательные сутки, что показывает каждая сущность), [Примеры](https://github.com/solarssk/ztm_warsaw/wiki/3.-Examples) (карточки и автоматизации для копирования) и [Решение проблем](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting). Оно на английском; исходные файлы лежат в [`docs/wiki/`](docs/wiki).

---

## 🧑‍💻 Участие и безопасность

Вы можете предлагать идеи, сообщать об ошибках и отправлять pull request. Правила участия приведены в [CONTRIBUTING.md](CONTRIBUTING.md). Об уязвимостях сообщайте по инструкции в [SECURITY.md](SECURITY.md).

---

## 🙌 Данные и благодарности

Данные: Город Варшава (**Miasto Stołeczne Warszawa**) и Управление городского транспорта Варшавы (**Zarząd Transportu Miejskiego**, ZTM) через портал открытых данных города ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)) по лицензии [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/deed.ru).

Я сам разработал концепцию, функции, структуру интеграции и способ работы с публичным API города Варшавы. Я не профессиональный разработчик Python, но базовые знания позволили мне спланировать работу проекта.

ChatGPT помогал мне с синтаксисом, поиском ошибок и деталями реализации. Решения о структуре и работе проекта я принимал сам.

Спасибо [@peetereczek](https://github.com/peetereczek/ztm), чей предыдущий проект послужил для меня источником вдохновения. Эта интеграция создана с нуля как независимый проект.

Приглашаю участвовать в развитии проекта: предлагать идеи, сообщать об ошибках и присылать улучшения.

---

## 📄 Лицензия

Лицензия MIT
