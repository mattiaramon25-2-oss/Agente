# Assistente del laboratorio — specifica

Data: 2026-11-02 · Stato: approvata (2026-11-02)

Le regole generali di lavoro (Git, test, documentazione, confini) sono nel `CLAUDE.md` alla radice della repository e valgono anche qui. Questa specifica le richiama solo dove servono.

## 1. Intento

Esercizio del corso «Deep Learning e LLM: costruire chatbot e agenti». Serve a costruire un assistente da terminale che fa una chat libera su qualsiasi argomento con un modello locale, con il flusso organizzato in un grafo LangGraph leggibile, e a mostrare il tool calling vero: il modello chiede l'ora, il programma la calcola davvero.

È per una sola persona, seduta al PC su cui girano sia l'assistente sia LM Studio.

## 2. Obiettivi

1. Chat da terminale con un modello servito da LM Studio sull'host.
2. Grafo LangGraph esplicito: stato, nodi e instradamento riconoscibili leggendo il codice.
3. Cronologia della conversazione conservata in memoria per la durata della sessione; alla chiusura si perde.
4. Strumento orologio con fuso orario esplicito, chiamato dal modello tramite tool calling ed eseguito dal programma.
5. Il fuso dell'utente viene rilevato automaticamente, anche quando l'assistente gira in Docker.
6. Avvio sia diretto (Python) sia con Docker Compose.

## 3. Non obiettivi

- Nessuna architettura client/server, nessun accesso dalla rete, nessuna sessione multipla. (Discusso e rimandato: forse in una lezione futura.)
- Nessuna persistenza della cronologia tra sessioni.
- Nessun altro strumento oltre all'orologio; niente MCP, RAG, workflow.
- Nessuna interfaccia grafica o web, nessun servizio cloud.
- Nessuna geolocalizzazione: si usa il fuso orario del computer, non la posizione.
- LM Studio non va containerizzato.

## 4. Anti-obiettivi (cose che lo renderebbero un fallimento anche se "funziona")

- L'ora è inventata dal modello invece che calcolata dallo strumento.
- I test passano solo grazie a risposte simulate e vengono presentati come prova che Gemma sa usare lo strumento.
- In Docker l'assistente dice l'ora in UTC invece che nel fuso dell'utente, senza avvisare.
- L'identificativo del modello o l'indirizzo del server sono scritti nel codice.
- Il grafo è nascosto dietro un agente "prefabbricato" che non mostra nodi e instradamento.

## 5. Comportamento

### 5.1 Sessione da terminale

