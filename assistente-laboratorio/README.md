# Assistente del laboratorio

Assistente da terminale che conversa con un modello locale servito da LM Studio.
Il flusso è un grafo LangGraph esplicito (`assistente/grafo.py`): il nodo `modello` chiama il modello,
il nodo `strumenti` esegue lo strumento che il modello chiede, il nodo `limite` chiude il turno
dopo 3 giri di strumento. La cronologia resta in memoria per la sessione e si perde alla chiusura;
le uniche informazioni che restano tra una sessione e l'altra sono le note (vedi sotto).

Gli strumenti stanno in un **server MCP** («Strumenti laboratorio», scritto con FastMCP) che
l'assistente avvia da solo, interroga con la discovery (`tools/list`) e spegne all'uscita:

| Strumento | Cosa fa |
|---|---|
| `ora_corrente(fuso)` | data e ora attuali nel fuso IANA indicato, per esempio `Asia/Tokyo` |
| `converti_unita(valore, da, a)` | conversione tra unità metriche di lunghezza, massa e volume, e tra °C e °F |
| `calcola(espressione)` | espressioni aritmetiche con `+ - * / % **` e parentesi, senza `eval`, in aritmetica decimale esatta |
| `search_catalog(query, max_results)` | cerca corsi dell'ITS nel catalogo locale (`risorse/catalogo_corsi.json`) per parole chiave: un corso compare se ogni parola si trova nel titolo, nella sede o nel codice (`Python base` trova «Programmazione in Python di base»; `corsi di Python` no, perché «corsi» non c'è); elenco breve, al massimo 5 risultati se non indicato (1–20); nessun risultato è una lista vuota, non un errore |
| `get_item(code)` | tutti i dettagli (titolo, sede, durata in ore) di un corso dato il codice esatto, per esempio `DLL-01` |
| `add_note(text)` | salva una nota persistente (al massimo 500 caratteri) nell'archivio SQLite `archivio/note.sqlite3`; restituisce ID e data di creazione (UTC) |
| `list_notes(limit)` | elenca le note dalla più recente (10 se non indicato, 1–50); non modifica nulla |
| `delete_note(note_id)` | elimina la nota con l'ID esatto; con un ID inesistente non elimina nulla. Finché il file dell'archivio esiste, gli ID non vengono mai riusati |
| `get_weather(city)` | meteo attuale (temperatura in °C, vento in km/h, condizioni) dal servizio pubblico Open-Meteo, senza chiavi e per uso non commerciale; se il nome è ambiguo sceglie la prima corrispondenza, la dichiara ed elenca gli omonimi; se la località scelta ha un nome diverso da quello chiesto (per esempio `Pordenon` → Pordenone, `Paris` → Parigi) lo dice in una `nota`. Richiede la rete |
| `calcola_scadenza(data_inizio, giorni, lavorativi)` | data di scadenza aggiungendo giorni di calendario o lavorativi (festività nazionali italiane 2026–2028 da `risorse/festivita_italia.json`); risultato indicativo, senza valore legale |

Nome, descrizione e schema degli strumenti arrivano dal server, non sono riscritti nell'assistente.
Ogni chiamata eseguita con successo compare nel terminale con la sua origine, per esempio
`[ora_corrente · mcp: Asia/Tokyo]`.

| Strumento | Varianti possibili | Dove gira | Dove guardare nei log |
|---|---|---|---|
| `ora_corrente` | solo `mcp` | server MCP | `assistente.log`, `server_mcp.log` |
| `converti_unita` | solo `mcp` | server MCP | `assistente.log`, `server_mcp.log` |
| `calcola` | `mcp` oppure `locale` | server MCP, oppure processo dell'assistente | `assistente.log` (`origine=…`); `server_mcp.log` solo con `mcp` |
| `calcola_scadenza` | `mcp` oppure `fastapi` | server MCP, oppure servizio FastAPI | `assistente.log` (`origine=…`); `server_mcp.log` con `mcp`, `servizio_api.log` con `fastapi` |
| `search_catalog`, `get_item` | solo `mcp` | server MCP (legge `risorse/catalogo_corsi.json`) | `assistente.log`, `server_mcp.log` |
| `add_note`, `list_notes`, `delete_note` | solo `mcp` | server MCP (scrive `archivio/note.sqlite3`) | `assistente.log`, `server_mcp.log` (più `modifica note …` per ogni modifica) |
| `get_weather` | solo `mcp` | server MCP, che chiama Open-Meteo su Internet | `assistente.log`, `server_mcp.log` |

