# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti». Questo file sta alla radice della repository; il progetto è nella cartella `assistente-laboratorio/`. Specifica e piano sono in `assistente-laboratorio/docs/superpowers/`.

## Struttura e comandi

Dentro `assistente-laboratorio/`:

- `logica/`: logica pura degli strumenti (`orologio.py`, `conversioni.py`, `calcolatrice.py`, `scadenze.py`, `catalogo.py`, `note.py`, `meteo.py`, `errori.py`), senza dipendenze da MCP, FastAPI o LangChain.
- `server_mcp/`: registrazione MCP degli strumenti (`server.py`) e avvio (`python -m server_mcp --porta 8765`).
- `servizio_api/`: servizio FastAPI delle scadenze (`app.py`) e avvio (`python -m servizio_api --porta 8766`).
- `servizio_agente/`: l'agente come servizio HTTP (`app.py` con `/salute` e `/chat`, senza stato) e avvio (`python -m servizio_agente`, porta da `AGENTE_PORTA`).
- `risorse/`: dati versionati letti dagli strumenti (`festivita_italia.json`, `catalogo_corsi.json`) e ambito dell'assistente con il testo del rifiuto (`ambito.json`).
- `assistente/`: `configurazione.py` e `fuso.py` (variabili d'ambiente, rilevamento del fuso), `modello.py` (LM Studio), `grafo.py` (stato, nodi, instradamento), `ambito.py` (lettura di `risorse/ambito.json`), `router.py` (router dell'ambito con output strutturato), `agente.py` (`crea_agente`, costruzione comune a CLI e servizio), `client_mcp.py` (discovery e ponte sincrono), `varianti.py` (scelta delle varianti e selezione degli strumenti), `calcolatrice_locale.py` (variante locale di `calcola` con `@tool`), `wrapper_scadenze.py` (variante FastAPI di `calcola_scadenza`: wrapper HTTP con `@tool`), `avvio_server.py` (avvio, attesa e arresto dei processi), `avvio.py` (preparazione degli strumenti), `registro.py` (log), `errori.py`, `terminale.py` (ciclo di chat), `__main__.py` (avvio).
- `logs/`: `assistente.log`, `server_mcp.log` e `servizio_api.log`, fuori da Git.
- `archivio/`: `note.sqlite3`, l'archivio delle note persistenti, fuori da Git e dall'immagine Docker.
- `tests/`: test automatici; `finti.py` contiene modello e strumenti finti; `reale.py` l'ambiente comune delle prove reali; `test_reale_*.py` sono le prove reali.
- `docs/studio/`: documenti di studio per argomento, con indice per lezione in `00-indice.md`; ogni capitolo ha una «Scheda in 5 minuti» in cima e una «Scaletta per le slide» in fondo. Quando cambia il codice, si aggiornano anche i capitoli interessati.
- `docs/superpowers/`: specifiche, piani e checkpoint in `specs/`, `plans/` e `checkpoint/`, con un indice per lezione in `README.md`.
- Dipendenze in `requirements.txt` (applicazione) e `requirements-dev.txt` (più pytest), versioni fissate.

Comandi (PowerShell, da `assistente-laboratorio/`, con `.\.venv\Scripts\Activate.ps1`):

