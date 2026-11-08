# Checkpoint — documentazione iniziale della lezione 5

Data: 2026-11-08

## Fatto

- **Presentazione letta** (`LLM_Lez_5`), con le decisioni prese insieme all'utente:
  - un solo server MCP per tutti gli strumenti, orologio compreso;
  - tre varianti di collegamento: MCP per tutti gli strumenti, `@tool` locale solo per la calcolatrice, FastAPI con wrapper HTTP solo per giorni e scadenze;
  - una sola versione di ogni strumento duplicato visibile al modello, scelta nel `.env`.
- **Correzione del convertitore** committata su `dev`: `02ce50d fix(server): segnala come troppo grandi le temperature fuori precisione`. Senza la correzione, `1e30 °C → °F` sollevava `InvalidOperation`. I nuovi test fallivano sul codice vecchio, e ora la suite dà 98 test passati e 7 saltati (prove reali).
- **Specifica** `docs/superpowers/specs/2026-11-08-strumenti-lezione-5-design.md`:
  - rivista da un revisore indipendente e approvata dall'utente;
  - committata su `dev` (`76787ac`).
- **Piani di implementazione**, uno per passo, in `docs/superpowers/plans/`:
  - `2026-11-08-passo-1-infrastruttura-mcp.md`: server MCP, convertitore, orologio spostato, ponte, avvio, log;
  - `2026-11-08-passo-2-calcolatrice.md`: varianti MCP e locale;
  - `2026-11-08-passo-3-scadenze.md`: varianti MCP e FastAPI;
  - `2026-11-08-passo-4-catalogo.md`;
  - `2026-11-08-passo-5-note.md`;
  - `2026-11-08-passo-6-meteo.md`;
  - `2026-11-08-passo-7-docker-documentazione.md`.

  Il vecchio piano `2026-11-03-convertitore-unita-mcp.md` è marcato come sostituito dal Task 2 in poi.
- **Versioni delle nuove dipendenze** verificate con `pip --dry-run` su Python 3.14.7, senza conflitti con quelle già fissate:

  | Pacchetto | Versione |
  |---|---|
  | `fastapi` | 0.162.2 |
  | `uvicorn` | 0.54.0 |
  | `httpx` | 0.28.1 |
  | `starlette` (indiretta) | 1.10.0 |
- **Date di Pasquetta** calcolate per il file delle festività: 2026-04-06, 2027-03-29, 2028-04-17.
- **Nuove regole di lavoro** registrate in `CLAUDE.md`:
  - un branch `dev-<passo>` per ogni passo;
  - merge in `main` solo con l'approvazione esplicita dell'utente;
  - checkpoint come questo;
  - il modello di LM Studio lo sceglie e lo cambia l'utente.

## Da fare

1. **L'utente approva i piani.** Il codice non si scrive prima di questa approvazione.
2. **Passo 1** sul branch `dev-infrastruttura-mcp`, poi approvazione e merge in `main`.
3. **Passi 2–7**, nell'ordine, ognuno sul suo branch e con il suo checkpoint.
4. **Prima delle prove reali**, l'utente aggiunge al `.env` le nuove variabili: `MCP_PORTA`, `VARIANTE_CALCOLATRICE`, `VARIANTE_SCADENZE` e `API_PORTA`. Il `.env` è suo.

## Stato attuale

- **Branch:** `dev`, 6 commit avanti a `main`, compreso quello di questo checkpoint (che è allineato a `origin/main`). Nessun push.
- **Ultimo commit di codice:** `02ce50d`. Questo checkpoint si committa con i piani.
- **Test:** 98 passati e 7 saltati (prove reali non eseguite), con `python -m pytest -q` del 2026-11-08.
- **Non verificato:**
  - nessuna prova reale con LM Studio o Docker è stata eseguita in questa sessione;
  - le versioni delle nuove dipendenze sono risolte ma non ancora installate nella `.venv`.
- **Rimasto in sospeso:** `.gitattributes` alla radice della repository risulta cancellato nella copia di lavoro. Non l'ho toccato perché è fuori da `assistente-laboratorio/` e l'utente non ha indicato cosa farne.
