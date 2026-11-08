# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti». Questo file sta alla radice della repository; il progetto è nella cartella `assistente-laboratorio/`. Specifica e piano sono in `assistente-laboratorio/docs/superpowers/`.

## Struttura e comandi

Dentro `assistente-laboratorio/`:

- `logica/`: logica pura degli strumenti (`orologio.py`, `conversioni.py`, `calcolatrice.py`, `scadenze.py`, `catalogo.py`, `errori.py`), senza dipendenze da MCP, FastAPI o LangChain.
- `server_mcp/`: registrazione MCP degli strumenti (`server.py`) e avvio (`python -m server_mcp --porta 8765`).
- `servizio_api/`: servizio FastAPI delle scadenze (`app.py`) e avvio (`python -m servizio_api --porta 8766`).
- `risorse/`: dati versionati letti dagli strumenti (`festivita_italia.json`, `catalogo_corsi.json`).
- `assistente/`: `configurazione.py` e `fuso.py` (variabili d'ambiente, rilevamento del fuso), `modello.py` (LM Studio), `grafo.py` (stato, nodi, instradamento), `client_mcp.py` (discovery e ponte sincrono), `varianti.py` (scelta delle varianti e selezione degli strumenti), `calcolatrice_locale.py` (variante locale di `calcola` con `@tool`), `wrapper_scadenze.py` (variante FastAPI di `calcola_scadenza`: wrapper HTTP con `@tool`), `avvio_server.py` (avvio, attesa e arresto dei processi), `avvio.py` (preparazione degli strumenti), `registro.py` (log), `errori.py`, `terminale.py` (ciclo di chat), `__main__.py` (avvio).
- `logs/`: `assistente.log`, `server_mcp.log` e `servizio_api.log`, fuori da Git.
- `tests/`: test automatici; `finti.py` contiene modello e strumenti finti; `reale.py` l'ambiente comune delle prove reali; `test_reale_*.py` sono le prove reali.
- Dipendenze in `requirements.txt` (applicazione) e `requirements-dev.txt` (più pytest), versioni fissate.

Comandi (PowerShell, da `assistente-laboratorio/`, con `.\.venv\Scripts\Activate.ps1`):

- Test automatici: `python -m pytest` (le prove reali risultano `skipped`).
- Prova reale con LM Studio: `python -m pytest --lmstudio -m lmstudio -v -s`.
- Prova reale con Docker: `python -m pytest --docker -m docker -v -s`.
- Avvio diretto: `python -m assistente`. Avvio con Docker: `.\avvia.ps1`.

## Obiettivo

Un'applicazione da terminale in Python che conversa con un modello locale e:

- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);  
- usa un modello servito da LM Studio, che resta sul computer host;  
- conserva la cronologia della conversazione per la durata della sessione (nessuna persistenza);  
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling ed eseguito davvero dal programma;  
- si avvia anche con Docker Compose.

## Confini

- Implementare solo i requisiti concordati. Gli strumenti MCP della lezione 5 sono descritti nella specifica `2026-11-08-strumenti-lezione-5-design.md`; workflow, RAG e altri strumenti arriveranno nelle lezioni successive: non anticiparli.  
- Niente interfacce grafiche, servizi cloud o framework non concordati.  
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