- Test automatici: `python -m pytest` (le prove reali risultano `skipped`).
- Prova reale con LM Studio: `python -m pytest --lmstudio -m lmstudio -v -s`.
- Prova reale con Docker: `python -m pytest --docker -m docker -v -s`.
- Avvio diretto: `python -m assistente`. Avvio con Docker: `.\avvia.ps1` (CLI) e `.\avvia-agente.ps1` (servizio HTTP dell'agente, porta solo su 127.0.0.1).
- Solo il server MCP: `python -m server_mcp --porta 8765` (con `--note <file>` per non toccare l'archivio reale). Solo il servizio FastAPI: `python -m servizio_api --porta 8766`. L'agente come servizio HTTP: `python -m servizio_agente`.
- Variabili nel `.env`: `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`, `MCP_PORTA`, `VARIANTE_CALCOLATRICE` (`mcp`/`locale`), `VARIANTE_SCADENZE` (`mcp`/`fastapi`), `API_PORTA` (solo con `fastapi`), `AGENTE_PORTA` (solo per `servizio_agente`), `AGENTE_HOST` (facoltativa, predefinita `127.0.0.1`; in Docker la imposta Compose); per Docker anche `LMSTUDIO_BASE_URL_DOCKER`.

## Obiettivo

Un'applicazione da terminale in Python che conversa con un modello locale e:

- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);  
- usa un modello servito da LM Studio, che resta sul computer host;  
- conserva la cronologia della conversazione per la durata della sessione (nessuna persistenza della cronologia; le note sono l'unica persistenza, voluta);  
- offre gli strumenti della lezione 5 (orologio, convertitore, calcolatrice, scadenze, catalogo, note, meteo) tramite un server MCP che avvia, scopre con la discovery e spegne da sé; il modello li richiede con il tool calling e il programma li esegue davvero;  
- permette di confrontare tre modi di collegare uno strumento: MCP per tutti, `@tool` locale per la calcolatrice, FastAPI con wrapper HTTP per le scadenze, scelti nel `.env` (una sola versione per nome visibile al modello);  
- si avvia anche con Docker Compose;  
- dalla lezione 6 risponde anche via HTTP (servizio dell'agente) e, con gli step 7–9, da una chat nel browser.

## Confini

- Implementare solo i requisiti concordati. Gli strumenti MCP della lezione 5 sono descritti nella specifica `2026-11-08-strumenti-lezione-5-design.md`; workflow, RAG e altri strumenti arriveranno nelle lezioni successive: non anticiparli.  
- L'unica interfaccia grafica ammessa è la chat nel browser della lezione 6 (step 8, front-end), che parla con il back-end; linguaggio e librerie si scelgono nella sua specifica e servono la mia approvazione. La CLI da terminale resta. Niente altre interfacce grafiche, servizi cloud o framework non concordati.  
- Lavorare solo dentro `assistente-laboratorio/`. La repository contiene altre lezioni: non leggerle per copiarne il codice e non modificarle.  
- Un branch per passo del piano, con nome `dev-<passo>` (per esempio `dev-calcolatrice`), che parte da `dev`; niente worktree se non richiesti. Il merge in `main` avviene solo con la mia approvazione esplicita, passo per passo.

## Scelte tecniche

- Python, codice sincrono e moduli piccoli, con una separazione semplice tra grafo, collegamento al modello, strumenti e interfaccia da terminale. L'unico punto asincrono è il ponte MCP (`assistente/client_mcp.py`).  
- Gli strumenti sono serviti dal server MCP, avviato e spento dall'assistente; la logica di ogni strumento è scritta una volta sola in `logica/`.  
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.  
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente. L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.  
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.  
- Docker Compose per l'applicazione; LM Studio non va containerizzato.  
- Dipendenze motivate, concordate e con versioni fissate.  
- Comandi documentati anche per PowerShell (Windows).

## Metodo: Superpowers

- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.  
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.  
- Salvare specifica e piano in `assistente-laboratorio/docs/superpowers/`.  
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.  
- Checkpoint: alla fine di ogni passo, e ogni volta che il lavoro si interrompe, scrivere un file in `assistente-laboratorio/docs/superpowers/checkpoint/` (`AAAA-MM-GG-<passo>.md`) con tre sezioni: **Fatto**, **Da fare**, **Stato attuale** (branch, ultimo commit, esito dei test, cosa non è verificato). Il checkpoint si committa insieme al lavoro che descrive.
- Il modello in LM Studio lo sceglio e lo cambio io: se le prove reali falliscono, riportare l'esito con le evidenze.

## Test e verifiche

- Test automatici ripetibili che non richiedono un modello attivo (grafo, cronologia, instradamento, strumento con istante controllato).  
- Prove reali con LM Studio e con Docker tenute separate e attivate esplicitamente.  
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.  
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Git

- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`, `docs: ...`.  
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.  
- Mai versionare credenziali, `.env`, ambienti virtuali, cache o pesi dei modelli.  
- Push soltanto su mia richiesta.

## Documentazione

- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo comandi verificati.  
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test, regole di lavoro), non per annotare l'avanzamento.