Struttura: `logica/` contiene la logica pura degli strumenti, scritta una volta sola e riusata da
tutte le varianti; `server_mcp/` la registrazione MCP; `servizio_api/` il servizio FastAPI delle
scadenze; `assistente/` l'agente (grafo, collegamento al modello, client MCP, varianti, avvio dei
processi, terminale); `risorse/` i dati versionati (catalogo, festività); `archivio/` le note e
`logs/` i log, entrambi fuori da Git.

### Varianti di uno strumento

Per confrontare i modi di collegare uno strumento (lezione 5), alcuni strumenti esistono anche
fuori dal server MCP. Il server li espone sempre tutti; è l'assistente a scegliere quale versione
passare al modello, una sola per nome, secondo il file `.env`:

| Strumento | Variabile | Valori | Dove gira |
|---|---|---|---|
| `calcola` | `VARIANTE_CALCOLATRICE` | `mcp`, `locale` | `mcp`: nel server, via MCP; `locale`: funzione Python con `@tool` nel processo dell'assistente (`assistente/calcolatrice_locale.py`) |
| `calcola_scadenza` | `VARIANTE_SCADENZE` | `mcp`, `fastapi` | `mcp`: nel server, via MCP; `fastapi`: servizio HTTP (`servizio_api/`, avviato dall'assistente sulla porta `API_PORTA`) chiamato da un wrapper scritto a mano e registrato con `@tool` (`assistente/wrapper_scadenze.py`) |

Le due versioni hanno lo stesso nome, la stessa descrizione, lo stesso schema degli argomenti e la
stessa logica (`logica/calcolatrice.py`): cambia solo il percorso. Per confrontarle si fa la stessa domanda
(per esempio «Quanto fa (3+4)*2?») dopo aver cambiato la variabile nel `.env` e riavviato.
La differenza si vede:

- nella riga di benvenuto (`calcola (mcp)` oppure `calcola (locale)`) e nella riga del terminale
  (`[calcola · locale: (3+4)*2]`);
- nei log: con `locale` la chiamata compare solo in `logs/assistente.log` (`origine=locale`),
  perché non c'è un altro processo; con `mcp` compare anche in `logs/server_mcp.log`.

Lo stesso vale per le scadenze («Se parto il 23 dicembre 2026, quando scadono 3 giorni
lavorativi?», risposta 29 dicembre): con `fastapi` la chiamata compare in `logs/assistente.log`
(`origine=fastapi`) e in `logs/servizio_api.log` (`endpoint=/scadenza`), non nel log del server MCP.
Nel wrapper nome, descrizione e schema degli argomenti sono scritti a mano (non c'è discovery): un
test controlla che coincidano con il catalogo MCP. Per argomenti del tipo giusto le due varianti
danno lo stesso risultato e gli stessi errori. Differenze note, dovute ai framework:

- nella richiesta HTTP i valori viaggiano come testo e FastAPI è più tollerante della variante MCP:
  accetta per esempio `lavorativi` scritto `"true"`, `1` o `"yes"`, e `giorni` scritto `"3.0"`,
  che la variante MCP rifiuta;

Un argomento obbligatorio mancante o un argomento inventato dal modello, invece, sono rifiutati
dall'assistente prima di eseguire, con lo stesso messaggio italiano per tutte le varianti
(`Argomenti mancanti per …` oppure `Argomenti non previsti per …: … Usa solo: …`): in quel caso la
chiamata non arriva né al server né al servizio, e compare solo in `logs/assistente.log`.

## Requisiti

- Python 3.14
- LM Studio sullo stesso computer, con il server attivo (porta predefinita 1234) e un modello
  scaricato. Provato con `google/gemma-4-e2b`.

## Configurazione

Tutti i comandi si eseguono in PowerShell dalla cartella `assistente-laboratorio`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Poi aprire `.env` e controllare i valori:

| Variabile | Obbligatoria | Significato |
|---|---|---|
| `LMSTUDIO_BASE_URL` | sì | indirizzo del server di LM Studio, per esempio `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL` | sì | identificativo del modello, come restituito da `GET /v1/models` |
| `LMSTUDIO_BASE_URL_DOCKER` | solo per Docker | indirizzo di LM Studio visto dal container |
| `MCP_PORTA` | sì | porta locale del server MCP (intero tra 1024 e 65535), per esempio `8765` |
| `VARIANTE_CALCOLATRICE` | sì | `mcp` oppure `locale`: quale versione di `calcola` vede il modello |
| `VARIANTE_SCADENZE` | sì | `mcp` oppure `fastapi`: quale versione di `calcola_scadenza` vede il modello |
| `API_PORTA` | solo con `fastapi` | porta locale del servizio FastAPI, diversa da `MCP_PORTA`, per esempio `8766` |
| `FUSO_ORARIO` | no | fuso IANA di riserva se il rilevamento automatico non riesce |

Per vedere gli identificativi disponibili:

```powershell
(Invoke-RestMethod http://localhost:1234/v1/models).data.id
```

Nessuna credenziale è necessaria: il file `.env` resta fuori da Git.

Chi ha già un `.env` creato prima del server MCP deve aggiungere a mano le righe nuove di
`.env.example` (`MCP_PORTA=8765`, `VARIANTE_CALCOLATRICE=mcp`, `VARIANTE_SCADENZE=mcp`,
`API_PORTA=8766`): senza, l'avvio si ferma con
`Variabili d'ambiente mancanti: …` e il nome delle variabili.

## Avvio diretto

```powershell
.\.venv\Scripts\Activate.ps1
python -m assistente
```

All'avvio il programma controlla che LM Studio risponda e che il modello configurato sia
nell'elenco, avvia il server MCP sulla porta `MCP_PORTA` e aspetta che risponda alla discovery,
poi mostra il fuso orario in uso e gli strumenti disponibili con la loro origine.
Si esce scrivendo `esci`, con `Ctrl+C` o a fine input: il server viene spento in ogni caso.

Esempio (ingresso inviato con una pipe):

```powershell
"che ore sono a Tokyo?", "quanti metri sono 2,5 km?", "esci" | python -m assistente
```

```
Assistente del laboratorio
Fuso orario: Europe/Berlin (computer locale)
Strumenti: converti_unita (mcp), ora_corrente (mcp), calcola (mcp), calcola_scadenza (mcp), search_catalog (mcp), get_item (mcp), add_note (mcp), list_notes (mcp), delete_note (mcp), get_weather (mcp)
Scrivi «esci» o premi Ctrl+C per uscire.
Tu: [ora_corrente · mcp: Asia/Tokyo]
Assistente: Attualmente a Tokyo sono le 04:13 del lunedì, 9 novembre 2026.
Tu: [converti_unita · mcp: 2.5, km, m]
Assistente: 2,5 km sono 2500 metri.
Tu: Arrivederci.
```

### Il server MCP da solo

Il server si può avviare anche senza l'assistente, per provarlo con MCP Inspector o con un altro
client MCP; ascolta solo su `127.0.0.1`, all'indirizzo `http://127.0.0.1:8765/mcp`:

```powershell
python -m server_mcp --porta 8765
```

Così avviato, il server usa l'archivio delle note reale (`archivio/note.sqlite3`); per provarlo
senza toccarlo si indica un altro file con `--note`, per esempio
`python -m server_mcp --porta 8765 --note prova.sqlite3`.

### Il servizio FastAPI da solo

Anche il servizio delle scadenze si può avviare da solo; FastAPI genera la descrizione OpenAPI
(`http://127.0.0.1:8766/openapi.json`) e una pagina interattiva per provarlo
(`http://127.0.0.1:8766/docs`):

```powershell
python -m servizio_api --porta 8766
```

Esempio di richiesta: `http://127.0.0.1:8766/scadenza?data_inizio=2026-12-23&giorni=3&lavorativi=true`.
Gli errori sono risposte `400` con `{"errore": "..."}` in italiano.

## Ambito e router

Prima dell'agente, un nodo `router` usa lo stesso modello di LM Studio (senza strumenti, con output
strutturato) per decidere se la domanda è `conversazione` o `fuori_ambito`. L'ambito e il testo del
rifiuto stanno in `risorse/ambito.json`: per cambiarli si modifica quel file, non il codice (vale al
riavvio). Le domande fuori ambito ricevono il rifiuto senza raggiungere l'agente; domanda e rifiuto
restano nella cronologia. Se il router restituisce un output non valido la domanda passa comunque
all'agente e il log lo registra con `esito=errore`.

## Log

Ogni chiamata a uno strumento lascia una traccia nei file della cartella `logs/` (fuori da Git;
con Docker è montata sull'host):

- `logs/assistente.log`: a ogni turno la riga del router (`nodo=router categoria=… motivo=… esito=…`),
  poi `nodo=modello` a ogni passaggio dall'agente oppure `nodo=rifiuto`; avvio e arresto del
  server, catalogo scoperto e, per ogni chiamata,
  `origine`, `tool`, `call_id`, `argomenti`, `esito` (`ok`, `errore_tool`, `errore_collegamento`,
  `strumento_sconosciuto`, `limite`), `risultato` e `tool_message.call_id`;
- `logs/server_mcp.log`: ogni chiamata ricevuta dal server con argomenti ed esito, più l'output
  della libreria MCP; ogni aggiunta o eliminazione di una nota riuscita lascia anche una riga
  `modifica note operazione=aggiunta|eliminazione id=…`;
- `logs/servizio_api.log` (solo con `VARIANTE_SCADENZE=fastapi`): avvio e arresto del servizio e
  ogni richiesta a `/scadenza` con argomenti ed esito.

Il `call_id` del modello non arriva al server (l'identificativo del protocollo è un altro): le due
tracce si confrontano per strumento, argomenti e ora. Una risposta plausibile senza la riga
`origine=… tool=…` in `assistente.log` (con `origine` uguale a `mcp`, `locale` o `fastapi`) non
dimostra che lo strumento sia stato usato.

## Avvio con Docker

Serve Docker Desktop acceso. LM Studio resta sull'host: il container lo raggiunge all'indirizzo
`LMSTUDIO_BASE_URL_DOCKER` del file `.env` (`http://host.docker.internal:1234/v1`), che
`compose.yaml` passa all'applicazione come `LMSTUDIO_BASE_URL`. Su questo computer non è
servito attivare in LM Studio l'opzione per servire sulla rete locale.

```powershell
docker compose build
.\avvia.ps1
```

Il server MCP (e, con `VARIANTE_SCADENZE=fastapi`, il servizio FastAPI) gira nello stesso container
dell'assistente: le porte non vengono pubblicate. `compose.yaml` richiede `MCP_PORTA`,
`VARIANTE_CALCOLATRICE` e `VARIANTE_SCADENZE` nel file `.env` e monta `./logs` e `./archivio`:
log e note restano sull'host anche dopo `--rm` (verificato: una nota scritta in un container si
ritrova sull'host e da un container nuovo; le cartelle vengono create se mancano). Il meteo usa la
rete del container: in un container senza interfaccia di rete risponde subito `Servizio meteo non
disponibile`, distinto da `Città non trovata`; con rete ma senza Internet l'errore arriva entro la
scadenza totale di 8 secondi (verificata dai test automatici, non in Docker). Per provare le varianti nel container senza cambiare il `.env`:

```powershell
"Che tempo fa a Udine?", "esci" | docker compose run --rm -T -e VARIANTE_SCADENZE=fastapi -e API_PORTA=8766 -e VARIANTE_CALCOLATRICE=locale assistente
```

Perché lo script: dentro il container il fuso del sistema è UTC, non quello dell'utente.
`avvia.ps1` legge il fuso di Windows (`(Get-TimeZone).Id`, per esempio `W. Europe Standard Time`)
e lo passa al container in `FUSO_HOST_WINDOWS`; la riga di benvenuto mostra
`Fuso orario: Europe/Berlin (host Windows)`.

Avviando a mano senza lo script, il fuso viene da `FUSO_ORARIO` del file `.env`
(`Fuso orario: Europe/Rome (FUSO_ORARIO)`); se manca anche quello si usa UTC con un avviso.
Con l'ingresso da una pipe serve l'opzione `-T`:

```powershell
"Che ore sono?", "esci" | docker compose run --rm -T assistente
```

> Verificato con ingresso da pipe (`avvia.ps1 -SenzaTty` e il comando sopra). L'avvio interattivo
> `.\avvia.ps1` da tastiera va ancora confermato.

## Test

Test automatici (non servono né LM Studio né Docker; il modello è simulato):

```powershell
python -m pytest
```

Alcuni test avviano il server MCP reale su una porta libera (senza modello): richiedono
qualche secondo ciascuno.

Le prove reali sono saltate (`skipped`) se non vengono richieste esplicitamente.
Prova reale con LM Studio acceso, ogni domanda in una sessione nuova:

- cinque domande su ora e data: il modello deve chiamare davvero `ora_corrente` (via MCP) con il
  fuso giusto; per le quattro domande sull'ora l'ora della risposta deve essere quella calcolata,
  per «Che giorno è oggi?» la risposta deve contenere il giorno della settimana o il giorno del mese
  restituiti dallo strumento; più un errore controllato (`Mars/Olympus` passato direttamente allo
  strumento, senza modello);
- cinque domande di conversione: l'ultima chiamata a `converti_unita` del turno deve avere gli
  argomenti giusti e il numero della risposta deve coincidere con il risultato dello strumento;
- «Quanto fa (3+4)*2?» una volta con la calcolatrice `mcp` e una con quella `locale`: il risultato
  deve essere 14 e il log deve riportare l'origine giusta; più un errore controllato
  (`__import__('os')` passato direttamente allo strumento) in entrambe le varianti;
- «Se parto il 23 dicembre 2026, quando scadono 3 giorni lavorativi?» una volta con le scadenze
  `mcp` e una con `fastapi`: la scadenza deve essere il 29 dicembre 2026 e, solo con `fastapi`,
  `logs/servizio_api.log` deve avere la riga della richiesta; più un errore controllato
  (data `2026-02-30`) in entrambe le varianti;
- catalogo: «Quali corsi di Python ci sono nel catalogo?» (una `search_catalog` con risultati),
  «C'è un corso di astrofisica?» (nessun risultato e nessun codice inventato nella risposta),
  «Quante ore dura il corso di Deep Learning e LLM?» (`search_catalog` e poi `get_item` con
  `DLL-01` nello stesso turno, risposta 120); più un errore controllato (`get_item` con `XX-99`);
- note, su un archivio temporaneo (mai quello reale): «Ricordami di consegnare il report venerdì»
  (una sola `add_note`), «Elimina la nota 99» (errore, nessuna eliminazione), riavvio e «Quali note
  ho salvato?» (la nota c'è ancora); «Elimina la nota sul report» è solo osservato e riportato;
- router: «che ore sono a Tokyo?» (riga `nodo=router categoria=conversazione`, poi `nodo=modello`
  e la chiamata a `ora_corrente`) e «scrivimi una poesia sul mare» (riga
  `categoria=fuori_ambito`, `nodo=rifiuto`, il testo del rifiuto e nessuna riga `nodo=modello`);
- meteo (serve la rete): «Che tempo fa a Udine?» (una `get_weather` riuscita e la temperatura
  restituita nella risposta); più un errore controllato (città `Xqzvbnmlkj`, «Città non trovata»).

Le prove reali leggono le variabili dal `.env`; calcolatrice e scadenze vengono forzate a
ciascuna variante dal test stesso.

```powershell
python -m pytest --lmstudio -m lmstudio -v -s
```

Prova reale con Docker (Docker Desktop e LM Studio accesi): costruisce l'immagine, avvia con
`avvia.ps1 -SenzaTty` e controlla che il fuso venga dall'host Windows e che l'orologio sia chiamato;
poi avvia con `docker compose run` senza lo script e controlla che si usi `FUSO_ORARIO`; fa una
conversione nel container e controlla le righe nei log sull'host; con le varianti `fastapi` e
`locale` chiede una scadenza e il meteo (e osserva la richiesta di una nota); verifica che una nota
scritta nel container resti nel volume; infine chiama il meteo in un container senza rete e
controlla che l'errore arrivi dal meteo entro 8 secondi. Durante la prova `logs/` e `archivio/`
dell'utente vengono spostati da parte (in `logs.riserva-prova-docker/` e
`archivio.riserva-prova-docker/`, ignorate da Git) e poi ripristinati; se una prova venisse
interrotta a forza, basta rinominarle di nuovo in `logs/` e `archivio/`. Non usare l'assistente
mentre gira la prova Docker.

```powershell
python -m pytest --docker -m docker -v -s
```

Il fuso dell'utente è rilevato una volta sola all'avvio, in quest'ordine:

1. `FUSO_HOST_WINDOWS` (impostata dallo script di avvio con Docker), convertita in nome IANA;
2. fuso del computer (solo fuori da Docker);
3. `FUSO_ORARIO` dal file `.env`;
4. `UTC`, con un avviso ben visibile nella riga di benvenuto.

## Diagnosi

Conviene procedere per livelli, dal basso: configurazione (`.env`), LM Studio, server MCP, servizio
FastAPI (solo con `VARIANTE_SCADENZE=fastapi`), rete (solo per il meteo), archivio delle note, e
infine il modello. Un errore di un livello basso non si risolve cambiando il messaggio di sistema.

- **`Impossibile raggiungere LM Studio all'indirizzo …`**: LM Studio è chiuso, il server non è
  attivo, oppure `LMSTUDIO_BASE_URL` è sbagliato. Il programma esce con codice 1.
- **`Il modello '…' non è disponibile su LM Studio`**: l'identificativo in `LMSTUDIO_MODEL` non è
  tra quelli restituiti dal server; il messaggio li elenca. Si possono vedere anche con
  `(Invoke-RestMethod http://localhost:1234/v1/models).data.id`.
- **`Variabili d'ambiente mancanti`**: manca il file `.env` (copiarlo da `.env.example`) o una variabile è vuota.
- **La prima risposta è lenta**: l'elenco di LM Studio può includere modelli scaricati ma non
  ancora caricati in memoria; il primo messaggio li carica. Le chiamate hanno un timeout di 120 secondi.
- **`required variable LMSTUDIO_BASE_URL_DOCKER is missing a value`** (con Docker): aggiungere
  `LMSTUDIO_BASE_URL_DOCKER` al file `.env`, come in `.env.example`.
- **Il container non raggiunge LM Studio** (`Impossibile raggiungere LM Studio all'indirizzo
  http://host.docker.internal:1234/v1/models`): controllare che il server di LM Studio sia attivo;
  se basta da fuori ma non dal container, attivare in LM Studio l'opzione per servire sulla rete locale.
- **`.\avvia.ps1` non può essere eseguito perché l'esecuzione di script è disabilitata**: avviarlo
  con `powershell -NoProfile -ExecutionPolicy Bypass -File .\avvia.ps1`, che vale solo per quel comando.
- **Il server MCP**, per livelli (dal processo alla risposta del modello):

  | Sintomo | Cosa controllare |
  |---|---|
  | `Porta … già in uso` | un altro programma (o un server rimasto acceso) usa `MCP_PORTA`: chiuderlo o cambiare porta nel `.env` |
  | `Il server MCP non è partito` | il messaggio riporta le ultime righe di `logs/server_mcp.log`: interprete, dipendenze (`pip install -r requirements-dev.txt`), percorsi |
  | processo attivo, catalogo assente (`non espone nessuno strumento`) | versioni di `fastmcp`, `mcp` e `langchain-mcp-adapters` come in `requirements.txt` |
  | `Server MCP non raggiungibile` o `nessuna risposta entro 10 secondi` durante la chat | il server è caduto o è bloccato: vedere `logs/server_mcp.log`; l'assistente non lo riavvia |
  | strumento nel catalogo ma nessuna chiamata (nessuna riga `[… · mcp: …]`) | descrizione dello strumento, messaggio di sistema, supporto al tool calling del modello |
  | risultato corretto nel log ma risposta sbagliata | ToolMessage e cronologia in `logs/assistente.log`, interpretazione del modello |

  Un processo acceso o un HTTP 200 non bastano: l'assistente considera pronto il server solo quando
  la discovery (`tools/list`) riesce.
- **`required variable MCP_PORTA is missing a value`** (con Docker): aggiungere `MCP_PORTA=8765` al file `.env`;
  lo stesso per `VARIANTE_CALCOLATRICE` e `VARIANTE_SCADENZE`.
- **`VARIANTE_CALCOLATRICE non valida`**: i valori ammessi sono `mcp` e `locale`.
- **`VARIANTE_SCADENZE non valida`**: i valori ammessi sono `mcp` e `fastapi`.
- **Il servizio FastAPI** (solo con `VARIANTE_SCADENZE=fastapi`):

  | Sintomo | Cosa controllare |
  |---|---|
  | `Porta … già in uso: … API_PORTA` | un altro programma usa `API_PORTA`: chiuderlo o cambiare porta nel `.env` |
  | `API_PORTA deve essere diversa da MCP_PORTA` | le due porte nel `.env` coincidono |
  | `Il servizio FastAPI non è partito` | ultime righe di `logs/servizio_api.log`: dipendenze (`fastapi`, `uvicorn`), percorsi |
  | `Servizio scadenze non raggiungibile` o `nessuna risposta entro 5 secondi` durante la chat | il servizio è caduto o bloccato: `logs/servizio_api.log`; l'assistente non lo riavvia |

  L'assistente considera pronto il servizio solo quando `/openapi.json` descrive `/scadenza`,
  non al primo HTTP 200.
- **Il meteo**: richiede l'accesso a Internet dal computer o dal container in cui gira il server.
  `Servizio meteo non disponibile` o `nessuna risposta entro 4 secondi` (per una fase della richiesta)
  o `entro 8 secondi` (per l'intero strumento, risoluzione del nome compresa) indicano un problema di
  rete o di Open-Meteo; il limite di 8 secondi resta sotto i 10 del collegamento MCP, così l'errore
  arriva dal meteo e non come `Server MCP: nessuna risposta`; `Città non trovata` indica invece che la rete funziona ma il nome non corrisponde
  a nessuna località. `Risposta non valida dal servizio meteo` indica una risposta inattesa di Open-Meteo.
  I test automatici non usano la rete: le risposte di Open-Meteo sono simulate.
- **Le note**: l'archivio è il file `archivio/note.sqlite3`, fuori da Git e dall'immagine Docker
  (con Docker la cartella è montata dall'host). Per svuotarlo si cancella il file con l'assistente
  spento. Il modello elimina solo per ID: se l'ID non è indicato, il messaggio di sistema gli chiede
  di elencare le note e chiedere quale eliminare (con una sola nota corrispondente un modello
  piccolo può eliminarla direttamente). `Archivio delle note non accessibile`: il file è bloccato da
  un altro programma, è danneggiato o la cartella non è scrivibile. Non usare nello stesso momento
  l'assistente avviato direttamente e quello in Docker: condividono il file e su Windows i blocchi
  di SQLite tra host e container non sono affidabili.
- **Il catalogo**: il file `risorse/catalogo_corsi.json` (lista di corsi con `codice`, `titolo`,
  `sede`, `durata_ore`) si può modificare; il server lo legge solo all'avvio, quindi dopo una
  modifica va riavviato l'assistente. Con Docker il file è copiato nell'immagine: prima di
  `.\avvia.ps1` serve `docker compose build` (lo stesso vale per `risorse/festivita_italia.json`).
  Se il file non è valido (lista vuota, campo mancante, durata non positiva, codice vuoto, con
  spazi o duplicato) il server non parte e le ultime righe di `logs/server_mcp.log`, riportate
  nell'errore di avvio, contengono `Catalogo non valido` con il motivo. Il file va salvato in
  UTF-8 senza BOM.
- **`Festività disponibili solo per gli anni 2026–2028`**: con `lavorativi=true` il calcolo è
  uscito dagli anni del file `risorse/festivita_italia.json`; per altri anni va aggiornato il file.
- **La calcolatrice rifiuta un'espressione** (`Carattere non consentito`, `Operazione non consentita`,
  `Esponente non ammesso`): è voluto. Sono ammessi solo numeri con il punto decimale, `+ - * / % **`
  e parentesi; niente funzioni, nomi, `//` o notazione scientifica, esponenti interi fino a 1000.
- **Il modello ogni tanto risponde senza usare lo strumento** (per esempio fa un calcolo a mente,
  oppure dopo un errore dello strumento non riprova): con dieci strumenti un modello piccolo come
  `google/gemma-4-e2b` non è sempre affidabile. Il caso più insidioso osservato: risponde «Ho salvato
  la nota» senza aver chiamato `add_note` (circa una volta su tre nelle prove), quindi la nota non
  esiste. Lo si riconosce perché nel terminale manca la riga `[add_note · mcp: …]` e in
  `logs/server_mcp.log` manca `modifica note operazione=aggiunta`. Nei log manca la riga `origine=… tool=…`. Si
  può riprovare la domanda o scegliere un modello più grande cambiando solo `LMSTUDIO_MODEL`.
- **`Fuso orario: Europe/Berlin` anche se si è in Italia**: Windows chiama il fuso dell'Europa centrale
  `W. Europe Standard Time`, che la tabella standard traduce in `Europe/Berlin`. È la stessa ora di Roma.
