# Checkpoint — pausa della lezione 6 (dopo gli step 1, 6, 7 e 8)

## Fatto

- Uniti in `main`, nell'ordine (9–12 novembre 2026):
  - `bd8b891`: step 1, il router dell'ambito;
  - `711f421`: risposta in streaming e nuovo testo del rifiuto;
  - `fa83a50`: step 6, l'agente come servizio HTTP;
  - `13a673f`: il servizio dell'agente in Docker;
  - `3631867`: la regola sulla chat nel browser in `CLAUDE.md`;
  - `a869164`: step 7, il back-end delle chat con PostgreSQL;
  - `c4f2391`: correzioni ai documenti del back-end;
  - `f00512f`: step 8, la chat nel browser installabile come app (l'utente l'ha installata in Edge il 12 novembre e funziona).
- Documenti di studio aggiornati alla lezione 6: `docs/studio/00-indice.md` (stato, tabella degli step senza branch in attesa, righe superate di «Cosa sapere a memoria»), `01-panoramica-e-concetti.md` (nuova sezione 13), `02-architettura.md` (sezione 1.5 ter con i processi di oggi e il diagramma browser, nginx, back-end, agente, database; cartelle nuove), `11-storia-del-progetto.md` (nuova sezione 8, la fase 5; registro delle decisioni 9.4; prove reali e punti aperti aggiornati), `12-glossario-e-domande.md` (14 voci nuove, sei domande nuove D63–D68, riferimenti `assistente/grafo.py` riallineati al codice attuale); indice `docs/superpowers/README.md`.

## Da fare

- Step 9: Docker Compose con quattro container (front-end, back-end, agente, database) avviati con un solo comando. Oggi l'agente e il back-end si avviano a mano sull'host; il database e il `frontend` con Compose.
- Step 2–5: revisore, riassunto della cronologia, resource, prompt.
- La cartella `.superpowers/`, alla radice della repository, non è tracciata: da aggiungere al `.gitignore` se l'utente lo vuole.

## Stato attuale

- Branch di lavoro `dev-docs-lezione-6`, da `dev`. `dev` è uguale a `main` a `f00512f`. Questo checkpoint si committa insieme ai documenti aggiornati; nessun merge eseguito, nessun push.
- Esiti al 12 novembre 2026, dopo l'unione dello step 8:
  - `npm test` (in `frontend/`): 108 passati;
  - `python -m pytest`: 625 passati, 74 saltati;
  - prove nel browser e di Compose (`--docker`): 9 passate;
  - `--lmstudio --docker`: 5 passate, prima delle correzioni finali dello step 8;
  - `--lmstudio`: 35 passate e 2 instabili per colpa del modello, che passano alla seconda esecuzione.
- In questo passo non è stato eseguito codice né test: sono stati modificati solo documenti. I riferimenti `file:riga` scritti o corretti sono stati controllati con `grep -n` sul codice attuale.
- Non verificato: `Ctrl+C` digitato in una console vera su `servizio_backend`; le suite complete con LM Studio dopo le correzioni finali dello step 8; il comportamento con il modello precedente, senza ragionamento (il modello `google/gemma-4-e2b` ora in LM Studio ragiona prima di rispondere e un turno richiede circa 1–2 minuti).
- Servizi lasciati accesi dall'ultima sessione: il database (`docker compose up -d database`), l'agente, il back-end e il container `frontend` (porta 8780). Le chat di prova dell'utente sono nel suo database.
