<h1 align="center">🚍 ZTM Varsovie pour Home Assistant</h1>

<p align="center">
  <strong>Les prochains départs programmés d’une ligne de bus, tramway, métro ou de nuit de Varsovie, sous forme de capteur.<br>À partir des données ouvertes de la ville. Sans YAML, sans promesse de suivi en direct.</strong>
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

Affiche les prochains **départs programmés** d’une ligne des transports publics de Varsovie (bus, tramway, métro, train urbain ou ligne de nuit) à un poteau d’arrêt sous forme de capteur dans Home Assistant, à partir des données ouvertes de la ville de Varsovie. Utile pour des tableaux de bord et des automatisations comme « pars dans huit minutes », sans ouvrir une application d’horaires.

Il affiche l’**horaire**, pas les véhicules en direct. Ce qu’il **ne** fait **pas** :

- pas de positions en direct, de retards ni de perturbations : la ville publie des départs planifiés, actualisés une fois par jour ;
- pas d’horaires pour d’autres jours : l’API ne fournit que la journée de service en cours ;
- pas de calcul d’itinéraire : pour cela, utilisez [wtp.waw.pl](https://wtp.waw.pl).

---

## 🔧 Fonctionnalités

- ✅ Lignes de bus, de tramway, de métro, de nuit, de cimetière, express et locales.
- ✅ Plusieurs instances : suivez autant d’arrêts et de lignes que vous le souhaitez.
- ✅ Le prochain départ sous forme d’horodatage, utilisable dans l’interface et dans les automatisations, et les trois suivants en attributs (`Next 1` ... `Next 3`).
- ✅ Un état « No service » clair les jours où une ligne ne circule pas, et `unavailable` quand l’API de la ville est en panne (voir [Dépannage](#-dépannage)).
- ✅ Configuration entière dans l’interface de Home Assistant, en anglais, polonais, ukrainien, russe, allemand, espagnol, français ou italien (les textes autres que l’anglais et le polonais sont traduits automatiquement : les corrections sont bienvenues en pull request).
- ✅ Des attributs avec l’arrêt (son nom et sa position, il apparaît donc comme une épingle sur la carte), la direction, un lien vers l’horaire et des remarques.
- ✅ Changez la clé API ou le jeton d’une entrée à tout moment dans **Configurer**, par exemple de l’ancienne API de la ville vers la nouvelle.
- ✅ Une entité **calendrier** par capteur (désactivée par défaut : activez-la dans les paramètres de l’entité) avec chaque départ de la journée comme événement d’une minute : voyez tout l’horaire dans la vue calendrier de Home Assistant et lancez des automatisations avec le déclencheur de calendrier (« 8 minutes avant un départ ») sans modèles.

---

## 📸 Captures d’écran

### Configuration de l’intégration
*Indiquez votre clé API et les informations de l’arrêt...*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Aspect de l’entité

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Attributs
*Exemple d’entité avec des départs et des attributs comme l’heure, la direction...*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Prérequis

- Home Assistant 2026.1 ou plus récent
- Une clé API ou un jeton de la ville de Varsovie (ci-dessous)

---

## 🧭 Obtenir une clé ou un jeton

La ville gère deux portails, et l’intégration accepte la clé de l’un ou de l’autre :

- **Nouveau (recommandé) :** sur [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api), saisissez un pseudo, acceptez les conditions et téléchargez votre propre jeton. C’est un long texte en trois parties séparées par des points.
- **Ancien :** une clé de [api.um.warszawa.pl](https://api.um.warszawa.pl) ressemble à `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Les anciennes clés existantes fonctionnent encore au moment de l’écriture, mais la ville ne donne ni date ni promesse de durée, donc passez à un jeton dès que possible.

L’intégration reconnaît laquelle vous avez collée et ne parle qu’à l’API correspondante. Pour faire passer une entrée existante à un jeton, utilisez **Configurer** sur cette entrée et saisissez le jeton (l’arrêt et la ligne restent) ; n’ajoutez pas une seconde entrée, car deux entrées pour le même arrêt, poteau et ligne ne peuvent pas coexister et l’assistant refuse la seconde.

---

## 📦 Installation

### Avec HACS

1. Dans Home Assistant, allez dans **HACS → Intégrations**.
2. Recherchez **Warsaw Public Transport**.
3. Cliquez sur **Télécharger** et confirmez.
4. Redémarrez Home Assistant.

### Manuellement

1. Téléchargez la dernière version depuis [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Copiez le dossier `ztm_warsaw` dans `/config/custom_components/`.
3. Redémarrez Home Assistant.

---

## 🔌 Configuration

1. Allez dans **Paramètres → Appareils et services**.
2. Cliquez sur **+ Ajouter une intégration** et recherchez **Warsaw Public Transport**.
3. Renseignez :
   - la **clé API ou le jeton** (voir ci-dessus),
   - l’**ID de l’arrêt** et le **numéro du poteau** (par exemple 7009 et 01),
   - le **numéro de la ligne** (par exemple 151).

L’entité porte le nom de l’arrêt et de la ligne, par exemple `sensor.line_151_from_7009_01`. Pour remplacer la clé API ou le jeton d’une entrée (par exemple passer d’une ancienne clé à un jeton), utilisez **Paramètres → Appareils et services → Warsaw Public Transport → Configurer** sur cette entrée ; l’arrêt et la ligne restent. Une entrée qui utilise encore une ancienne clé affiche un avis que l’on peut fermer dans **Paramètres → Réparations**.

**L’ID de l’arrêt et le numéro du poteau** ne sont pas la même chose : l’ID de l’arrêt est commun à tous les poteaux d’un arrêt, et le numéro du poteau (généralement 01, 02, ...) est le numéro peint sur la plaque du poteau (*słupek*). Un arrêt à plusieurs directions a un numéro différent pour chacune.

---

## 🩺 Dépannage

- **L’état est `unknown` et l’attribut indique « No service ».** La ligne ne circule pas aujourd’hui, ou son dernier départ est passé. Ce n’est pas une erreur : consultez [wtp.waw.pl](https://wtp.waw.pl) ou appelez le 19115.
- **Le capteur est `unavailable`.** L’API de la ville a répondu, mais pas avec un horaire : la clé ou le jeton a été refusé, l’arrêt, le poteau et la ligne sont inconnus de l’API, ou la réponse avait un format que l’intégration ne comprend pas. Si dès le premier chargement cela échoue (pas à cause d’une clé refusée, voir ci-dessous), l’intégration s’affiche comme *nouvelle tentative de configuration* et Home Assistant réessaie tout seul. L’erreur est dans le journal de Home Assistant (la clé n’y figure jamais), et le capteur se rétablit tout seul quand l’API répond de nouveau correctement ; sinon, vérifiez dans les paramètres la clé, l’arrêt, le poteau et la ligne.
- **Home Assistant demande une nouvelle clé (ré-authentification).** L’ancienne API a répondu trois fois de suite « clé refusée » (les nouvelles tentatives d’une configuration comptent aussi ; une panne entre-temps relance le compte). Saisissez une nouvelle clé ou un nouveau jeton dans l’invite ; l’arrêt et la ligne restent, et une clé est acceptée même si la ligne ne circule pas aujourd’hui. Tant que vous ne le faites pas, le capteur reste `unavailable`. La nouvelle API répond de la même façon à toute requête refusée, donc un jeton refusé ne s’y distingue pas d’une panne : le capteur garde l’horaire enregistré jusqu’à la fin de sa journée de service, puis devient `unavailable`, et aucune invite n’apparaît ; si vous avez révoqué le jeton, saisissez-en un nouveau dans **Configurer** sur l’entrée.
- **Signaler un problème.** Ouvrez l’entrée de l’intégration, utilisez *Télécharger les diagnostics* et joignez le fichier au ticket : il montre l’entrée et l’état de l’horaire, la clé ou le jeton étant remplacés par `**REDACTED**`.
- **Les données semblent périmées pendant une panne.** Un délai dépassé, une erreur réseau ou une erreur serveur (HTTP 5xx) après un chargement réussi ne rend **pas** le capteur `unavailable` : il garde le dernier horaire et réessaie toutes les heures, car l’horaire est une donnée planifiée qui ne change pas en une journée. Le capteur de diagnostic **Last update** (désactivé par défaut ; activez-le dans les paramètres de l’entité) indique quand les données ont été récupérées avec succès pour la dernière fois.
- **La configuration indique que la ligne est introuvable.** L’API ne liste que les lignes qui circulent aujourd’hui. Une ligne qui ne circule pas aujourd’hui (par exemple une ligne de semaine un dimanche) ne peut pas être ajoutée avant le jour où elle circule.
- **Une ligne de wtp.waw.pl manque ici.** Le calculateur d’itinéraire dispose de plus de données que l’API publique. Cela ne peut pas être corrigé dans l’intégration.
- **Lignes de nuit** (`N01`, `N44` ...) : la ville compte toute la nuit dans la journée de service précédente, donc un bus à `24:50` ou `26:20` est encore dans l’horaire de cette journée. L’intégration lit ces heures correctement : un départ à `02:15` (`26:15` dans l’API) est affiché à 02:00 comme « dans 15 minutes ».

---

## 📚 Documentation

Le [wiki](https://github.com/solarssk/ztm_warsaw/wiki) est le manuel utilisateur : installation, configuration, fonctionnement de l’horaire et de la journée de service, et dépannage. Il est publié depuis [`docs/wiki/`](docs/wiki) dans ce dépôt (en anglais).

---

## 🧑‍💻 Contribuer et sécurité

Les idées, rapports de bugs et pull requests sont les bienvenus : voir [CONTRIBUTING.md](CONTRIBUTING.md). Pour signaler une vulnérabilité, voir [SECURITY.md](SECURITY.md).

---

## 🙌 Données et remerciements

Données : la ville de Varsovie (**Miasto Stołeczne Warszawa**) et l’autorité des transports publics de Varsovie (**Zarząd Transportu Miejskiego**, ZTM), via le portail de données ouvertes de la ville ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), sous licence [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/deed.fr).

Ce projet a été entièrement planifié et conçu par moi, du concept et du comportement attendu de l’intégration jusqu’à sa manière de dialoguer avec l’API publique de la ville de Varsovie. Je ne suis pas un développeur Python professionnel, mais je comprends l’essentiel assez bien pour définir la structure, la logique et les fonctionnalités que je voulais.

Pour la réaliser, j’ai utilisé l’aide d’une IA (ChatGPT), principalement pour la syntaxe, le débogage et les détails d’implémentation. La conception générale, le comportement et le flux de travail viennent toutefois de moi.

Un merci particulier à [@peetereczek](https://github.com/peetereczek/ztm), dont le projet précédent m’a inspiré au début. Bien que cette version finale ait été construite de façon indépendante, à partir de zéro, son travail m’a donné la première impulsion pour aborder les choses à ma manière.

Si vous souhaitez améliorer ou étendre le projet, allez-y ! Les contributions, idées et pull requests sont toujours les bienvenues.

---

## 📄 Licence

Licence MIT
