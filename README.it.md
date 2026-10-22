<h1 align="center">🚍 ZTM Varsavia per Home Assistant</h1>

<p align="center">
  <strong>Gli orari del trasporto pubblico di Varsavia in Home Assistant.<br>Le prossime partenze nelle dashboard e nelle automazioni. Configurazione senza YAML.</strong>
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
  🇫🇷 <a href="README.fr.md">Français</a>
  &nbsp;·&nbsp;
  🇮🇹 <strong>Italiano</strong>
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
<summary><strong>Indice</strong></summary>

- [Funzionalità](#-funzionalità)
- [Schermate](#-schermate)
- [Requisiti](#-requisiti)
- [Come ottenere una chiave o un token](#-come-ottenere-una-chiave-o-un-token)
- [Installazione](#-installazione)
- [Configurazione](#-configurazione)
- [Risoluzione dei problemi](#-risoluzione-dei-problemi)
- [Documentazione](#-documentazione)
- [Contribuire e sicurezza](#-contribuire-e-sicurezza)
- [Dati e ringraziamenti](#-dati-e-ringraziamenti)
- [Licenza](#-licenza)

</details>

Mostra **quando parte il prossimo autobus, tram o treno dalla tua fermata**: un sensore per una linea a un punto di fermata, per la tua dashboard e per automazioni come «dimmi quando uscire». Usa i dati aperti della città di Varsavia e non richiede hardware aggiuntivo.

Mostra partenze **programmate**: niente ritardi né avvisi di disservizio, solo il giorno di servizio in corso e nessuna pianificazione di viaggi (per questo c’è [wtp.waw.pl](https://wtp.waw.pl)). Il veicolo della prossima partenza può comparire sulla mappa (facoltativo, serve un token).

---

## 🔧 Funzionalità

- ✅ Autobus, tram, metropolitana e treni urbani (SKM), comprese le linee notturne, espresse e locali.
- ✅ La prossima partenza è lo stato del sensore; le tre successive, la prima e l’ultima partenza della giornata sono attributi.
- ✅ Un sensore *Stato* dice con parole semplici cosa sta succedendo («L’ultima partenza della giornata è passata»).
- ✅ Configurazione cercando il nome della fermata e scegliendo poi il punto di fermata e la linea: nessun numero da cercare.
- ✅ Più linee e fermate, un tempo di cammino facoltativo, un calendario facoltativo e un segnaposto facoltativo del veicolo sulla mappa.
- ✅ Otto lingue: inglese, polacco, ucraino, russo, tedesco, spagnolo, francese e italiano. Le sei più recenti sono tradotte automaticamente; le correzioni sono benvenute come pull request.

---

## 📸 Schermate

### Configurazione dell’integrazione
*Il modulo di configurazione con le credenziali e i dati della linea e della fermata.*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Aspetto dell’entità

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Attributi
*I dettagli dell’orario, comprese le ore di partenza e la direzione di viaggio.*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Requisiti

- Home Assistant 2026.1 o successivo
- Una chiave API o un token della città di Varsavia (sotto)

---

## 🧭 Come ottenere una chiave o un token

Ottieni un token gratuito su [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api): inserisci un nickname, accetta le condizioni e scaricalo. È un testo lungo in tre parti separate da punti.

Una vecchia chiave API (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, da [api.um.warszawa.pl](https://api.um.warszawa.pl)) funziona ancora, ma quel server a volte non risponde, la città non ha indicato una data di chiusura e il veicolo sulla mappa richiede un token. Per cambiare, apri l’avviso in **Riparazioni** oppure scegli **Configura** sulla linea e incolla il token. Le tue impostazioni restano.

---

## 📦 Installazione

### Con HACS

1. In Home Assistant vai su **HACS → Integrazioni**.
2. Cerca **Trasporto pubblico di Varsavia**.
3. Clicca su **Scarica** e conferma.
4. Riavvia Home Assistant.

### Manualmente

1. Scarica l’ultima versione da [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Copia la cartella `ztm_warsaw` in `/config/custom_components/`.
3. Riavvia Home Assistant.

---

## 🔌 Configurazione

1. Vai su **Impostazioni → Dispositivi e servizi**.
2. Fai clic su **+ Aggiungi integrazione** e cerca **Trasporto pubblico di Varsavia**.
3. Incolla il token e scrivi una parte del nome della fermata (per esempio `Marcelin`) o il suo ID.
4. Scegli il punto di fermata (il numero è sul cartello della fermata, uno per direzione) e la linea. Sono elencate solo le linee che oggi vi fermano.

Il sensore si chiama per esempio `sensor.line_151_from_7009_01`. Un’altra fermata della linea si aggiunge con **Aggiungi fermata**. Se conosci già i numeri, spunta **Conosco i numeri** nella prima schermata. Il tempo di cammino, il calendario, il segnaposto del veicolo e come rimuovere una linea sono nella [wiki](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration).

---

## 🩺 Risoluzione dei problemi

- **Il sensore è `unknown` e mostra «No service».** La linea oggi non circola o la sua ultima partenza è passata. È normale. Quale dei due casi lo dice il sensore *Stato*; l’orario è su [wtp.waw.pl](https://wtp.waw.pl), oppure chiama il 19115.
- **Il sensore è `unavailable`.** La città non ha restituito un orario valido: un token rifiutato, oppure una fermata, un punto di fermata o una linea che non conosce. Il motivo è nel registro di Home Assistant (chiavi e token non vi compaiono mai).
- **Errori di rete, con una vecchia chiave.** Il vecchio server della città a volte non risponde. I sensori tengono l’orario che hanno e chiedono di nuovo più tardi; passare a un token risolve.
- **Home Assistant chiede una nuova chiave.** La città ha rifiutato la chiave tre volte di fila. Inserisci una nuova chiave o un nuovo token nel modulo; le tue impostazioni restano.
- **Segnalare un problema.** Scegli *Scarica la diagnostica* sulla voce e allega il file alla tua issue. La chiave o il token vi compare come `**REDACTED**`.

Altre risposte sono nella [wiki](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting).

---

## 📚 Documentazione

La [wiki](https://github.com/solarssk/ztm_warsaw/wiki) è il manuale d’uso: [Configurazione](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration) (tempo di cammino, rimuovere una linea), [Concetti](https://github.com/solarssk/ztm_warsaw/wiki/2.-Concepts) (il giorno di servizio, cosa mostra ogni entità), [Esempi](https://github.com/solarssk/ztm_warsaw/wiki/3.-Examples) (schede e automazioni da copiare) e [Risoluzione dei problemi](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting). È in inglese; i sorgenti sono in [`docs/wiki/`](docs/wiki).

---

## 🧑‍💻 Contribuire e sicurezza

Idee, segnalazioni di errori e pull request sono benvenute. Le indicazioni per contribuire sono in [CONTRIBUTING.md](CONTRIBUTING.md). Per segnalare una vulnerabilità, segui le istruzioni in [SECURITY.md](SECURITY.md).

---

## 🙌 Dati e ringraziamenti

Dati: la città di Varsavia (**Miasto Stołeczne Warszawa**) e l’Autorità del trasporto pubblico di Varsavia (**Zarząd Transportu Miejskiego**, ZTM), tramite il portale dei dati aperti della città ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), con licenza [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/deed.it).

Ho progettato il concetto, le funzionalità, la struttura e il collegamento con l’API pubblica della città di Varsavia. Non sono uno sviluppatore Python professionista, ma le mie conoscenze di base mi hanno permesso di pianificare il funzionamento del progetto.

Ho utilizzato ChatGPT come supporto per la sintassi, il debug e i dettagli di implementazione. Ho preso personalmente le decisioni sul progetto e sul suo funzionamento.

Grazie a [@peetereczek](https://github.com/peetereczek/ztm), il cui progetto precedente mi ha ispirato. Questa integrazione è stata sviluppata da zero come progetto indipendente.

Puoi contribuire allo sviluppo del progetto con idee, segnalazioni di errori e proposte di miglioramento.

---

## 📄 Licenza

Licenza MIT
