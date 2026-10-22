<h1 align="center">🚍 ZTM Varsovie pour Home Assistant</h1>

<p align="center">
  <strong>Les horaires des transports publics de Varsovie dans Home Assistant.<br>Les prochains départs dans vos tableaux de bord et automatisations. Configuration sans YAML.</strong>
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
  🇩🇪 <a href="README.de.md">Deutsch</a>
  &nbsp;·&nbsp;
  🇪🇸 <a href="README.es.md">Español</a>
  &nbsp;·&nbsp;
  🇫🇷 <strong>Français</strong>
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
<summary><strong>Sommaire</strong></summary>

- [Fonctionnalités](#-fonctionnalités)
- [Captures d’écran](#-captures-décran)
- [Prérequis](#-prérequis)
- [Obtenir une clé ou un jeton](#-obtenir-une-clé-ou-un-jeton)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Dépannage](#-dépannage)
- [Documentation](#-documentation)
- [Contribuer et sécurité](#-contribuer-et-sécurité)
- [Données et remerciements](#-données-et-remerciements)
- [Licence](#-licence)

</details>

Affiche **l’heure du prochain bus, tramway ou train à votre arrêt** : un capteur pour une ligne à un point d’arrêt, pour votre tableau de bord et pour des automatisations comme « dis-moi quand partir ». Il utilise les données ouvertes de la ville de Varsovie et n’a besoin d’aucun matériel supplémentaire.

Il affiche des départs **prévus** : pas de retards ni d’alertes de perturbation, seulement la journée de service en cours, et pas de calcul d’itinéraire (pour cela, voir [wtp.waw.pl](https://wtp.waw.pl)). Le véhicule du prochain départ peut s’afficher sur la carte (facultatif, il faut un jeton).

---

## 🔧 Fonctionnalités

- ✅ Bus, tramways, métro et trains urbains (SKM), y compris les lignes de nuit, express et locales.
- ✅ Le prochain départ est l’état du capteur ; les trois suivants, ainsi que le premier et le dernier départ de la journée, sont des attributs.
- ✅ Un capteur *État* dit en mots simples ce qui se passe (« Le dernier départ de la journée est passé »).
- ✅ Configuration en cherchant le nom de l’arrêt, puis en choisissant le point d’arrêt et la ligne : aucun numéro à chercher.
- ✅ Plusieurs lignes et arrêts, un temps de marche facultatif, un calendrier facultatif et un repère facultatif du véhicule sur la carte.
- ✅ Huit langues : anglais, polonais, ukrainien, russe, allemand, espagnol, français et italien. Les six plus récentes sont traduites automatiquement ; les corrections sont les bienvenues sous forme de pull request.

---

## 📸 Captures d’écran

### Configuration de l’intégration
*Le formulaire de configuration des identifiants d’accès, de la ligne et de l’arrêt.*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Aspect de l’entité

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Attributs
*Les détails des horaires, notamment les heures de départ et le sens de circulation.*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Prérequis

- Home Assistant 2026.1 ou plus récent
- Une clé API ou un jeton de la ville de Varsovie (ci-dessous)

---

## 🧭 Obtenir une clé ou un jeton

Obtenez un jeton gratuit sur [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) : saisissez un pseudo, acceptez les conditions et téléchargez-le. C’est un long texte en trois parties séparées par des points.

Une ancienne clé API (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, de [api.um.warszawa.pl](https://api.um.warszawa.pl)) fonctionne encore, mais ce serveur ne répond parfois plus, la ville n’a annoncé aucune date d’arrêt et le véhicule sur la carte demande un jeton. Pour changer, ouvrez l’avis dans **Corrections** ou choisissez **Configurer** sur la ligne, puis collez le jeton. Vos réglages sont conservés.

---

## 📦 Installation

### Avec HACS

1. Dans Home Assistant, allez dans **HACS → Intégrations**.
2. Recherchez **Transports publics de Varsovie**.
3. Cliquez sur **Télécharger** et confirmez.
4. Redémarrez Home Assistant.

### Manuellement

1. Téléchargez la dernière version depuis [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Copiez le dossier `ztm_warsaw` dans `/config/custom_components/`.
3. Redémarrez Home Assistant.

---

## 🔌 Configuration

1. Allez dans **Paramètres → Appareils et services**.
2. Cliquez sur **+ Ajouter une intégration** et cherchez **Transports publics de Varsovie**.
3. Collez votre jeton et saisissez une partie du nom de l’arrêt (par exemple `Marcelin`) ou son ID.
4. Choisissez le point d’arrêt (son numéro figure sur le panneau, un par sens) et la ligne. Seules les lignes qui s’y arrêtent aujourd’hui sont proposées.

Le capteur s’appelle par exemple `sensor.line_151_from_7009_01`. Ajoutez un autre arrêt de la ligne avec **Ajouter un arrêt**. Si vous connaissez déjà les numéros, cochez **Je connais les numéros** sur le premier écran. Le temps de marche, le calendrier, le repère du véhicule et la suppression d’une ligne sont décrits dans le [wiki](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration).

---

## 🩺 Dépannage

- **Le capteur est à `unknown` et affiche « No service ».** La ligne ne circule pas aujourd’hui, ou son dernier départ est passé. C’est normal. Le capteur *État* dit lequel des deux ; l’horaire est sur [wtp.waw.pl](https://wtp.waw.pl), ou appelez le 19115.
- **Le capteur est à `unavailable`.** La ville n’a pas renvoyé d’horaire valide : un jeton refusé, ou un arrêt, un point d’arrêt ou une ligne qu’elle ne connaît pas. La raison est dans le journal de Home Assistant (les clés et les jetons n’y figurent jamais).
- **Erreurs réseau, avec une ancienne clé.** L’ancien serveur de la ville ne répond parfois plus. Les capteurs gardent l’horaire qu’ils ont et redemandent plus tard ; passer à un jeton règle le problème.
- **Home Assistant demande une nouvelle clé.** La ville a refusé la clé trois fois de suite. Saisissez une nouvelle clé ou un nouveau jeton dans le formulaire ; vos réglages sont conservés.
- **Signaler un problème.** Choisissez *Télécharger les diagnostics* sur l’entrée et joignez le fichier à votre ticket. La clé ou le jeton y est remplacé par `**REDACTED**`.

D’autres réponses se trouvent dans le [wiki](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting).

---

## 📚 Documentation

Le [wiki](https://github.com/solarssk/ztm_warsaw/wiki) est le manuel d’utilisation : [Configuration](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration) (temps de marche, supprimer une ligne), [Concepts](https://github.com/solarssk/ztm_warsaw/wiki/2.-Concepts) (la journée de service, ce que montre chaque entité), [Exemples](https://github.com/solarssk/ztm_warsaw/wiki/3.-Examples) (cartes et automatisations à copier) et [Dépannage](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting). Il est en anglais ; les sources sont dans [`docs/wiki/`](docs/wiki).

---

## 🧑‍💻 Contribuer et sécurité

Les idées, signalements de bugs et pull requests sont les bienvenus. Les consignes de contribution figurent dans [CONTRIBUTING.md](CONTRIBUTING.md). Pour signaler une vulnérabilité, suivez les instructions de [SECURITY.md](SECURITY.md).

---

## 🙌 Données et remerciements

Données : la ville de Varsovie (**Miasto Stołeczne Warszawa**) et l’autorité des transports publics de Varsovie (**Zarząd Transportu Miejskiego**, ZTM), via le portail de données ouvertes de la ville ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), sous licence [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/deed.fr).

J’ai conçu le principe, les fonctionnalités, la structure et la connexion à l’API publique de la ville de Varsovie. Je ne suis pas développeur Python professionnel, mais mes connaissances de base m’ont permis de définir le fonctionnement du projet.

J’ai utilisé ChatGPT pour m’aider avec la syntaxe, le débogage et les détails de l’implémentation. J’ai pris moi-même les décisions concernant la conception et le fonctionnement du projet.

Merci à [@peetereczek](https://github.com/peetereczek/ztm), dont le projet précédent m’a inspiré. Cette intégration a été créée de toutes pièces comme un projet indépendant.

Vous pouvez contribuer au projet en proposant des idées, en signalant des bugs ou en soumettant des améliorations.

---

## 📄 Licence

Licence MIT
