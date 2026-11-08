# Assistente del laboratorio

Assistente da terminale che conversa con un modello locale servito da LM Studio.
Il flusso è un grafo LangGraph esplicito (`assistente/grafo.py`): il nodo `modello` chiama il modello,
il nodo `strumenti` esegue lo strumento che il modello chiede, il nodo `limite` chiude il turno
dopo 3 giri di strumento. La cronologia resta in memoria per la sessione e si perde alla chiusura.

Gli strumenti stanno in un **server MCP** («Strumenti laboratorio», scritto con FastMCP) che
l'assistente avvia da solo, interroga con la discovery (`tools/list`) e spegne all'uscita:

| Strumento | Cosa fa |
|---|---|
| `ora_corrente(fuso)` | data e ora attuali nel fuso IANA indicato, per esempio `Asia/Tokyo` |
| `converti_unita(valore, da, a)` | conversione tra unità metriche di lunghezza, massa e volume, e tra °C e °F |
| `calcola(espressione)` | espressioni aritmetiche con `+ - * / % **` e parentesi, senza `eval`, in aritmetica decimale esatta |
| `calcola_scadenza(data_inizio, giorni, lavorativi)` | data di scadenza aggiungendo giorni di calendario o lavorativi (festività nazionali italiane 2026–2028 da `risorse/festivita_italia.json`); risultato indicativo, senza valore legale |

Nome, descrizione e schema degli strumenti arrivano dal server, non sono riscritti nell'assistente.
Ogni chiamata eseguita con successo compare nel terminale con la sua origine, per esempio
`[ora_corrente · mcp: Asia/Tokyo]`.

Struttura: `logica/` contiene la logica pura degli strumenti, `server_mcp/` la registrazione MCP,
`assistente/` l'agente (grafo, collegamento al modello, client MCP, avvio dei processi, terminale).

### Varianti di uno strumento

Per confrontare i modi di collegare uno strumento (lezione 5), alcuni strumenti esistono anche
fuori dal server MCP. Il server li espone sempre tutti; è l'assistente a scegliere quale versione
passare al modello, una sola per nome, secondo il file `.env`:

