# Checkpoint — documenti di studio aggiornati e riordinati, prima della lezione 6

## Fatto

- **Revisione unita in `main`.** I test sono stati rilanciati su `dev-revisione` (467 passati, 36 saltati). Poi, con l'approvazione dell'utente, il branch è stato unito in `main` con il merge `846b02a`. `dev` è stato portato allo stesso commit.
- **Merge rifatto senza `Co-Authored-By`.** Il primo merge (`f7ce874`) conteneva quella riga, che i piani vietano dal convertitore in poi. È stato ricreato con gli stessi file e gli stessi genitori, cambiando solo il messaggio. Non era mai stato inviato a GitHub.
- **Branch.** In locale sono stati cancellati i branch dei passi 1–7 e `dev-revisione`, tutti già uniti. È stato aperto `dev-lezione_6`, che parte da `dev`.
- **Capitoli di `docs/studio/` (da 01 a 12).** Ognuno ha ora una «Scheda in 5 minuti» in cima e una «Scaletta per le slide» in fondo, con 9 o 10 slide. I valori delle tabelle «Da sapere a memoria» e i riferimenti dei «Da mostrare» sono stati controllati sul codice. Le sezioni esistenti non sono state rinumerate.
- **`docs/studio/00-indice.md` riscritto.** Contiene:
  - come sono fatti i capitoli;
  - il progetto lezione per lezione: 4, 5 e 6, con i nove step della lezione 6 presi dalle slide;
  - i percorsi di studio, con un nuovo percorso «solo schede»;
  - una guida per preparare le presentazioni.
- **Passaggi superati corretti.** Riguardavano lo stato prima del merge: `dev-revisione` descritto come non unito, i conteggi di commit vecchi, la frase su `origin/main`. Si trovavano nei capitoli 05, 09, 11 e 12. Nel capitolo 11 c'è una nuova sezione, la 7.11 «L'unione in `main`». Nel capitolo 08 lo stato del `.env` locale ora dice che contiene tutte le otto variabili.
- **Piccole correzioni ai capitoli.**
  - Capitolo 05: `_esito` sta a `grafo.py:66-74`, non a `:65-74`.
  - Capitolo 09, titolo della sezione 5.2: le righe di `chiamata` e di `chiamata_orologio` erano invertite.
  - Capitoli 04, 08 e 11: la riga di navigazione è tornata in fondo, dopo la scaletta.
- **`docs/superpowers/README.md`.** È un nuovo indice per lezione di specifiche, piani e checkpoint. I file restano in `specs/`, `plans/` e `checkpoint/`, perché il metodo e il `CLAUDE.md` usano quei percorsi.
- **`CLAUDE.md`.** Nella struttura ora compaiono `docs/studio/` e `docs/superpowers/`, con la regola di aggiornare i capitoli quando cambia il codice.

## Da fare

- **Lezione 6.** Brainstorming, poi specifica e piano degli step da terminale: router, revisore e riassunto della cronologia. Resta aperta una domanda. Le slide dicono che il router decide solo se la domanda è nell'ambito, mentre gli strumenti restano scelti dall'agente. Nel primo messaggio, invece, l'utente parlava di un router che decide se usare i tool.
- **Branch remoti.** Su GitHub restano `dev-calcolatrice`, `dev-catalogo`, `dev-docker-docs`, `dev-infrastruttura-mcp`, `dev-meteo`, `dev-note`, `dev-scadenze` e `dev-revisione`. La cancellazione remota non è stata permessa all'assistente: può farla l'utente.
- **Push.** `main` e `dev` sono avanti rispetto a GitHub. Il push si fa solo su richiesta.
- **Modifiche locali non decise.** `.gitattributes` e `.env.example` risultano cancellati nella copia di lavoro, e `.env.ll` non è tracciato. Nessuno dei tre entra in questo commit.
- **Nota sul codice, non corretta.** In `tests/test_reale_docker.py` il commento alle righe 27–28 dice che le variabili già presenti nell'ambiente hanno la precedenza. `compose_con_varianti`, alla riga 112, fa il contrario: `{**os.environ, **ENV_COME_DA_DOTENV}`. In pratica non cambia nulla, perché in quel test le varianti arrivano dalle opzioni `-e`.

## Stato attuale

- **Branch:** `dev-lezione_6`. Il commit che contiene questo checkpoint parte da `846b02a`.
- **Test:** `python -m pytest -q` dà 467 passati e 36 saltati (le prove reali), eseguito il 2026-11-09 su questo branch. Il commit cambia solo documenti e `CLAUDE.md`.
- **Non verificato:**
  - le prove reali con LM Studio e con Docker, non rieseguite dopo la revisione;
  - la resa grafica dei diagrammi mermaid nuovi, controllata solo nella sintassi (blocchi chiusi), non visualizzata;
  - l'attribuzione della base del 2 novembre alla lezione 4, che è dedotta dalla slide 2 della lezione 6 («si parte dall'agente delle lezioni 4 e 5»).
