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

L’integrazione mostra le **partenze previste dall’orario** utilizzando i dati aperti della città di Varsavia. Ogni sensore mostra le partenze di una linea da un punto di fermata specifico. Puoi visualizzarle nella dashboard di Home Assistant o utilizzarle nelle automazioni, ad esempio per ricevere un promemoria quando è ora di uscire per prendere l’autobus.

I dati provengono dagli orari pubblicati. L’integrazione presenta questi limiti:

- non mostra ritardi né avvisi di disservizio: l’API fornisce partenze programmate, aggiornate una volta al giorno. Il veicolo della prossima partenza può comparire sulla mappa come entità facoltativa (serve un token, vedi la wiki);
- gli orari sono disponibili solo per il giorno di servizio corrente: l’API pubblica non fornisce altre date;
- non pianifica percorsi o coincidenze: per questo, usa [wtp.waw.pl](https://wtp.waw.pl).

---

## 🔧 Funzionalità

- ✅ Autobus, tram, metropolitana e treni SKM, comprese le linee notturne, per i cimiteri, espresse e locali.
- ✅ Supporto per più linee e fermate.
- ✅ L’ora della prossima partenza come stato del sensore, disponibile nelle dashboard e nelle automazioni. Le tre partenze successive sono salvate negli attributi (`Next 1`–`Next 3`).
- ✅ Il messaggio «No service» quando non ci sono più partenze e lo stato `unavailable` quando non è possibile ottenere un orario valido (vedi [Risoluzione dei problemi](#-risoluzione-dei-problemi)).
- ✅ Configurazione nell’interfaccia di Home Assistant in otto lingue: inglese, polacco, ucraino, russo, tedesco, spagnolo, francese e italiano. Le sei nuove versioni sono state tradotte automaticamente; puoi proporre correzioni tramite pull request.
- ✅ Attributi con il nome e le coordinate della fermata, la direzione di viaggio, un collegamento all’orario e le note. Le coordinate permettono di visualizzare la fermata su una mappa.
- ✅ Modifica della chiave API o del token tramite **Configura**, anche per passare alla nuova API della città.
- ✅ Un’entità **calendario** separata per ogni sensore, disattivata per impostazione predefinita. Dopo averla attivata nelle impostazioni dell’entità, ogni partenza del giorno di servizio appare come un evento di un minuto. Il trigger del calendario permette di avviare un’automazione, ad esempio otto minuti prima della partenza, senza creare template.

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

L’integrazione supporta le credenziali di entrambe le API della città di Varsavia:

- **Token per la nuova API (consigliato):** su [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api), inserisci un nome utente, accetta le condizioni e scarica il tuo token. È una lunga stringa di caratteri composta da tre parti separate da punti.
- **Chiave per la vecchia API:** una chiave di [api.um.warszawa.pl](https://api.um.warszawa.pl) ha il formato `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. La vecchia API a volte non risponde, e la città non ha annunciato quando verrà disattivata. Consigliamo di passare alla nuova API.

L’integrazione riconosce il tipo di credenziale e la invia soltanto all’API corrispondente. Per sostituire una vecchia chiave con un token, scegli **Configura** per la linea e incolla il token. Le impostazioni della linea e delle fermate verranno mantenute. Non serve aggiungere di nuovo l’integrazione: la procedura rifiuta configurazioni duplicate della stessa linea nello stesso punto di fermata.

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
2. Clicca su **+ Aggiungi integrazione** e cerca **Trasporto pubblico di Varsavia**.
3. Compila:
   - **chiave API o token** (vedi sopra),
   - **ID della fermata** e **numero del punto di fermata** (per esempio 7009 e 01),
   - **numero della linea** (per esempio 151).

L’ID dell’entità contiene il numero della linea, l’ID della fermata e il numero del punto di fermata, ad esempio `sensor.line_151_from_7009_01`. Per modificare la chiave API o il token, apri **Impostazioni → Dispositivi e servizi → Trasporto pubblico di Varsavia** e scegli **Configura** per la linea. Le impostazioni della linea e delle fermate verranno mantenute. Se viene ancora utilizzata una vecchia chiave, in **Riparazioni** comparirà un avviso con le istruzioni per passare a un token. Puoi ignorarlo.

L’**ID della fermata** è comune a tutti i punti di fermata che appartengono alla stessa fermata. Il **numero del punto di fermata** identifica il luogo preciso in cui si sale a bordo, solitamente per una direzione di viaggio. Di norma è composto da due cifre, come 01 o 02, e si trova sulla palina della fermata. In polacco, questo punto numerato si chiama *słupek*.

---

## 🩺 Risoluzione dei problemi

- **Il sensore ha lo stato `unknown` e gli attributi mostrano «No service».** La linea oggi non circola oppure tutte le partenze sono già passate. È il comportamento previsto. Consulta l’orario su [wtp.waw.pl](https://wtp.waw.pl) o chiama il 19115.
- **Il sensore ha lo stato `unavailable` (non disponibile).** L’API non ha restituito un orario valido. Le possibili cause includono una chiave rifiutata, dati errati della fermata, del punto di fermata o della linea, oppure un formato di risposta non supportato. Se il primo recupero dei dati fallisce per un motivo diverso da una chiave rifiutata, Home Assistant riprova automaticamente la configurazione. Le chiavi rifiutate vengono gestite come descritto di seguito. I dettagli dell’errore si trovano nel registro di Home Assistant; le chiavi e i token non vengono registrati. Il sensore torna disponibile quando riceve dati validi. Se il problema persiste, verifica le credenziali e i dati della fermata e della linea.
- **Home Assistant richiede una nuova chiave.** Succede quando la vecchia API rifiuta la chiave tre volte consecutive. Contano anche i tentativi durante la configurazione; un errore di rete o del server interrompe la sequenza. Inserisci una nuova chiave API o un token nel modulo. Le impostazioni verranno mantenute e una chiave valida verrà accettata anche se la linea non circola quel giorno. Il sensore rimane non disponibile finché non aggiorni le credenziali. La nuova API non permette di distinguere un token rifiutato da un’interruzione del servizio. Se è già stato scaricato un orario, il sensore lo utilizza fino al termine del giorno di servizio, poi diventa non disponibile. Non appare automaticamente alcun modulo per cambiare le credenziali. Se hai revocato il token, inseriscine uno nuovo tramite **Configura** per la linea.
- **Segnalare un problema.** Apri la configurazione della linea, scegli *Scarica la diagnostica* e allega il file alla segnalazione. Contiene informazioni sulla configurazione e sull’orario. La chiave API o il token viene sostituito da `**REDACTED**`.
- **Le partenze sono ancora visibili durante un’interruzione dell’API.** Dopo un download riuscito, un timeout, un errore di rete o un errore del server (HTTP 5xx) non rende immediatamente il sensore non disponibile. L’integrazione utilizza l’orario salvato fino al termine del giorno di servizio e riprova il download ogni ora. Le partenze programmate non cambiano nel corso della giornata. Il sensore diagnostico **Last update**, disattivato per impostazione predefinita, mostra l’ultimo recupero riuscito. Puoi attivarlo nelle impostazioni dell’entità.
- **La linea non viene trovata durante la configurazione.** L’API elenca soltanto le linee che circolano quel giorno. Ad esempio, una linea attiva solo nei giorni feriali non può essere aggiunta di domenica. Riprova in un giorno in cui sono previste partenze.
- **Una linea appare su wtp.waw.pl, ma non nell’integrazione.** Il pianificatore di percorsi utilizza più dati rispetto all’API pubblica. L’integrazione può mostrare solo i dati forniti dall’API.
- **Orari delle linee notturne** (`N01`, `N44` ecc.). Il giorno di servizio può proseguire oltre la mezzanotte: `24:50` significa le 00:50 del giorno successivo e `26:20` significa le 02:20. L’integrazione converte correttamente questi orari. Una partenza registrata come `26:15` corrisponde alle 02:15 del giorno successivo; alle 02:00 appare come una partenza tra 15 minuti.

---

## 📚 Documentazione

Il [manuale utente nella wiki](https://github.com/solarssk/ztm_warsaw/wiki) descrive l’installazione, la configurazione, gli orari, il giorno di servizio e la risoluzione dei problemi. È disponibile in inglese; i file sorgente si trovano in [`docs/wiki/`](docs/wiki).

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
