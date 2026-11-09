# Streaming della risposta e nuovo testo del rifiuto

Data: 2026-11-09 · Branch: `dev-streaming` (da `dev`, che contiene il router)

Richiesta dell'utente, fuori dai nove step delle slide: la risposta del modello compare nel terminale man mano che arriva; il rifiuto del router invita a usare un altro provider.

## Decisioni dell'utente

- Il nuovo messaggio **sostituisce** il rifiuto attuale: stesse due categorie del router, cambia solo `rifiuto` in `risorse/ambito.json`.
- In streaming va **solo la risposta finale dell'agente** (nodo `modello`). Router, righe degli strumenti e rifiuto restano come oggi.

## Testo del rifiuto

«Questo agente è costruito per compiti specifici: data e ora, conversioni, calcoli, scadenze, corsi dell'ITS, note, meteo e domande sui temi del corso. Se hai bisogno di aiuto per un compito diverso, prova a usare un altro provider.»

## Streaming

- `grafo.stream(..., stream_mode=["messages", "values"])`: i pezzi di testo con `langgraph_node == "modello"` vanno a una funzione `su_testo`; i pezzi del router (JSON) e i messaggi degli altri nodi sono ignorati. Lo stato finale è quello dell'ultimo evento `values`.
- Nuova funzione `esegui_turno_in_streaming(grafo, cronologia, fuso, testo, su_testo, su_messaggi)` in `grafo.py`; `esegui_turno` resta com'è. `su_messaggi` riceve la cronologia parziale a ogni passo, così il terminale stampa le righe `[strumento · variante: …]` prima del testo, nello stesso ordine di oggi.
- Terminale: nuovo parametro `scrivi_pezzo` di `esegui_sessione`. Se c'è, la risposta si stampa a pezzi dopo «Assistente: »; se nessun pezzo arriva (rifiuto, limite, risposta vuota) si stampa la riga intera come oggi. Senza `scrivi_pezzo` il comportamento è quello attuale. `__main__` passa una funzione che scrive su `stdout` e fa `flush`.
- Errore a metà risposta: si va a capo, si stampa `Errore: …` e la cronologia resta quella di prima, come oggi.
- Il modello non cambia: LangChain usa lo streaming dell'API di LM Studio quando il grafo è eseguito con `stream`.

## Test

- Automatici con il modello finto: i pezzi arrivano solo dal nodo `modello`; righe degli strumenti prima del testo; rifiuto e limite stampati interi; errore a metà; cronologia uguale a quella di `esegui_turno`.
- Prova reale (`--lmstudio`): una risposta arriva in più di un pezzo e il testo ricomposto è uguale all'ultimo messaggio della cronologia; il rifiuto ha il nuovo testo.
