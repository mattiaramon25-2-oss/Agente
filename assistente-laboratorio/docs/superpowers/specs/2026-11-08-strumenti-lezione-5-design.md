# Strumenti della lezione 5 in tre varianti — specifica

Data: 2026-11-08 · Stato: approvata (2026-11-08) · Branch: `dev`, poi un branch per passo (sezione 12)

Estende due specifiche, che restano valide per tutto ciò che qui non cambia:

- `2026-11-02-assistente-laboratorio-design.md`: l'assistente di base;
- `2026-11-03-convertitore-unita-mcp-design.md`: il convertitore e tutta l'infrastruttura MCP, cioè server FastMCP con Streamable HTTP, ponte sincrono, avvio con un solo comando, log a due file e diagnosi per livelli.

Dove questa specifica contraddice la seconda (per esempio i suoi non obiettivi, o il fatto che l'orologio resti locale), vale questa. Le regole generali di lavoro sono nel `CLAUDE.md` alla radice della repository.

## 1. Intento

Lezione 5 del corso («MCP: dalle funzioni agli strumenti condivisi»). L'utente vuole due cose.

1. **Un solo server MCP per tutti gli strumenti**, compreso l'orologio che oggi è una funzione locale. Il server espone i sei strumenti proposti nel blocco 5 della presentazione (convertitore, calcolatrice sicura, giorni e scadenze, catalogo locale, note persistenti, meteo) più l'orologio, con i contratti scritti nelle slide.
2. **Un confronto didattico tra i tre modi di collegare uno strumento** (blocco 4 della presentazione):
   - **variante MCP**: server FastMCP, catalogo scoperto dal client e adattato al grafo. È la variante di **tutti** gli strumenti;
   - **variante locale**: funzione Python registrata con `@tool` nel processo dell'agente. Ha **un solo** strumento, la calcolatrice;
   - **variante FastAPI**: servizio HTTP con un wrapper nell'agente, scritto a mano e registrato con `@tool`. Ha **un solo** strumento, giorni e scadenze.

Nelle varianti locale e FastAPI lo strumento è inevitabilmente una copia di quello MCP: stesso nome, stessi argomenti, stesso risultato, stessi errori (slide 21: «un confronto utile mantiene invariati domanda, modello e significato dello strumento»). Cambia solo il percorso con cui il nodo strumenti ottiene il risultato.

**Decisioni dell'utente:**
- server MCP unico, con dentro anche l'orologio;
- tre varianti: tutti gli strumenti in MCP, uno solo in locale, uno solo in FastAPI;
- le copie locale e FastAPI sono di due strumenti **diversi**, scelti tra i cinque nuovi;
- il modello vede **una sola versione** di ciascuno strumento duplicato alla volta, scelta nel `.env`.

**Scelta mia**: la calcolatrice va in locale e giorni e scadenze in FastAPI.
- La calcolatrice è un calcolo puro e interno, esattamente il caso in cui la slide 17 dice che la funzione locale è la scelta ragionevole.
- Giorni e scadenze ha argomenti semplici da passare in una query HTTP e un risultato deterministico, quindi le due varianti si confrontano al valore esatto.

## 2. Obiettivi

1. **Orologio spostato nel server MCP.** `ora_corrente` mantiene nome, argomenti, risultato e comportamento attuali. Nell'agente non resta nessuno strumento orologio locale.
2. **Cinque nuovi strumenti MCP** nello stesso server del convertitore, con i contratti della sezione 5. In tutto il server espone dieci strumenti:

   | Strumento | Nomi MCP |
   |---|---|
   | orologio | `ora_corrente` |
   | convertitore | `converti_unita` |
   | calcolatrice | `calcola` |
   | scadenze | `calcola_scadenza` |
   | catalogo | `search_catalog`, `get_item` |
   | note | `add_note`, `list_notes`, `delete_note` |
   | meteo | `get_weather` |
3. **Variante locale della calcolatrice**: `calcola` come `@tool` nell'agente. Contratto ricavato dalla firma e dalla docstring, identico a quello MCP.
4. **Variante FastAPI delle scadenze**: un servizio FastAPI con l'endpoint per `calcola_scadenza` e un wrapper HTTP nell'agente, registrato con `@tool`, con nome, descrizione e schema scritti a mano e identici a quelli MCP (slide 19: niente discovery).
5. **Scelta della variante nel `.env`.** Una variabile per ciascuno strumento duplicato. L'agente passa al modello una sola versione per nome, e nei log e nel terminale si vede quale.
6. **La logica di ogni strumento è scritta una volta sola**, in moduli puri senza dipendenze da `fastmcp`, `fastapi` o LangChain. Tutte le varianti la riusano. Dove cambia il percorso, la logica non cambia (slide 18: «la logica dell'orologio già disponibile nel progetto»).
7. **Un solo comando avvia tutto**, come oggi: l'agente avvia il server MCP e, se la variante delle scadenze è FastAPI, anche il servizio FastAPI. All'uscita li spegne entrambi.
8. **Ogni chiamata è tracciata nei log**, con la variante (`origine`) da cui è passata.

## 3. Non obiettivi

- Le estensioni facoltative della slide 29:
  - trasporto stdio;
  - due server MCP collegati allo stesso agente;
  - prompt MCP.
- Resources MCP, compresa la resource facoltativa del catalogo (slide 28).
- Varianti locale o FastAPI per strumenti diversi da calcolatrice e scadenze.
- Versione FastAPI del server MCP, cioè un server MCP che chiama il servizio FastAPI. Le due varianti delle scadenze riusano la stessa logica pura, ciascuna per conto suo.
- Più di una variante dello stesso strumento visibile al modello nella stessa sessione.
- Cambiare variante a sessione in corso. Si cambia il `.env` e si riavvia.
- Grafo o interfaccia asincroni; server o servizio raggiungibili da altri computer; autenticazione.
- Ricerca semantica o RAG sul catalogo: è materia della lezione 6 (slide 28, «verso la lezione 6»).
- Conferma interattiva dell'utente prima dell'eliminazione di una nota: l'eliminazione è sicura perché avviene solo per ID esatto (sezione 5.6) — *scelta mia*.
- Festività locali (santi patroni) e calcoli con valore legale.

## 4. Anti-obiettivi (lo renderebbero un fallimento anche se "funziona")

Valgono tutti quelli della specifica del convertitore, estesi a ogni strumento. In più:

- **Due versioni dello stesso strumento visibili insieme al modello**, o uno strumento con lo stesso nome che arriva sia dal server MCP sia dall'agente.
- **Varianti che non sono copie.** Le due versioni di uno strumento duplicato hanno nome, descrizione, schema, risultato o messaggi di errore diversi per lo stesso input. Il confronto non sarebbe più tra percorsi, ma tra strumenti diversi.
- **Logica duplicata.** La calcolatrice o le scadenze sono riscritte una seconda volta in una variante, invece di riusare il modulo puro.
- **La variante dichiarata non è quella usata.** Il `.env` dice `locale` ma la chiamata passa dal server MCP, o il contrario, e i log non lo mostrano.
- **La calcolatrice usa `eval`, `exec` o equivalenti**, o accetta qualcosa di diverso dalle operazioni ammesse.
- **Note modificate senza traccia:** un'aggiunta o un'eliminazione senza una riga nel log del server, oppure l'eliminazione di una nota diversa da quella con l'ID indicato.
- **Meteo inventato:** una temperatura restituita quando la città non è stata trovata o la rete non risponde. Oppure una città ambigua risolta in silenzio, senza dire quale è stata scelta.
- **Catalogo inventato:** una ricerca senza risultati che restituisce elementi non presenti nel file.
- **Rete e dominio confusi:** un errore di rete del meteo presentato come «città non trovata», o il contrario.
- **Processi orfani:** dopo l'uscita resta acceso il servizio FastAPI.

## 5. Strumenti

Regole comuni a tutti gli strumenti, prese dalla specifica del convertitore e qui estese a ognuno:

- **Risultato:** un oggetto JSON con chiavi in italiano (tranne dove le slide fissano nomi diversi), senza artefatti della virgola mobile.
- **Errori dello strumento:**
  - messaggio in italiano, comprensibile al modello, mai insieme a un risultato;
  - nella variante MCP passano dal meccanismo di errore di MCP (`isError`);
  - nelle altre varianti arrivano al grafo come `{"errore": "..."}` con lo stesso testo.
- **Validazione:** se la validazione automatica dello schema non dà un messaggio italiano comprensibile, la fa il codice dello strumento.
- **Numeri scritti come testo:** stessa regola del convertitore. `"2.5"` è accettato, `"2,5"` è rifiutato con la richiesta di usare il punto.
- **Nomi.** Dove le slide fissano nomi di strumenti e argomenti (note, catalogo, meteo) si usano quelli, in inglese — *scelta mia*: «nel modo in cui c'è scritto». Gli strumenti già esistenti (`ora_corrente`, `converti_unita`) mantengono i loro nomi. Quelli senza nome nelle slide (calcolatrice, scadenze) li ricevono in italiano.

### 5.1 Orologio — `ora_corrente` (spostato)

Contratto invariato rispetto a oggi:
- argomento `fuso`, un nome IANA esatto;
- risultato con `fuso`, `data_ora`, `scarto_utc` e `giorno_settimana`.

Cambia solo una cosa: un fuso sconosciuto ora è un errore MCP, mentre oggi è un risultato `{"errore": ...}` normale.

- Il rilevamento del fuso dell'utente all'avvio (`fuso.py`) resta nell'agente. Deve continuare a funzionare senza importare il pacchetto del server.
- Il messaggio di sistema continua a nominare `ora_corrente` per data e ora, come oggi: è la regola che impedisce al modello di inventare l'ora.
- Il fuso del container Docker (UTC) non conta: lo strumento usa sempre il fuso passato come argomento.

### 5.2 Convertitore — `converti_unita`

Invariato rispetto alla sua specifica.

### 5.3 Calcolatrice sicura — `calcola` (varianti MCP e locale)

Slide 25: «espressioni aritmetiche senza eval: solo operazioni consentite. Allena il rifiuto esplicito di input non validi.»

**Argomento:** `espressione` (testo, obbligatorio), per esempio `"(3 + 4) * 2"`.

**Ammesso** — *scelte mie*:
- numeri decimali con il punto;
- `+`, `-` (anche unario), `*`, `/`, `%` (resto), `**` (potenza) e parentesi tonde;
- spazi.

**Calcolo:**
- aritmetica decimale esatta, come nel convertitore, quindi `0.1 + 0.2` dà `0.3`;
- precedenze usuali, con `**` associativa a destra;
- risultato intero senza `.0`;
- divisioni non esatte limitate a un numero ragionevole di cifre significative, per esempio 15. La precisione esatta è lasciata al costruttore.

**Rifiutati, con messaggio esplicito:**
- qualsiasi altro carattere o costrutto: nomi, funzioni, attributi, virgolette, `//`, notazione scientifica;
- la virgola decimale, con la richiesta di usare il punto;
- un'espressione vuota o più lunga di 200 caratteri;
- un errore di sintassi;
- una divisione o un resto per zero;
- una potenza con esponente non intero o con valore assoluto oltre 1000, e qualsiasi risultato troppo grande. `9**9**9` non deve bloccare il programma.

**Realizzazione:** analisi dell'espressione con un parser esplicito, per esempio l'albero `ast` di Python filtrato su una lista chiusa di nodi oppure un piccolo parser scritto a mano. Mai `eval` o `exec`.

**Risultato:**

```json
{"espressione": "(3 + 4) * 2", "risultato": 14}
```

**Variante locale.** `calcola` è registrato con `@tool` di LangChain su una funzione dell'agente che chiama la logica pura:
- nome, descrizione e schema li ricava LangChain dalla firma e dalla docstring (slide 19);
- un test verifica che nome, descrizione, nomi e tipi degli argomenti e campi obbligatori coincidano con quelli del catalogo MCP;
- in caso di errore la funzione restituisce `{"errore": "..."}` con lo stesso testo della variante MCP, e il grafo lo marca come errore.

### 5.4 Giorni e scadenze — `calcola_scadenza` (varianti MCP e FastAPI)

Slide 25: «date ISO e festività da file locale, risultato non normativo. Allena formati e casi limite.»

È **un solo strumento** — *scelta mia*: le varianti locale e FastAPI devono contenerne uno solo, e meno strumenti aiutano il modello piccolo.

**Argomenti** (tutti obbligatori):

| Nome | Tipo | Note |
|---|---|---|
| `data_inizio` | testo | data ISO `AAAA-MM-GG` |
| `giorni` | intero | da 0 a 3650 |
| `lavorativi` | booleano | `true`: conta solo i giorni lavorativi; `false`: giorni di calendario |

**Regole:**
- **Giorni lavorativi:** dal lunedì al venerdì, escluse le festività nazionali italiane lette da un file locale versionato nel progetto. Il file contiene le date (Pasquetta compresa) almeno per il 2026, il 2027 e il 2028 — *scelta mia*.
- **Conteggio:** la scadenza è `data_inizio` più `giorni`, contati dal giorno successivo. Con `giorni = 0` la scadenza è `data_inizio` stessa. Se `data_inizio` cade in un giorno non lavorativo, il conteggio dei lavorativi parte comunque dal giorno successivo — *scelta mia*.
- **Errori:**
  - data non ISO o inesistente (`2026-02-30`, `30/01/2026`);
  - `giorni` fuori intervallo, non intero o booleano;
  - `lavorativi` non booleano;
  - con `lavorativi = true`, un calcolo che esce dagli anni coperti dal file delle festività, con gli anni coperti nel messaggio. Con giorni di calendario il file non serve e non c'è questo limite.

**Risultato:**

```json
{"data_inizio": "2026-12-23", "giorni": 3, "lavorativi": true,
 "scadenza": "2026-12-29", "giorno_settimana": "martedì",
 "festivita_saltate": ["2026-12-25 Natale", "2026-12-26 Santo Stefano"],
 "nota": "Calcolo indicativo: non ha valore legale."}
```

**Variante FastAPI:**
- **Servizio.** Un'applicazione FastAPI, in un pacchetto proprio, con un endpoint `GET /scadenza` che riceve gli stessi tre argomenti nella query e restituisce lo stesso JSON. Gli errori dello strumento sono risposte `400` con `{"errore": "..."}` e lo stesso testo della variante MCP. FastAPI genera `/openapi.json` e `/docs` (slide 4).
- **Avvio.** Il servizio gira come processo separato su `127.0.0.1:<API_PORTA>`, avviato e spento dall'agente con lo stesso schema del server MCP: porta libera, attesa che risponda, arresto garantito e nessun output nel terminale della chat. Si può avviare anche da solo, con un comando documentato.
- **Pronto vuol dire contratto presente.** Il servizio è considerato pronto quando `/openapi.json` risponde e descrive `/scadenza`, non al primo HTTP 200 — *scelta mia*: coerente con la slide 24.
- **Wrapper nell'agente.** Una funzione registrata con `@tool`, con nome, descrizione e schema scritti a mano e identici al catalogo MCP: un test lo verifica, come per la calcolatrice. La funzione chiama l'endpoint con un client HTTP sincrono e un timeout di 5 secondi (slide 19). Poi:
  - una risposta `400` con `{"errore": ...}` diventa un errore dello strumento;
  - connessione rifiutata, timeout, risposta `5xx` e JSON non valido diventano un errore di collegamento, per esempio *«Servizio scadenze non raggiungibile: …»*;
  - non solleva mai eccezioni verso il grafo.
- **Tipi degli argomenti** — *scelta mia*. Nella query HTTP ogni valore viaggia come testo, quindi il servizio non può distinguere il booleano `true` dalla stringa `"true"`. Per questo:
  - **parità piena** tra le varianti per gli argomenti con il tipo previsto dallo schema: stesso risultato e stesso errore, per esempio data inesistente, `giorni` fuori intervallo, festività fuori dagli anni coperti;
  - **errori di tipo** (argomento mancante, `lavorativi` non booleano, `giorni` non intero): ogni variante deve rifiutarli con un messaggio italiano e senza risultato, ma il testo può essere diverso;
  - **il wrapper resta sottile**, come nella slide 19: converte gli argomenti in parametri di query (`true`/`false`, interi in cifre) e non ripete la validazione. Ogni chiamata arriva al servizio e compare in `servizio_api.log`;
  - **il servizio** interpreta i parametri e rifiuta quelli non validi con un `400` in italiano. Non lascia uscire il `422` in inglese di FastAPI.

### 5.5 Catalogo locale — `search_catalog`, `get_item`

Contratto della slide 28.

**Dati:** un file JSON versionato nel progetto con 10–15 corsi immaginari dell'ITS. Ogni corso ha `codice`, `titolo`, `sede` e `durata_ore` — *scelta mia*: i campi delle slide, con l'unità di misura nel nome. Il contenuto del file è lasciato al costruttore.

**`search_catalog(query, max_results)`**
- `query`: testo obbligatorio, non vuoto. Cerca senza distinguere maiuscole e minuscole, come sottostringa, in codice, titolo e sede — *scelta mia*.
- `max_results`: intero facoltativo, da 1 a 20, predefinito 5 — *scelta mia*.
- **Risultato:** `{"query": ..., "risultati": [{codice, titolo, sede}, ...], "totale": n}`. Nessun risultato non è un errore: la lista è vuota e `totale` vale 0.
- **Errori:** query vuota; `max_results` fuori intervallo o non intero.

**`get_item(code)`**
- `code`: codice esatto. Restituisce il corso completo.
- **Errori:** codice inesistente, con l'invito a usare prima `search_catalog`.

Le due descrizioni devono distinguersi chiaramente (slide 28: «il modello deve scegliere lo strumento corretto»).

### 5.6 Note persistenti — `add_note`, `list_notes`, `delete_note`

Contratto della slide 26. È l'unico strumento con effetti.

**Archivio:**
- un file SQLite in una cartella dati del progetto, esclusa da Git e dall'immagine Docker;
- in Docker la cartella è montata dall'host, così le note sopravvivono al container `--rm`;
- la cartella viene creata se manca;
- il percorso è fisso, perché è un file locale come i log — *scelta mia*. Nei test il server riceve un percorso temporaneo.

**`add_note(text)`**
- **Testo:** obbligatorio, senza spazi all'inizio e alla fine, da 1 a 500 caratteri — *scelta mia*.
- **Risultato:** `{"id": 7, "testo": ..., "creata": "<data e ora ISO con scarto>", "esito": "nota creata"}`. L'ora di creazione è in UTC con scarto esplicito — *scelta mia*: il server non conosce il fuso dell'utente.

**`list_notes(limit)`**
- `limit`: intero facoltativo, da 1 a 50, predefinito 10.
- **Risultato:** le note dalla più recente, `{"note": [...], "totale_archivio": n}`. Un archivio vuoto dà una lista vuota, non un errore.

**`delete_note(note_id)`**
- `note_id`: intero esatto.
- **Risultato:** `{"id": 7, "testo": ..., "esito": "nota eliminata"}`, con il testo eliminato come conferma.
- **Errori:** ID inesistente, senza eliminare nulla.

**Errori comuni:** testo vuoto o troppo lungo; `limit` o `note_id` non validi; archivio non accessibile (file bloccato, cartella non scrivibile), con un messaggio distinto dagli errori di input.

**Eliminazione mai ambigua:** si elimina solo per ID. Il messaggio di sistema dice al modello: se l'utente non indica l'ID, prima elenca le note e chiedi quale eliminare.

**Log:** ogni aggiunta ed eliminazione riuscita scrive nel log del server una riga con l'ID e l'operazione.

### 5.7 Meteo — `get_weather` (MCP sopra un servizio HTTP esterno)

Contratto della slide 27. Il server MCP incapsula l'API pubblica Open-Meteo, che non richiede chiavi.

**`get_weather(city)`**
- `city`: testo obbligatorio, non vuoto.
- **Passo 1:** risolve la città con l'API di geocoding di Open-Meteo, in italiano, chiedendo alcune corrispondenze. Sceglie la prima e la **dichiara** nel risultato: nome, regione, paese e coordinate. Se ce ne sono altre, il risultato ne elenca alcune in `altre_corrispondenze` — *scelta mia*: slide 27, «scelta dichiarata nel risultato, non selezione silenziosa».
- **Passo 2:** chiede le condizioni attuali all'API forecast, con il fuso della località.
- **Risultato:**

  ```json
  {"citta": {"nome": "Udine", "regione": "Friuli Venezia Giulia", "paese": "Italia", "latitudine": 46.06, "longitudine": 13.24},
   "altre_corrispondenze": [],
   "temperatura": {"valore": 8.4, "unita": "°C"},
   "vento": {"valore": 12.0, "unita": "km/h"},
   "condizioni": "parzialmente nuvoloso",
   "ora_riferimento": "2026-11-08T10:15+01:00",
   "fonte": "Open-Meteo"}
  ```

  Le condizioni sono la traduzione italiana del codice meteo WMO restituito dall'API.
- **Errori**, ciascuno con il suo messaggio:
  - città non trovata;
  - timeout;
  - servizio non disponibile, cioè connessione impossibile o risposta `5xx`;
  - risposta non valida, cioè JSON malformato o campi mancanti.

  Gli errori di rete si distinguono sempre da «città non trovata».
- **Tempi:** ogni richiesta a Open-Meteo ha un timeout tale che le due richieste insieme restino sotto il timeout di 10 secondi del ponte MCP, per esempio 4 secondi ciascuna. Così l'errore arriva dal meteo e non dal ponte.
- **Rete:** serve accesso a Internet dal computer o dal container in cui gira il server (slide 27). La diagnosi del README lo dice.

## 6. Varianti e configurazione

**Nuove variabili** in `.env.example`:

| Variabile | Valori | Obbligatoria | Note |
|---|---|---|---|
| `VARIANTE_CALCOLATRICE` | `mcp`, `locale` | sì | quale `calcola` vede il modello |
| `VARIANTE_SCADENZE` | `mcp`, `fastapi` | sì | quale `calcola_scadenza` vede il modello |
| `API_PORTA` | intero tra 1024 e 65535 | solo con `VARIANTE_SCADENZE=fastapi` | porta locale del servizio FastAPI; diversa da `MCP_PORTA` |

- **Obbligatorie** come `MCP_PORTA`, per coerenza con la regola «nessun valore di configurazione nel codice» — *scelta mia*. Un valore mancante o non ammesso dà un errore chiaro, che elenca i valori validi.
- **Il server MCP espone sempre tutti e dieci gli strumenti**, qualunque sia la variante: è un servizio condiviso e non dipende dalla configurazione di un singolo agente. È **l'agente**, come host, a selezionare le capacità consentite (slide 11): se una variante non è `mcp`, toglie dal catalogo scoperto lo strumento con quel nome e al suo posto mette la versione locale o FastAPI.
- **Controllo prima della chat:** nessun nome duplicato tra gli strumenti passati al modello, altrimenti errore di avvio.
- **Benvenuto:** la riga di benvenuto elenca gli strumenti con la loro variante, per esempio `Strumenti: ora_corrente (mcp), calcola (locale), calcola_scadenza (fastapi), …`. Il formato esatto è lasciato al costruttore.

## 7. Avvio, arresto, grafo e terminale

- **Avvio.** La sequenza è quella della specifica del convertitore (sezione 5.3). Se `VARIANTE_SCADENZE=fastapi`, si aggiungono porta libera, avvio, attesa e controllo del servizio FastAPI, prima della chat e con gli stessi criteri di errore e arresto. Attesa massima 10 secondi — *scelta mia*.
- **Arresto.** All'uscita, in ogni caso, vengono spenti tutti i processi avviati. Se uno fallisce a metà avvio, vengono spenti anche quelli già partiti.
- **Servizio che cade a sessione in corso.** Errore di collegamento nel ToolMessage, la chat continua, nessun riavvio. È lo stesso comportamento del server MCP.
- **Grafo.**
  - La struttura resta invariata. Gli strumenti passati a `crea_modello` e `crea_grafo` sono quelli selezionati nella sezione 6.
  - Il limite di giri resta 3. Bastano anche i casi a due passaggi: ricerca e dettaglio nel catalogo, elenco ed eliminazione delle note, orologio e scadenza.
- **Messaggio di sistema.** Alla regola generica del convertitore («per conversioni e calcoli usa sempre gli strumenti») si aggiungono:
  - eliminazione delle note solo per ID, come nella sezione 5.6;
  - se il meteo dichiara una città scelta tra più corrispondenze, dirlo all'utente.

  Il testo esatto è lasciato al costruttore.
- **Terminale.** Per ogni chiamata riuscita nel turno compare una riga con il nome dello strumento, la sua **variante** e gli argomenti principali, per esempio `[calcola · locale: (3 + 4) * 2]` o `[ora_corrente · mcp: Asia/Tokyo]`. È un formato uniforme per tutti gli strumenti: sostituisce `[orologio: …]` di oggi e `[convertitore: …]` della specifica precedente. I test del terminale vanno aggiornati di conseguenza — *scelta mia*: la variante deve essere visibile durante il confronto. Il formato esatto è lasciato al costruttore.

## 8. Log

Stessi due file della specifica del convertitore, più uno:

- **`logs/assistente.log`:** per ogni chiamata il campo `origine` vale `mcp`, `locale` o `fastapi`. All'avvio si registrano anche le varianti scelte. L'esito `errore_collegamento` vale anche per il servizio FastAPI.
- **`logs/server_mcp.log`:** ogni chiamata a ogni strumento, più una riga per ogni aggiunta o eliminazione di note (sezione 5.6).
- **`logs/servizio_api.log`** (nuovo): avvio e arresto del servizio FastAPI, ogni richiesta a `/scadenza` con argomenti ed esito, e l'output del processo.

Una chiamata `calcola` in variante locale compare solo in `assistente.log`, perché non c'è un altro processo. È proprio questa la differenza da osservare.

## 9. Docker

- **Un solo container**, come nella specifica del convertitore. Il servizio FastAPI, quando serve, gira lì accanto al server MCP e all'agente, e la sua porta non va pubblicata.
- **Il `Dockerfile` copia** i nuovi pacchetti (logica, server, servizio) e i file di dati versionati (catalogo, festività).
- **`compose.yaml` monta** sia `./logs` sia la cartella delle note, così log e note restano sull'host.
- **Esclusioni:** la cartella delle note va in `.gitignore` e `.dockerignore`.
- **Rete:** il meteo richiede che il container raggiunga Internet, cosa normale con la rete predefinita di Compose. Va verificato nella prova reale.

## 10. Dipendenze

Le nuove dipendenze dirette vanno concordate con l'utente. Questa specifica le propone; approvarla significa approvarle:

| Pacchetto | Ruolo | Usato da |
|---|---|---|
| `fastapi` | servizio HTTP della variante FastAPI | servizio scadenze |
| `uvicorn` | server ASGI che esegue il servizio FastAPI | servizio scadenze |
| `httpx` | client HTTP sincrono, per il wrapper e per Open-Meteo | agente, server MCP |

- `httpx` e `uvicorn` arrivano già come dipendenze indirette di `fastmcp` e `mcp`. Vanno comunque fissate in `requirements.txt` perché il codice le usa direttamente — *scelta mia*, stessa logica con cui la specifica del convertitore fissa `mcp`.
- **Nessuna libreria per la calcolatrice**, perché basta la libreria standard. **Nessuna per SQLite** (`sqlite3`), **nessuna per le festività**: c'è il file locale.
- **Versioni fissate e verificate nel piano:**
  - compatibilità con Python 3.14;
  - compatibilità con `fastmcp` 3.4.11, `mcp` 1.30.0 e `langchain-mcp-adapters` 0.3.2, soprattutto per la versione di `starlette`, condivisa tra FastAPI e `mcp`;
  - `pip check` pulito.

## 11. Struttura

Tutto dentro `assistente-laboratorio/`. I nomi sono lasciati al costruttore, ma la separazione va rispettata:

- **Un pacchetto di logica pura** con un modulo per strumento: orologio, conversioni, calcolatrice, scadenze, catalogo, note e meteo. Non dipende né da `fastmcp`, né da `fastapi`, né da LangChain. Il modulo `server_mcp/conversioni.py`, già scritto nel Task 1 del piano del convertitore, si sposta qui. Va bene anche tenerlo dov'è, a patto che le altre varianti non importino moduli che dipendono da `fastmcp`. Decide il piano.
- **`server_mcp/`:** solo la registrazione MCP dei dieci strumenti e il punto di avvio.
- **Un pacchetto per il servizio FastAPI:** solo l'endpoint e il punto di avvio.
- **In `assistente/`:**
  - la variante locale della calcolatrice;
  - il wrapper HTTP delle scadenze;
  - la selezione delle varianti;
  - l'avvio e l'arresto del servizio FastAPI, riusando il più possibile l'avvio del server MCP;
  - la rimozione dell'orologio locale;
  - le modifiche minime a configurazione, grafo, terminale e avvio.
- **Dati versionati:** il catalogo e le festività, in una posizione che il server legge e il `Dockerfile` copia.
- **Dati non versionati:** la cartella dell'archivio delle note.

## 12. Ordine di lavoro

- **Il piano del convertitore viene sostituito** dal nuovo piano, a partire dal suo Task 2. Il Task 1 (logica di conversione, già committato) resta. I «fatti verificati nel prototipo» elencati nel vecchio piano restano validi e vanno riportati — *scelta mia*: l'infrastruttura MCP si costruisce una volta sola, già pensata per dieci strumenti e per lo spostamento dell'orologio.
- **Incrementi piccoli e verificati** (per CLAUDE.md), in quest'ordine — *scelta mia*:
  1. infrastruttura MCP con convertitore e orologio spostato, fino alla prova reale;
  2. calcolatrice nelle varianti MCP e locale;
  3. scadenze nelle varianti MCP e FastAPI;
  4. catalogo;
  5. note;
  6. meteo;
  7. Docker e documentazione.

  Ogni incremento finisce con i test automatici verdi e un commit. Le prove reali con LM Studio si fanno almeno alla fine dei passi 1, 3 e 6.
- **Un branch per passo** (decisione dell'utente):
  - ogni passo si sviluppa su un branch proprio, che parte da `dev`, per esempio `dev-infrastruttura-mcp`, `dev-calcolatrice`, `dev-scadenze`, `dev-catalogo`, `dev-note`, `dev-meteo`, `dev-docker-docs`;
  - i nomi usano il trattino perché `dev/...` non si può creare finché esiste il branch `dev`;
  - il merge in `main` avviene **solo con l'approvazione esplicita dell'utente**, passo per passo;
  - se un passo dipende da uno non ancora unito, il suo branch parte da quello precedente, e il merge in `main` segue lo stesso ordine.
- **Correzione del convertitore committata** su `dev` il 2026-11-08 (`02ce50d`): i risultati «troppo grandi» della conversione di temperatura.
- **`.gitattributes` alla radice:** risulta cancellato, ed è fuori da `assistente-laboratorio/`, quindi non si tocca senza indicazione dell'utente.

## 13. Test e verifiche

**Test automatici** (sempre eseguibili, senza LM Studio, Docker né rete):

- **Logica pura**, per ogni strumento, con tutti gli errori della sezione 5. In particolare:
  - **calcolatrice:** precedenze, decimali esatti, ogni tipo di input rifiutato (`__import__('os')`, `2**10000`, `9**9**9`, `1/0`, `2,5`);
  - **scadenze:** a cavallo di festività, weekend e cambio d'anno, `giorni = 0`, date inesistenti, uscita dagli anni coperti;
  - **catalogo:** nessun risultato, `max_results` ai limiti, codice inesistente;
  - **note:** su un database temporaneo, aggiunta, elenco ordinato, eliminazione, ID inesistente senza effetti, persistenza dopo la riapertura del file, archivio non accessibile;
  - **meteo:** con risposte HTTP simulate, senza rete. Risultato corretto, città ambigua dichiarata, città non trovata, timeout, `5xx`, JSON non valido. Gli errori di rete devono essere distinti da «città non trovata»;
  - **orologio:** gli attuali test con istante controllato, spostati.
- **Server MCP** (client in memoria):
  - il catalogo contiene esattamente i dieci nomi, ciascuno con descrizione e schema;
  - una chiamata riuscita e un errore MCP per ciascuno strumento.
- **Varianti a confronto:**
  - per calcolatrice e scadenze, nome, descrizione, argomenti e campi obbligatori sono identici tra il catalogo MCP e la versione locale o FastAPI;
  - per lo stesso input con il tipo previsto, le varianti danno lo stesso risultato e lo stesso messaggio d'errore. Se il calcolo dipende da una data, questa è fissata nell'input. Per gli errori di tipo basta che ogni variante dia un errore senza risultato (sezione 5.4).
- **Servizio FastAPI** (client di test di FastAPI, senza rete): risultato corretto, errore `400` con il testo atteso, `/openapi.json` che descrive `/scadenza`.
- **Wrapper FastAPI:**
  - con trasporto HTTP simulato: successo, errore dello strumento, timeout, connessione rifiutata, `5xx`, JSON non valido, senza mai sollevare eccezioni;
  - con il servizio reale avviato in un processo locale: ciclo completo e nessun processo orfano.
- **Selezione delle varianti:**
  - con ogni combinazione, il modello riceve una sola versione per nome, con l'origine giusta;
  - un nome duplicato dà un errore di avvio;
  - le variabili mancanti o non valide danno errori chiari.
- **Grafo e terminale** con modello finto:
  - ToolMessage correlati;
  - campo `origine` nei log;
  - riga del terminale con la variante;
  - limite di giri invariato.

**Prove reali con LM Studio** (attivate esplicitamente, come oggi). Ogni caso in una sessione nuova. Il criterio dell'utente per il convertitore (5 su 5, correzione ammessa entro il limite di giri, conta l'ultima chiamata del turno) si estende a **tutti** i casi — *scelta mia*.

| Strumento | Caso | Evidenza |
|---|---|---|
| orologio (MCP) | «Che ore sono a Tokyo?» | `ora_corrente` con `Asia/Tokyo`, `origine=mcp` |
| convertitore | i 5 casi della sua specifica | come lì |
| calcolatrice | «Quanto fa (3+4)*2?», una volta con `VARIANTE_CALCOLATRICE=mcp` e una con `locale` | `calcola` chiamato, risposta 14, `origine` corrispondente alla variante |
| scadenze | «Se parto il 23 dicembre 2026, quando scadono 3 giorni lavorativi?», con `mcp` e con `fastapi` | 29 dicembre 2026, `origine` corrispondente, riga in `servizio_api.log` solo con `fastapi` |
| catalogo | una ricerca con risultati, una senza, una domanda che richiede ricerca e poi dettaglio | nessun corso inventato; due chiamate in sequenza nell'ultimo caso |
| note | «Ricordami di consegnare il report venerdì», poi «Elimina la nota 99», poi riavvio ed elenco | una sola `add_note`; errore senza eliminazione; la nota è ancora presente dopo il riavvio |
| meteo | «Che tempo fa a Udine?» | `get_weather` chiamato, città dichiarata nella risposta. Richiede rete |

- **Errore controllato** (slide 23): un'invocazione diretta di ogni strumento con un input non valido, senza passare dal modello, dà un errore e nessun falso risultato. Il fuso `Mars/Olympus` per l'orologio; un'espressione vietata per la calcolatrice, in entrambe le varianti; una data inesistente per le scadenze, in entrambe le varianti.
- **Rischio da dichiarare:** il modello configurato oggi è piccolo (2B) e riceve dieci strumenti. Se la selezione degli strumenti fallisce: al massimo un paio di ritocchi alle descrizioni e al messaggio di sistema, poi si riporta l'esito con le evidenze. **Il cambio di modello lo decide e lo fa l'utente** (decisione dell'utente). Non si dichiara completato un percorso che non lo è.
- **Docker:** avvio con `avvia.ps1` e `VARIANTE_SCADENZE=fastapi`. Una domanda di scadenza e una di meteo. Nell'output compaiono le righe con le varianti, e i log e le note si trovano sull'host.

Ogni resoconto indica cosa è stato eseguito, con quale esito e cosa resta da provare.

## 14. Git e documentazione

- **Git:** un branch per passo come nella sezione 12, merge in `main` solo con l'approvazione esplicita dell'utente, commit in Conventional Commits in italiano, incrementi piccoli verificati, nessun push senza richiesta.
- **README:**
  - le nuove variabili;
  - come scegliere e confrontare le varianti;
  - l'avvio del solo servizio FastAPI, con `/docs`;
  - dove si trovano note, log, catalogo e festività;
  - la diagnosi per livelli, estesa al servizio FastAPI e alla rete per il meteo.

  Solo comandi verificati.
- **`CLAUDE.md`:**
  - aggiornare struttura e comandi;
  - nei «Confini», MCP e gli strumenti della lezione 5 diventano parte del progetto;
  - nell'obiettivo, «nessuna persistenza» resta vero per la cronologia, mentre le note sono l'unica eccezione, voluta.

## 15. Lasciato al costruttore

- Nomi di pacchetti, moduli e funzioni, e posizione dei file di dati.
- Testi esatti di descrizioni, messaggi di errore e messaggio di sistema, nel rispetto della sezione 5.
- Contenuto del catalogo e formato del file delle festività.
- Formato esatto di righe di log, righe del terminale e numeri nei risultati.
- Precisione delle divisioni non esatte della calcolatrice.
- Quanto codice di avvio e arresto condividere tra server MCP e servizio FastAPI.
- Tabella di traduzione dei codici meteo WMO.
