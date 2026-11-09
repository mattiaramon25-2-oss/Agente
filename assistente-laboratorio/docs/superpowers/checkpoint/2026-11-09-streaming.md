# Checkpoint — risposta in streaming e nuovo testo del rifiuto

## Fatto

- Specifica e piano: `specs/2026-11-09-streaming-rifiuto-design.md`, `plans/2026-11-09-streaming-rifiuto.md` (`6994483`). Decisioni dell'utente: il nuovo messaggio sostituisce il rifiuto; in streaming va solo la risposta finale.
- Rifiuto in `risorse/ambito.json`: «Questo agente è costruito per compiti specifici: … Se hai bisogno di aiuto per un compito diverso, prova a usare un altro provider.» (`37a6419`).
- `esegui_turno_in_streaming` nel grafo (`8becee5`); `_StampaInStreaming` e `scrivi_pezzo` nel terminale e nell'avvio (`bed0dbe`); prova reale `tests/test_reale_streaming.py` (`77a1b0d`).
- **Correzione su codice già in `main`:** dopo il router, `tests/test_avvio_unico.py` chiamava davvero LM Studio con il router reale (passava solo perché LM Studio era acceso). Ora usa un router finto e un indirizzo dove non ascolta nessuno (`3a6a9ac`).
- **Correzione emersa dalla prova di avvio:** con lo streaming il router faceva stampare a pydantic un avviso nel terminale a ogni turno. Ora il router ha `disable_streaming=True` e il tag `nostream` (`3add62f`).
- Documenti: README (avvio, ambito, prove reali), `docs/studio/04` (sezione 22, slide 12), indice `docs/superpowers/README.md`.

## Da fare

- Approvazione dell'utente per il merge di `dev-streaming` in `main` (nessun merge eseguito).
- Osservazione, non corretta: alla domanda «che cosa sai fare?» il modello si descrive in modo generico («una vasta gamma di compiti») invece di elencare gli strumenti; dipende dal messaggio di sistema dell'agente, non dallo streaming.

## Stato attuale

- Branch `dev-streaming`, da `dev` (= `main` dopo il router).
- `python -m pytest`: 509 passati, 40 saltati.
- `python -m pytest --lmstudio -m lmstudio tests/test_reale_streaming.py tests/test_reale_router.py tests/test_reale_lmstudio.py`: 10 passati (`google/gemma-4-e2b`); la risposta di prova è arrivata in 48 pezzi.
- Avvio diretto con pipe (`ciao`, `esci`): risposta in streaming, nessun avviso nel terminale.
- Non verificato: le altre prove reali (calcolatrice, scadenze, catalogo, note, meteo, convertitore) dopo lo streaming, che però usano `esegui_turno` e non cambiano; le prove Docker; lo streaming in una console interattiva (provato solo con la pipe).
