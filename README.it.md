<h1 align="center">🚍 ZTM Varsavia per Home Assistant</h1>

<p align="center">
  <strong>Le prossime partenze programmate di una linea di autobus, tram, metro o notturna di Varsavia, come sensore.<br>Dai dati aperti della città. Senza YAML e senza promesse di tracciamento in tempo reale.</strong>
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

Mostra le prossime **partenze programmate** di una linea del trasporto pubblico di Varsavia (autobus, tram, metro, treno urbano o linea notturna) a un palo di fermata come sensore in Home Assistant, dai dati aperti della città di Varsavia. Utile per dashboard e automazioni come «esci tra otto minuti» senza aprire un’app di orari.

Mostra l’**orario**, non i veicoli in tempo reale. Cosa **non** fa:

- niente posizioni in tempo reale, ritardi o disservizi: la città pubblica partenze pianificate, aggiornate una volta al giorno;
- niente orari per altri giorni: l’API fornisce solo il giorno di servizio corrente;
- niente pianificazione di viaggi: per questo c’è [wtp.waw.pl](https://wtp.waw.pl).

---

## 🔧 Funzionalità

- ✅ Linee di autobus, tram, metro, notturne, per i cimiteri, express e locali.
- ✅ Più istanze: monitora quante fermate e linee vuoi.
- ✅ La prossima partenza come marca temporale, utilizzabile nell’interfaccia e nelle automazioni, e le tre successive come attributi (`Next 1` ... `Next 3`).
- ✅ Uno stato «No service» chiaro nei giorni in cui una linea non circola e `unavailable` quando l’API della città ha problemi (vedi [Risoluzione dei problemi](#-risoluzione-dei-problemi)).
- ✅ Configurazione interamente nell’interfaccia di Home Assistant, in inglese, polacco, ucraino, russo, tedesco, spagnolo, francese o italiano (i testi diversi da inglese e polacco sono tradotti automaticamente: le correzioni sono benvenute come pull request).
- ✅ Attributi con la fermata (nome e posizione, quindi compare come segnaposto sulla scheda mappa), la direzione, un link all’orario e delle note.
- ✅ Cambia la chiave API o il token di una voce in qualsiasi momento in **Configura**, per esempio dalla vecchia API della città alla nuova.
- ✅ Un’entità **calendario** per ogni sensore (disattivata di default: attivala nelle impostazioni dell’entità) con ogni partenza del giorno come evento di un minuto: vedi tutto l’orario nella vista calendario di Home Assistant e avvii automazioni con il trigger del calendario («8 minuti prima di una partenza») senza template.

---

## 📸 Schermate

### Configurazione dell’integrazione
*Inserisci la tua chiave API e i dati della fermata...*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Aspetto dell’entità

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Attributi
*Entità di esempio con partenze e attributi come orario, direzione...*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Requisiti

- Home Assistant 2026.1 o successivo
- Una chiave API o un token della città di Varsavia (sotto)

---

## 🧭 Come ottenere una chiave o un token

La città gestisce due portali, e l’integrazione accetta la chiave di entrambi:

- **Nuovo (consigliato):** su [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) inserisci un nickname, accetta le condizioni e scarica il tuo token. È un lungo testo in tre parti separate da punti.
- **Vecchio:** una chiave di [api.um.warszawa.pl](https://api.um.warszawa.pl) ha l’aspetto `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Le vecchie chiavi esistenti funzionano ancora al momento della scrittura, ma la città non indica né una data né una promessa su quanto, quindi passa a un token quando puoi.

L’integrazione riconosce quale hai incollato e parla solo con l’API corrispondente. Per passare una voce esistente a un token, usa **Configura** su quella voce e inserisci il token (la fermata e la linea restano); non aggiungere una seconda voce, perché due voci per la stessa fermata, palo e linea non possono coesistere e la procedura rifiuta la seconda.

---

## 📦 Installazione

### Con HACS

1. In Home Assistant vai su **HACS → Integrazioni**.
2. Cerca **Warsaw Public Transport**.
3. Clicca su **Scarica** e conferma.
4. Riavvia Home Assistant.

### Manualmente

1. Scarica l’ultima versione da [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Copia la cartella `ztm_warsaw` in `/config/custom_components/`.
3. Riavvia Home Assistant.

---

## 🔌 Configurazione

1. Vai su **Impostazioni → Dispositivi e servizi**.
2. Clicca su **+ Aggiungi integrazione** e cerca **Warsaw Public Transport**.
3. Compila:
   - **chiave API o token** (vedi sopra),
   - **ID della fermata** e **numero del palo** (per esempio 7009 e 01),
   - **numero della linea** (per esempio 151).

L’entità prende il nome dalla fermata e dalla linea, per esempio `sensor.line_151_from_7009_01`. Per sostituire la chiave API o il token di una voce (ad esempio passare da una vecchia chiave a un token), usa **Impostazioni → Dispositivi e servizi → Warsaw Public Transport → Configura** su quella voce; la fermata e la linea restano. Una voce che usa ancora una vecchia chiave mostra un avviso chiudibile in **Impostazioni → Riparazioni**.

**L’ID della fermata e il numero del palo** non sono la stessa cosa: l’ID della fermata è comune a tutti i pali di una fermata, e il numero del palo (di solito 01, 02, ...) è il numero dipinto sul cartello del palo (*słupek*). Una fermata con più direzioni ha un numero diverso per ciascuna.

---

## 🩺 Risoluzione dei problemi

- **Lo stato è `unknown` e l’attributo dice «No service».** La linea oggi non circola, oppure la sua ultima partenza è passata. Non è un errore: controlla [wtp.waw.pl](https://wtp.waw.pl) o chiama il 19115.
- **Il sensore è `unavailable`.** L’API della città ha risposto, ma non con un orario: la chiave o il token è stato rifiutato, la fermata, il palo e la linea non sono noti all’API, oppure la risposta aveva un formato che l’integrazione non capisce. Se già il primo caricamento fallisce (non per una chiave rifiutata, vedi sotto), l’integrazione appare come *nuovo tentativo di configurazione* e Home Assistant riprova da solo. L’errore è nel log di Home Assistant (la chiave non vi compare mai), e il sensore si riprende da solo quando l’API risponde di nuovo correttamente; altrimenti controlla nelle impostazioni la chiave, la fermata, il palo e la linea.
- **Home Assistant chiede una nuova chiave (riautenticazione).** La vecchia API ha risposto «chiave rifiutata» tre volte di fila (contano anche i nuovi tentativi di una configurazione; un’interruzione nel mezzo riavvia il conteggio). Inserisci una nuova chiave o un token nella richiesta; la fermata e la linea restano, e una chiave viene accettata anche se la linea oggi non circola. Finché non lo fai, il sensore resta `unavailable`. La nuova API risponde allo stesso modo a ogni richiesta rifiutata, quindi un token rifiutato lì non si distingue da un’interruzione: il sensore tiene l’orario salvato fino alla fine del suo giorno di servizio, poi diventa `unavailable`, e non compare alcuna richiesta; se hai revocato il token, inseriscine uno nuovo in **Configura** sulla voce.
- **Segnalare un problema.** Apri la voce dell’integrazione, usa *Scarica diagnostica* e allega il file alla segnalazione: mostra la voce e lo stato dell’orario, con la chiave o il token sostituiti da `**REDACTED**`.
- **I dati sembrano obsoleti durante un’interruzione.** Un timeout, un errore di rete o un errore del server (HTTP 5xx) dopo un caricamento riuscito **non** rende il sensore `unavailable`: conserva l’ultimo orario e riprova ogni ora, perché l’orario è un dato pianificato che non cambia nell’arco di un giorno. Il sensore diagnostico **Last update** (disattivato di default; attivalo nelle impostazioni dell’entità) mostra quando i dati sono stati recuperati con successo l’ultima volta.
- **La configurazione dice che la linea non è stata trovata.** L’API elenca solo le linee che circolano oggi. Una linea che oggi non circola (per esempio una linea feriale di domenica) non può essere aggiunta fino al giorno in cui circola.
- **Una linea di wtp.waw.pl manca qui.** Il pianificatore di viaggi ha più dati dell’API pubblica. Questo non si può correggere nell’integrazione.
- **Linee notturne** (`N01`, `N44` ...): la città conta tutta la notte come parte del giorno di servizio precedente, quindi un autobus alle `24:50` o `26:20` è ancora nell’orario di quel giorno. L’integrazione legge correttamente questi orari: una partenza alle `02:15` (`26:15` nell’API) alle 02:00 è mostrata come «tra 15 minuti».

---

## 📚 Documentazione

La [wiki](https://github.com/solarssk/ztm_warsaw/wiki) è il manuale utente: installazione, configurazione, come funzionano orario e giorno di servizio, e risoluzione dei problemi. È pubblicata da [`docs/wiki/`](docs/wiki) in questo repository (in inglese).

---

## 🧑‍💻 Contribuire e sicurezza

Idee, segnalazioni di bug e pull request sono benvenute: vedi [CONTRIBUTING.md](CONTRIBUTING.md). Per segnalare una vulnerabilità, vedi [SECURITY.md](SECURITY.md).

---

## 🙌 Dati e ringraziamenti

Dati: la città di Varsavia (**Miasto Stołeczne Warszawa**) e l’Autorità del trasporto pubblico di Varsavia (**Zarząd Transportu Miejskiego**, ZTM), tramite il portale dei dati aperti della città ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), con licenza [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/deed.it).

Questo progetto è stato interamente pianificato e progettato da me: dall’idea e dal comportamento atteso dell’integrazione fino a come dialoga con l’API pubblica della città di Varsavia. Non sono uno sviluppatore Python professionista, ma capisco l’essenziale abbastanza bene da definire la struttura, la logica e le funzioni che volevo offrisse.

Per realizzarla ho usato il supporto di un’IA (ChatGPT), che mi ha aiutato soprattutto con la sintassi, il debug e i dettagli di implementazione. Il progetto complessivo, il comportamento e il flusso di lavoro sono però frutto mio.

Un ringraziamento speciale a [@peetereczek](https://github.com/peetereczek/ztm), il cui progetto precedente mi ha ispirato all’inizio. Anche se questa versione finale è stata costruita in modo indipendente da zero, il suo lavoro mi ha dato la prima spinta ad affrontare le cose a modo mio.

Se ti interessa migliorare o estendere il progetto, fai pure! Contributi, idee e pull request sono sempre benvenuti.

---

## 📄 Licenza

Licenza MIT