| Strumento | Variabile | Valori | Dove gira |
|---|---|---|---|
| `calcola` | `VARIANTE_CALCOLATRICE` | `mcp`, `locale` | `mcp`: nel server, via MCP; `locale`: funzione Python con `@tool` nel processo dell'assistente (`assistente/calcolatrice_locale.py`) |
| `calcola_scadenza` | `VARIANTE_SCADENZE` | `mcp`, `fastapi` | `mcp`: nel server, via MCP; `fastapi`: servizio HTTP (`servizio_api/`, avviato dall'assistente sulla porta `API_PORTA`) chiamato da un wrapper scritto a mano e registrato con `@tool` (`assistente/wrapper_scadenze.py`) |

Le due versioni hanno lo stesso nome, la stessa descrizione, lo stesso schema degli argomenti e la
stessa logica (`logica/calcolatrice.py`): cambia solo il percorso. Unica differenza dovuta ai
framework: FastMCP rifiuta un argomento in più che il modello dovesse inventare, mentre `@tool` lo
ignora. Per confrontarle si fa la stessa domanda
(per esempio «Quanto fa (3+4)*2?») dopo aver cambiato la variabile nel `.env` e riavviato.
La differenza si vede:

- nella riga di benvenuto (`calcola (mcp)` oppure `calcola (locale)`) e nella riga del terminale
  (`[calcola · locale: (3+4)*2]`);
- nei log: con `locale` la chiamata compare solo in `logs/assistente.log` (`origine=locale`),
  perché non c'è un altro processo; con `mcp` compare anche in `logs/server_mcp.log`.

Lo stesso vale per le scadenze («Se parto il 23 dicembre 2026, quando scadono 3 giorni
lavorativi?», risposta 29 dicembre): con `fastapi` la chiamata compare in `logs/assistente.log`
(`origine=fastapi`) e in `logs/servizio_api.log` (`endpoint=/scadenza`), non nel log del server MCP.
Nel wrapper nome, descrizione e schema sono scritti a mano (non c'è discovery): un test controlla
che coincidano con il catalogo MCP. Nella richiesta HTTP i valori viaggiano come testo, quindi per
gli argomenti di tipo sbagliato le due varianti danno entrambe un errore in italiano, ma con testi
che possono differire.

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
Strumenti: converti_unita (mcp), ora_corrente (mcp), calcola (mcp)
Scrivi «esci» o premi Ctrl+C per uscire.
Tu: [ora_corrente · mcp: Asia/Tokyo]
Assistente: Attualmente a Tokyo sono le ore **23:23:46** di domenica 8 novembre 2026.
Tu: [converti_unita · mcp: 2.5, km, m]
Assistente: 2,5 km sono **2500 metri**.
Tu: Arrivederci.
```

### Il server MCP da solo

Il server si può avviare anche senza l'assistente, per provarlo con MCP Inspector o con un altro
client MCP; ascolta solo su `127.0.0.1`, all'indirizzo `http://127.0.0.1:8765/mcp`:

```powershell
python -m server_mcp --porta 8765
```

### Il servizio FastAPI da solo

Anche il servizio delle scadenze si può avviare da solo; FastAPI genera la descrizione OpenAPI
(`http://127.0.0.1:8766/openapi.json`) e una pagina interattiva per provarlo
(`http://127.0.0.1:8766/docs`):

```powershell
python -m servizio_api --porta 8766
```

Esempio di richiesta: `http://127.0.0.1:8766/scadenza?data_inizio=2026-12-23&giorni=3&lavorativi=true`.
Gli errori sono risposte `400` con `{"errore": "..."}` in italiano.

## Log

Ogni chiamata a uno strumento lascia una traccia in due file della cartella `logs/` (fuori da Git;
con Docker è montata sull'host):

- `logs/assistente.log`: avvio e arresto del server, catalogo scoperto e, per ogni chiamata,
  `origine`, `tool`, `call_id`, `argomenti`, `esito` (`ok`, `errore_tool`, `errore_collegamento`,
  `strumento_sconosciuto`, `limite`), `risultato` e `tool_message.call_id`;
- `logs/server_mcp.log`: ogni chiamata ricevuta dal server con argomenti ed esito, più l'output
  della libreria MCP;
- `logs/servizio_api.log` (solo con `VARIANTE_SCADENZE=fastapi`): avvio e arresto del servizio e
  ogni richiesta a `/scadenza` con argomenti ed esito.

Il `call_id` del modello non arriva al server (l'identificativo del protocollo è un altro): le due
tracce si confrontano per strumento, argomenti e ora. Una risposta plausibile senza la riga
`origine=mcp tool=…` in `assistente.log` non dimostra che lo strumento sia stato usato.

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
`VARIANTE_CALCOLATRICE` e `VARIANTE_SCADENZE` nel file `.env` e monta `./logs`, così i log restano sull'host.

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

- cinque domande sull'ora: il modello deve chiamare davvero `ora_corrente` (via MCP) con il fuso
  giusto e l'ora della risposta deve essere quella calcolata; più un errore controllato
  (`Mars/Olympus` passato direttamente allo strumento, senza modello);
- cinque domande di conversione: l'ultima chiamata a `converti_unita` del turno deve avere gli
  argomenti giusti e il numero della risposta deve coincidere con il risultato dello strumento;
- «Quanto fa (3+4)*2?» una volta con la calcolatrice `mcp` e una con quella `locale`: il risultato
  deve essere 14 e il log deve riportare l'origine giusta; più un errore controllato
  (`__import__('os')` passato direttamente allo strumento) in entrambe le varianti;
- «Se parto il 23 dicembre 2026, quando scadono 3 giorni lavorativi?» una volta con le scadenze
  `mcp` e una con `fastapi`: la scadenza deve essere il 29 dicembre 2026 e, solo con `fastapi`,
  `logs/servizio_api.log` deve avere la riga della richiesta; più un errore controllato
  (data `2026-02-30`) in entrambe le varianti.

Le prove reali leggono le variabili dal `.env`; calcolatrice e scadenze vengono forzate a
ciascuna variante dal test stesso.

```powershell
python -m pytest --lmstudio -m lmstudio -v -s
```

Prova reale con Docker (Docker Desktop e LM Studio accesi): costruisce l'immagine, avvia con
`avvia.ps1 -SenzaTty` e controlla che il fuso venga dall'host Windows e che l'orologio sia chiamato;
poi avvia con `docker compose run` senza lo script e controlla che si usi `FUSO_ORARIO`; infine
fa una conversione nel container e controlla le righe nei log sull'host.

```powershell
python -m pytest --docker -m docker -v -s
```

Il fuso dell'utente è rilevato una volta sola all'avvio, in quest'ordine:

1. `FUSO_HOST_WINDOWS` (impostata dallo script di avvio con Docker), convertita in nome IANA;
2. fuso del computer (solo fuori da Docker);
3. `FUSO_ORARIO` dal file `.env`;
4. `UTC`, con un avviso ben visibile nella riga di benvenuto.

## Diagnosi

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
  lo stesso per `VARIANTE_CALCOLATRICE`.
- **`VARIANTE_CALCOLATRICE non valida`**: i valori ammessi sono `mcp` e `locale`.
- **Il servizio FastAPI** (solo con `VARIANTE_SCADENZE=fastapi`):

  | Sintomo | Cosa controllare |
  |---|---|
  | `Porta … già in uso: … API_PORTA` | un altro programma usa `API_PORTA`: chiuderlo o cambiare porta nel `.env` |
  | `API_PORTA deve essere diversa da MCP_PORTA` | le due porte nel `.env` coincidono |
  | `Il servizio FastAPI non è partito` | ultime righe di `logs/servizio_api.log`: dipendenze (`fastapi`, `uvicorn`), percorsi |
  | `Servizio scadenze non raggiungibile` o `nessuna risposta entro 5 secondi` durante la chat | il servizio è caduto o bloccato: `logs/servizio_api.log`; l'assistente non lo riavvia |

  L'assistente considera pronto il servizio solo quando `/openapi.json` descrive `/scadenza`,
  non al primo HTTP 200.
- **`Festività disponibili solo per gli anni 2026–2028`**: con `lavorativi=true` il calcolo è
  uscito dagli anni del file `risorse/festivita_italia.json`; per altri anni va aggiornato il file.
- **La calcolatrice rifiuta un'espressione** (`Carattere non consentito`, `Operazione non consentita`,
  `Esponente non ammesso`): è voluto. Sono ammessi solo numeri con il punto decimale, `+ - * / % **`
  e parentesi; niente funzioni, nomi, `//` o notazione scientifica, esponenti interi fino a 1000.
- **`Fuso orario: Europe/Berlin` anche se si è in Italia**: Windows chiama il fuso dell'Europa centrale
  `W. Europe Standard Time`, che la tabella standard traduce in `Europe/Berlin`. È la stessa ora di Roma.
