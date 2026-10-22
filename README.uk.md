<h1 align="center">🚍 ZTM Варшава для Home Assistant</h1>

<p align="center">
  <strong>Розклади громадського транспорту Варшави в Home Assistant.<br>Найближчі відправлення на панелях і в автоматизаціях. Налаштування без YAML.</strong>
</p>

<p align="center">
  🇬🇧 <a href="README.md">English</a>
  &nbsp;·&nbsp;
  🇵🇱 <a href="README.pl.md">Polski</a>
  &nbsp;·&nbsp;
  🇺🇦 <strong>Українська</strong>
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
<summary><strong>Зміст</strong></summary>

- [Можливості](#-можливості)
- [Скріншоти](#-скріншоти)
- [Вимоги](#-вимоги)
- [Як отримати ключ або токен](#-як-отримати-ключ-або-токен)
- [Встановлення](#-встановлення)
- [Налаштування](#-налаштування)
- [Вирішення проблем](#-вирішення-проблем)
- [Документація](#-документація)
- [Участь і безпека](#-участь-і-безпека)
- [Дані та подяки](#-дані-та-подяки)
- [Ліцензія](#-ліцензія)

</details>

Показує, **коли відправиться найближчий автобус, трамвай чи потяг із вашої зупинки**: один сенсор для маршруту на місці посадки, для панелі та автоматизацій на кшталт «скажи мені, коли виходити». Користується відкритими даними міста Варшави й не потребує додаткового обладнання.

Показує **заплановані** відправлення: без затримок і повідомлень про порушення руху, лише поточну розкладову добу й без планування подорожей (для цього є [wtp.waw.pl](https://wtp.waw.pl)). Транспорт найближчого відправлення можна показати на мапі (необов’язково, потрібен токен).

---

## 🔧 Можливості

- ✅ Автобуси, трамваї, метро та міська електричка (SKM), зокрема нічні, експресні й місцеві маршрути.
- ✅ Станом сенсора є найближче відправлення; наступні три, а також перше й останнє відправлення доби є атрибутами.
- ✅ Сенсор *Статус* простими словами пояснює, що відбувається («Останнє відправлення сьогодні вже було»).
- ✅ Налаштування через пошук зупинки за назвою, потім вибір місця посадки й маршруту: нічого не треба шукати за номерами.
- ✅ Кілька маршрутів і зупинок, необов’язковий час дороги пішки, необов’язковий календар і необов’язкова позначка транспорту на мапі.
- ✅ Вісім мов: англійська, польська, українська, російська, німецька, іспанська, французька та італійська. Шість новіших перекладено машинно; виправлення вітаються як pull request.

---

## 📸 Скріншоти

### Налаштування інтеграції
*Форма налаштування даних доступу, маршруту та зупинки.*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Вигляд сутності

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Атрибути
*Дані розкладу, зокрема час відправлення та напрямок руху.*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Вимоги

- Home Assistant 2026.1 або новіший
- Ключ API або токен від міста Варшави (нижче)

---

## 🧭 Як отримати ключ або токен

Безкоштовний токен можна отримати на [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api): введіть будь-який псевдонім, прийміть умови й завантажте токен. Це довгий текст із трьох частин, розділених крапками.

Старий ключ API (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, з [api.um.warszawa.pl](https://api.um.warszawa.pl)) ще працює, але цей сервер іноді не відповідає, місто не оголосило дати його вимкнення, а транспорт на мапі потребує токена. Щоб перейти на токен, відкрийте сповіщення у **Виправленні проблем** або виберіть **Налаштувати** біля маршруту й вставте токен. Ваші налаштування збережуться.

---

## 📦 Встановлення

### Через HACS

1. У Home Assistant відкрийте **HACS → Інтеграції**.
2. Знайдіть **Громадський транспорт Варшави**.
3. Натисніть **Завантажити** й підтвердьте.
4. Перезапустіть Home Assistant.

### Вручну

1. Завантажте останню версію з [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Скопіюйте теку `ztm_warsaw` до `/config/custom_components/`.
3. Перезапустіть Home Assistant.

---

## 🔌 Налаштування

1. Відкрийте **Налаштування → Пристрої та сервіси**.
2. Натисніть **+ Додати інтеграцію** й знайдіть **Громадський транспорт Варшави**.
3. Вставте токен і введіть частину назви зупинки (наприклад, `Marcelin`) або її ID.
4. Виберіть місце посадки (номер указано на табличці зупинки, для кожного напрямку свій) і маршрут. У списку лише маршрути, що сьогодні там зупиняються.

Сенсор матиме назву на кшталт `sensor.line_151_from_7009_01`. Іншу зупинку цього маршруту додайте через **Додати зупинку**. Якщо знаєте номери, позначте **Я знаю номери** на першому екрані. Про час дороги пішки, календар, позначку транспорту й видалення маршруту читайте у [вікі](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration).

---

## 🩺 Вирішення проблем

- **Сенсор у стані `unknown` і показує «No service».** Маршрут сьогодні не курсує або його останнє відправлення вже було. Це нормально. Який це випадок, підкаже сенсор *Статус*; розклад є на [wtp.waw.pl](https://wtp.waw.pl), можна й зателефонувати на 19115.
- **Сенсор у стані `unavailable`.** Місто не повернуло коректного розкладу: токен відхилено або зупинка, місце посадки чи маршрут йому невідомі. Причину видно в журналі Home Assistant (ключі й токени туди ніколи не потрапляють).
- **Помилки мережі, а ви маєте старий ключ.** Старий сервер міста іноді не відповідає. Сенсори зберігають наявний розклад і запитують знову пізніше; перехід на токен усуває проблему.
- **Home Assistant просить новий ключ.** Місто тричі поспіль відхилило ключ. Введіть новий ключ або токен у формі; налаштування збережуться.
- **Повідомлення про проблему.** Виберіть біля запису *Завантажити діагностику* й додайте файл до звернення. Ключ або токен у ньому замінено на `**REDACTED**`.

Більше відповідей є у [вікі](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting).

---

## 📚 Документація

[Вікі](https://github.com/solarssk/ztm_warsaw/wiki) — це посібник користувача: [Налаштування](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration) (час дороги пішки, видалення маршруту), [Поняття](https://github.com/solarssk/ztm_warsaw/wiki/2.-Concepts) (розкладова доба, що показує кожна сутність), [Приклади](https://github.com/solarssk/ztm_warsaw/wiki/3.-Examples) (картки й автоматизації для копіювання) та [Вирішення проблем](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting). Воно англійською; вихідні файли лежать у [`docs/wiki/`](docs/wiki).

---

## 🧑‍💻 Участь і безпека

Ви можете пропонувати ідеї, повідомляти про помилки й надсилати pull request. Правила участі наведено в [CONTRIBUTING.md](CONTRIBUTING.md). Про вразливості повідомляйте за інструкцією в [SECURITY.md](SECURITY.md).

---

## 🙌 Дані та подяки

Дані: Місто Варшава (**Miasto Stołeczne Warszawa**) та Управління міського транспорту Варшави (**Zarząd Transportu Miejskiego**, ZTM) через портал відкритих даних міста ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)) за ліцензією [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/deed.uk).

Я сам розробив концепцію, функції, структуру інтеграції та спосіб роботи з публічним API міста Варшави. Я не професійний розробник Python, але базові знання дали мені змогу спланувати роботу проєкту.

ChatGPT допомагав мені із синтаксисом, пошуком помилок і деталями реалізації. Рішення щодо структури та роботи проєкту я ухвалював сам.

Дякую [@peetereczek](https://github.com/peetereczek/ztm), чий попередній проєкт став для мене джерелом натхнення. Цю інтеграцію створено з нуля як незалежний проєкт.

Запрошую долучатися до розвитку проєкту: пропонувати ідеї, повідомляти про помилки та надсилати вдосконалення.

---

## 📄 Ліцензія

Ліцензія MIT
