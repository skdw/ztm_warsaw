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

L’intégration affiche les **départs prévus** à partir des données ouvertes de la ville de Varsovie. Chaque capteur indique les départs d’une ligne à un point d’arrêt précis. Vous pouvez les afficher dans votre tableau de bord Home Assistant ou les utiliser dans des automatisations, par exemple pour recevoir un rappel avant de partir prendre le bus.

Les données proviennent des horaires publiés. L’intégration présente les limites suivantes :

- pas de retards ni d’alertes de perturbation : l’API fournit des départs prévus, mis à jour une fois par jour. Le véhicule du prochain départ peut s’afficher sur la carte, comme une entité facultative (il faut un jeton, voir le wiki) ;
- les horaires sont disponibles uniquement pour la journée de service en cours : l’API publique ne fournit pas les autres dates ;
- pas de calcul d’itinéraires ni de correspondances : utilisez [wtp.waw.pl](https://wtp.waw.pl) pour cela.

---

## 🔧 Fonctionnalités

- ✅ Bus, tramways, métro et trains SKM, y compris les lignes de nuit, les dessertes des cimetières, les lignes express et locales.
- ✅ Prise en charge de plusieurs lignes et arrêts.
- ✅ L’heure du prochain départ comme état du capteur, utilisable dans les tableaux de bord et les automatisations. Les trois départs suivants sont enregistrés dans les attributs (`Next 1`–`Next 3`).
- ✅ Le message « No service » lorsqu’il ne reste plus de départs, et l’état `unavailable` lorsqu’aucun horaire valide ne peut être obtenu (voir [Dépannage](#-dépannage)).
- ✅ Configuration dans l’interface de Home Assistant en huit langues : anglais, polonais, ukrainien, russe, allemand, espagnol, français et italien. Les six nouvelles versions ont été traduites automatiquement ; les propositions de correction sont les bienvenues sous forme de pull requests.
- ✅ Des attributs avec le nom et les coordonnées de l’arrêt, le sens de circulation, un lien vers les horaires et des remarques. Les coordonnées permettent d’afficher l’arrêt sur une carte.
- ✅ Modification de la clé API ou du jeton via **Configurer**, y compris pour passer à la nouvelle API de la ville.
- ✅ Une entité **calendrier** distincte pour chaque capteur, désactivée par défaut. Une fois activée dans les paramètres de l’entité, elle affiche chaque départ de la journée de service comme un événement d’une minute. Un déclencheur de calendrier permet de lancer une automatisation, par exemple huit minutes avant le départ, sans créer de modèles.

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

L’intégration prend en charge les identifiants d’accès aux deux API de la ville de Varsovie :

- **Jeton pour la nouvelle API (recommandé) :** sur [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api), saisissez un pseudonyme, acceptez les conditions et téléchargez votre jeton. Il s’agit d’une longue chaîne de caractères composée de trois parties séparées par des points.
- **Clé pour l’ancienne API :** une clé de [api.um.warszawa.pl](https://api.um.warszawa.pl) a le format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. L’ancienne API ne répond parfois plus, et la ville n’a pas annoncé de date d’arrêt du service. Nous recommandons de passer à la nouvelle API.

L’intégration reconnaît le type d’identifiant et l’envoie uniquement à l’API correspondante. Pour remplacer une ancienne clé par un jeton, choisissez **Configurer** pour la ligne et collez le jeton. Les réglages de la ligne et des arrêts seront conservés. Il est inutile d’ajouter à nouveau l’intégration : l’assistant refuse les configurations en double pour une même ligne au même point d’arrêt.

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
2. Cliquez sur **+ Ajouter une intégration** et recherchez **Transports publics de Varsovie**.
3. Renseignez :
   - la **clé API ou le jeton** (voir ci-dessus),
   - l’**ID de l’arrêt** et le **numéro du point d’arrêt** (par exemple 7009 et 01),
   - le **numéro de la ligne** (par exemple 151).

L’identifiant de l’entité comprend le numéro de ligne, l’ID de l’arrêt et le numéro du point d’arrêt, par exemple `sensor.line_151_from_7009_01`. Pour modifier la clé API ou le jeton, ouvrez **Paramètres → Appareils et services → Transports publics de Varsovie**, puis choisissez **Configurer** pour la ligne. Les réglages de la ligne et des arrêts seront conservés. Si une ancienne clé est encore utilisée, un avis dans **Corrections** explique comment passer à un jeton. Vous pouvez ignorer cet avis.

L’**ID de l’arrêt** est commun à tous les points d’arrêt appartenant au même arrêt. Le **numéro du point d’arrêt** désigne le lieu précis de montée, généralement pour un sens de circulation. Il comporte habituellement deux chiffres, comme 01 ou 02, et figure sur le panneau de l’arrêt. En polonais, ce point numéroté est appelé *słupek*.

---

## 🩺 Dépannage

- **Le capteur a l’état `unknown` et ses attributs indiquent « No service ».** La ligne ne circule pas aujourd’hui ou tous les départs sont déjà passés. Il s’agit du comportement attendu. Consultez les horaires sur [wtp.waw.pl](https://wtp.waw.pl) ou appelez le 19115.
- **Le capteur a l’état `unavailable` (indisponible).** L’API n’a pas renvoyé d’horaires valides. Cela peut venir d’une clé refusée, d’informations incorrectes sur l’arrêt, le point d’arrêt ou la ligne, ou d’un format de réponse non pris en charge. Si la première récupération échoue pour une autre raison qu’une clé refusée, Home Assistant relance automatiquement la configuration. Le traitement des clés refusées est expliqué ci-dessous. Les détails de l’erreur figurent dans le journal de Home Assistant ; les clés et jetons n’y sont pas enregistrés. Le capteur redevient disponible dès qu’il reçoit des données valides. Si le problème persiste, vérifiez les identifiants d’accès et les informations de l’arrêt et de la ligne.
- **Home Assistant demande une nouvelle clé.** Cela se produit lorsque l’ancienne API refuse la clé trois fois de suite. Les tentatives pendant la configuration sont également comptées ; une erreur réseau ou serveur interrompt cette série. Saisissez une nouvelle clé API ou un jeton dans le formulaire. Les réglages seront conservés et une clé valide sera acceptée même si la ligne ne circule pas ce jour-là. Le capteur reste indisponible jusqu’à la modification des identifiants. La nouvelle API ne permet pas de distinguer un jeton refusé d’une panne du service. Si des horaires ont déjà été téléchargés, le capteur les utilise jusqu’à la fin de la journée de service, puis devient indisponible. Aucun formulaire de modification des identifiants ne s’affiche automatiquement. Si vous avez révoqué le jeton, saisissez-en un nouveau via **Configurer** pour la ligne.
- **Signaler un problème.** Ouvrez la configuration de la ligne, choisissez *Télécharger les diagnostics* et joignez le fichier à votre signalement. Il contient des informations sur la configuration et les horaires. La clé API ou le jeton est remplacé par `**REDACTED**`.
- **Les départs restent affichés pendant une panne de l’API.** Après un téléchargement réussi, un dépassement du délai d’attente, une erreur réseau ou une erreur serveur (HTTP 5xx) ne rend pas immédiatement le capteur indisponible. L’intégration utilise les horaires enregistrés jusqu’à la fin de la journée de service et réessaie toutes les heures. Les départs prévus ne changent pas au cours de la journée. Le capteur de diagnostic **Last update**, désactivé par défaut, indique la dernière récupération réussie. Vous pouvez l’activer dans les paramètres de l’entité.
- **La ligne est introuvable lors de la configuration.** L’API ne fournit que les lignes qui circulent le jour même. Par exemple, une ligne circulant uniquement en semaine ne peut pas être ajoutée un dimanche. Réessayez un jour où des départs sont prévus.
- **Une ligne apparaît sur wtp.waw.pl, mais pas dans l’intégration.** Le calculateur d’itinéraires utilise davantage de données que l’API publique. L’intégration ne peut afficher que les données fournies par l’API.
- **Horaires des lignes de nuit** (`N01`, `N44`, etc.). Une journée de service peut se prolonger après minuit : `24:50` signifie 00 h 50 le lendemain, et `26:20` signifie 02 h 20. L’intégration convertit correctement ces horaires. Un départ enregistré sous la forme `26:15` correspond à 02 h 15 le lendemain ; à 02 h 00, il est affiché comme un départ dans 15 minutes.

---

## 📚 Documentation

Le [manuel utilisateur du wiki](https://github.com/solarssk/ztm_warsaw/wiki) présente l’installation, la configuration, les horaires, la journée de service et le dépannage. Il est disponible en anglais ; ses fichiers source se trouvent dans [`docs/wiki/`](docs/wiki).

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