- All'avvio il programma:
  1. legge la configurazione (sezione 6);
  2. verifica che LM Studio risponda (`GET {LMSTUDIO_BASE_URL}/models`) e che l'identificativo configurato sia nell'elenco restituito. Se no, stampa un messaggio chiaro (server irraggiungibile / modello non caricato, con l'elenco dei modelli disponibili) ed esce con codice diverso da zero, senza traceback;
  3. rileva il fuso orario dell'utente (sezione 5.3) e lo mostra in una riga di benvenuto, insieme a come uscire.
- Ciclo: l'utente scrive, l'assistente risponde. Le risposte sono stampate intere a fine generazione (nessuno streaming) — *scelta mia*.
- Uscita: scrivendo `esci` (ignorando maiuscole e spazi), con `Ctrl+C`, o a fine input (EOF). In tutti i casi uscita pulita, senza traceback.
- Riga vuota: ignorata, non viene inviata al modello — *scelta mia*.
- Quando lo strumento viene eseguito, il terminale mostra una riga breve, per esempio `[orologio: Asia/Tokyo]`, così si vede che è stato davvero chiamato — *scelta mia*, utile per la lezione, si può togliere.
- Se una chiamata al modello fallisce a metà sessione (LM Studio chiuso, timeout), viene stampato un errore leggibile e la sessione continua; il messaggio dell'utente che ha causato l'errore non resta nella cronologia — *scelta mia*.

### 5.2 Conversazione e cronologia

- La cronologia contiene messaggi dell'utente, risposte del modello, richieste di strumento e risultati dello strumento, nell'ordine.
- Vive solo nella memoria del processo per la durata della sessione.
- Il messaggio di sistema non è salvato nella cronologia: viene costruito a ogni chiamata del modello a partire dallo stato (così contiene sempre il fuso dell'utente) — *scelta mia*.
- Messaggio di sistema in italiano. Indicazioni minime: sei un assistente utile; rispondi nella lingua in cui scrive l'utente; per data e ora usa sempre lo strumento orologio, non inventarle; il fuso dell'utente è `<fuso>` e va usato quando non viene indicato un altro luogo o fuso; per un luogo indicato scegli il fuso IANA corrispondente.

### 5.3 Fuso orario dell'utente

Deciso con l'utente: il fuso è rilevato **una volta sola, all'inizio della sessione**, e resta nello stato della conversazione per tutta la sessione. Cambi di fuso a programma aperto non vengono visti.

Ordine di rilevamento:

1. **Avvio con Docker tramite `avvia.ps1`:** lo script legge il fuso di Windows (`(Get-TimeZone).Id`, per esempio `W. Europe Standard Time`) e lo passa al container nella variabile `FUSO_HOST_WINDOWS`. Nel container il nome Windows viene convertito in nome IANA (per esempio `Europe/Rome`) usando la tabella di `tzlocal`.
2. **Avvio diretto (fuori da Docker):** il fuso del computer letto con `tzlocal` (che su Windows fa già la conversione). **Dentro un container questo passo viene saltato**, perché `tzlocal` restituirebbe il fuso del container (UTC), non quello dell'utente. Il programma sa di essere in un container grazie a una variabile impostata nel `Dockerfile` (nome suggerito: `ASSISTENTE_IN_DOCKER=1`) — *scelta mia*.
3. **Riserva manuale:** se il rilevamento non riesce (o in Docker senza `avvia.ps1`), si usa `FUSO_ORARIO` dalla configurazione (per esempio `Europe/Rome`).
4. **Ultima risorsa:** `UTC`, con un avviso ben visibile nella riga di benvenuto che spiega come avviare con `avvia.ps1` o impostare `FUSO_ORARIO` — *scelta mia*.

Quindi un avvio Docker senza lo script (per esempio `docker compose run` a mano) funziona, ma usa `FUSO_ORARIO` oppure UTC con avviso: mai UTC in silenzio.

Ogni valore ottenuto viene validato (deve essere un fuso IANA esistente) prima di essere usato. Il fuso in uso è sempre mostrato all'avvio.

### 5.4 Strumento orologio

- Un solo strumento. Nome suggerito: `ora_corrente`.
- Parametro obbligatorio: `fuso`, nome IANA (per esempio `Asia/Tokyo`). Il fuso è sempre esplicito: è il modello a passarlo, usando quello dell'utente se non ne è stato indicato un altro.
- Risultato: testo o JSON leggibile dal modello con data e ora in quel fuso, nome del fuso e scarto da UTC (per esempio `2026-11-02T15:04:05+01:00`, `Europe/Rome`).
- Fuso inesistente: lo strumento non solleva eccezioni verso il grafo, restituisce un messaggio di errore leggibile al modello, che può riprovare o spiegarlo all'utente.
- L'istante corrente è iniettabile (funzione orologio passata dall'esterno), così i test usano un istante fisso.

### 5.5 Grafo

Struttura minima, da rendere riconoscibile nel codice:

- **Stato:** cronologia dei messaggi; fuso dell'utente; contatore dei giri di strumento nel turno corrente (o equivalente).
- **Nodo modello:** chiama il modello con il messaggio di sistema e la cronologia, con lo strumento disponibile.
- **Nodo strumenti:** esegue le chiamate allo strumento richieste dal modello e aggiunge i risultati alla cronologia.
- **Instradamento dopo il nodo modello:** se il modello ha chiesto lo strumento e il limite non è raggiunto → nodo strumenti; altrimenti → fine del turno. Dal nodo strumenti si torna sempre al nodo modello.
- **Limite di giri:** al massimo 3 giri di strumento per ogni messaggio dell'utente — *scelta mia*. Raggiunto il limite, l'utente riceve comunque una risposta leggibile e la cronologia resta valida per i turni successivi (nessuna richiesta di strumento lasciata senza risultato). Come ottenerlo è lasciato al costruttore.
- Il grafo è costruito da una funzione che riceve il modello (e l'orologio) come parametri, così i test possono passare un modello finto.

Si possono usare i componenti di LangGraph per lo stato dei messaggi e per l'esecuzione degli strumenti, purché nodi e instradamento restino dichiarati esplicitamente nel nostro codice. Non usare agenti prefabbricati che nascondono il grafo.

## 6. Configurazione

Solo da variabili d'ambiente; nessun valore di indirizzo o modello nel codice. Nomi — *scelta mia*:

| Variabile | Obbligatoria | Esempio | Note |
|---|---|---|---|
| `LMSTUDIO_BASE_URL` | sì | `http://localhost:1234/v1` | usata nell'avvio diretto |
| `LMSTUDIO_BASE_URL_DOCKER` | sì per Docker | `http://host.docker.internal:1234/v1` | `compose.yaml` la passa al container come `LMSTUDIO_BASE_URL` |
| `LMSTUDIO_MODEL` | sì | `google/gemma-4-e2b` | deve essere uno degli id restituiti da `GET /v1/models` |
| `FUSO_ORARIO` | no | `Europe/Rome` | riserva manuale se il rilevamento fallisce |
| `FUSO_HOST_WINDOWS` | no | `W. Europe Standard Time` | impostata da `avvia.ps1`, non a mano |

- `.env.example` versionato, senza credenziali (LM Studio non ne richiede; se la libreria esige una chiave API, si usa un valore segnaposto fisso nel codice, non una credenziale).
- `.env` reale escluso da Git.
- Avvio diretto: il `.env` viene letto con `python-dotenv`. Docker: Compose legge lo stesso `.env` e imposta nel container `LMSTUDIO_BASE_URL` al valore di `LMSTUDIO_BASE_URL_DOCKER` (sintassi `${...}` di Compose), così nemmeno `compose.yaml` contiene indirizzi scritti a mano — *scelta mia*.
- La verifica all'avvio usa `GET /v1/models`, come chiede il `CLAUDE.md`. Con il caricamento "al volo" di LM Studio l'elenco può includere modelli scaricati ma non ancora caricati in memoria, quindi la prima risposta può essere lenta: le chiamate al modello hanno un timeout generoso e il README lo spiega nella sezione di diagnosi — *scelta mia*.

Modello verificato il 2026-11-02 sul server di LM Studio: `google/gemma-4-e2b` è caricato. È piccolo e potrebbe non usare lo strumento in modo affidabile; alternative presenti sul server: `qwen/qwen3.5-9b`, `qwen/qwen3.8-27b`. Cambiare modello richiede solo di cambiare `LMSTUDIO_MODEL`.

## 7. Docker

- Un `Dockerfile` per l'applicazione e un `compose.yaml` con un solo servizio (l'assistente). LM Studio resta sull'host.
- Il servizio è interattivo (stdin e terminale collegati) e raggiunge l'host tramite `host.docker.internal` (aggiungendo `host-gateway` per compatibilità). Il `Dockerfile` imposta `ASSISTENTE_IN_DOCKER=1` (vedi 5.3).
- `avvia.ps1` (PowerShell, Windows): legge il fuso di Windows e lancia `docker compose run --rm` con `FUSO_HOST_WINDOWS` impostata. È il modo documentato per avviare con Docker.
- Immagine base: Python della stessa serie usata in locale (3.14), variante slim — *scelta mia*, da confermare nel piano verificando la compatibilità delle dipendenze.
- Rischio da verificare nella prova Docker: LM Studio può accettare solo connessioni da `localhost`; potrebbe servire abilitare l'opzione per servire sulla rete locale. Se serve, va scritto nel README.

## 8. Dipendenze

Proposte (versioni fissate nel piano):

- `langgraph` — il grafo (requisito del corso).
- `langchain-openai` — client per l'API compatibile OpenAI di LM Studio, con supporto al tool calling e integrazione diretta con LangGraph.
- `tzlocal` — rilevamento del fuso locale e conversione dei nomi Windows in nomi IANA.
- `tzdata` — database dei fusi orari: su Windows Python non ce l'ha, e serve a `zoneinfo`.
- `python-dotenv` — lettura del `.env` nell'avvio diretto.
- `pytest` — test (solo sviluppo).

Nessun'altra dipendenza senza accordo.

## 9. Struttura

Tutto dentro `assistente-laboratorio/`. Moduli piccoli con questa separazione (nomi lasciati al costruttore):

- configurazione e rilevamento del fuso;
- collegamento al modello (client LM Studio, verifica all'avvio);
- strumenti (orologio);
- grafo (stato, nodi, instradamento);
- interfaccia da terminale (ciclo, uscita, stampa);
- punto di ingresso.

Più: `tests/`, `README.md`, `.env.example`, `.gitignore`, `Dockerfile`, `compose.yaml`, `avvia.ps1`, file delle dipendenze con versioni fissate, `docs/superpowers/` (specifica e piano).

## 10. Test e verifiche

**Test automatici** (sempre eseguibili, senza LM Studio né Docker):

- strumento con istante fisso: fusi diversi, fuso inesistente;
- rilevamento del fuso: conversione da nome Windows, riserva `FUSO_ORARIO`, ripiego su UTC, valori non validi;
- instradamento: con e senza richiesta di strumento, limite di giri;
- grafo con modello finto: risposta diretta; ciclo modello → strumento → modello; cronologia che cresce correttamente tra più turni; limite raggiunto con cronologia valida;
- interfaccia: `esci`, riga vuota, EOF (con ingresso e uscita simulati);
- configurazione: variabili mancanti producono un errore chiaro.

**Prove reali** (separate, attivate esplicitamente, per esempio con un marcatore di pytest o uno script dedicato; mai eseguite di default):

- LM Studio: chiedendo l'ora (con e senza un luogo), Gemma chiama davvero lo strumento: nello stato compare il risultato dello strumento, e l'ora nella risposta corrisponde a quella calcolata.
  - **Criterio deciso con l'utente:** 5 domande sull'ora (con e senza luogo); Gemma deve usare lo strumento in tutte e 5.
  - Se non ci riesce: al massimo un paio di tentativi di miglioramento del messaggio di sistema e della descrizione dello strumento.
  - Se ancora non basta: si riporta il risultato all'utente e si passa a `qwen/qwen3.5-9b` cambiando solo `LMSTUDIO_MODEL`. Il progetto è comunque consegnabile, con il resoconto onesto dell'esito su Gemma.
- Docker: avvio con `avvia.ps1`, collegamento a LM Studio dall'interno del container, fuso dell'utente corretto (non UTC).

Ogni resoconto indica cosa è stato eseguito, con quale esito e cosa resta da provare.

## 11. Git e documentazione

- Repository inizializzata in `progetto_lezione_3/` (fatto il 2026-11-02), branch `master`.
- Commit in Conventional Commits in italiano, incrementi piccoli verificati, come da `CLAUDE.md`.
- README in `assistente-laboratorio/` con configurazione, avvio (diretto e Docker), test, diagnosi; comandi PowerShell; solo comandi verificati.
- Il `CLAUDE.md` va aggiornato con la struttura e i comandi di test quando diventano stabili. Correzione da fare: oggi dice che il file sta dentro `assistente-laboratorio/`, ma sta alla radice della repository.

## 12. Lasciato al costruttore

- Nomi dei moduli, delle funzioni e dei nodi.
- Come realizzare il modello finto nei test.
- Come garantire una cronologia valida al raggiungimento del limite di giri.
- Formato esatto del risultato dello strumento e testo esatto del messaggio di sistema, nel rispetto della sezione 5.
- Meccanismo di attivazione delle prove reali.
- Gestore delle dipendenze e formato del file (purché le versioni siano fissate e i comandi documentati per PowerShell).
