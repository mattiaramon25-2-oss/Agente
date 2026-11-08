# Checkpoint conclusivo — passo 7 e progetto della lezione 5

Data: 2026-11-08 · Piano: `docs/superpowers/plans/2026-11-08-passo-7-docker-documentazione.md` · Specifica: `docs/superpowers/specs/2026-11-08-strumenti-lezione-5-design.md`

## Fatto

### Passo 7

| Commit | Contenuto |
|---|---|
| `fe2048d` | prova Docker con le varianti `fastapi` e `locale`, volume delle note verificato in modo deterministico, meteo senza rete nel container; README con tabella strumenti/varianti/log e diagnosi per livelli; `CLAUDE.md` con obiettivo e comandi finali; nel messaggio di sistema la regola «se non hai chiamato lo strumento, non l'hai fatto» |
| `d92d7bb` | correzioni dopo la revisione: spostamento sicuro di `logs/` e `archivio/` durante la prova Docker (con 6 test automatici), comando del README per le varianti eseguito nella sua forma esatta, README allineato |

Il `Dockerfile`, `compose.yaml` e `.dockerignore` erano già completi dai passi 1, 3 e 5.

### I sette passi

| Passo | Branch | Stato | Checkpoint |
|---|---|---|---|
| 1 — infrastruttura MCP, convertitore, orologio nel server | `dev-infrastruttura-mcp` | unito in `main` (`a6eb059`) | `2026-11-08-infrastruttura-mcp.md` |
| 2 — calcolatrice (MCP e locale) | `dev-calcolatrice` | unito (`fc2ff31`) | `2026-11-08-calcolatrice.md` |
| 3 — scadenze (MCP e FastAPI) | `dev-scadenze` | unito (`ca82a5d`) | `2026-11-08-scadenze.md` |
| 4 — catalogo | `dev-catalogo` | unito (`0f2cc17`) | `2026-11-08-catalogo.md` |
| 5 — note persistenti | `dev-note` | unito (`1214615`) | `2026-11-08-note.md` |
| 6 — meteo | `dev-meteo` | unito (`5806352`) | `2026-11-08-meteo.md` |
| 7 — Docker e documentazione | `dev-docker-docs` | **in attesa della tua approvazione** | questo file |

### Ultime esecuzioni, 2026-11-08

- **Test automatici:** `python -m pytest -q` dà 419 passati e 36 saltati (le prove reali). Nessun test usa la rete, e nessuno scrive nell'archivio reale delle note.
- **LM Studio**, modello `google/gemma-4-e2b`, dieci strumenti:
  - **ultimo giro completo:** 28 su 30;
  - **i due falliti:** il modello ha risposto «Ho salvato la nota» senza chiamare `add_note`, e dopo il riavvio l'archivio risultava vuoto;
  - **misura ripetuta della sola prova di aggiunta:** riuscita 2 volte su 3.

  Tutti gli altri strumenti e varianti sono passati: orologio, convertitore, calcolatrice MCP e locale, scadenze MCP e FastAPI, catalogo, eliminazione di note, meteo. Nei passi precedenti i giri completi avevano dato 27/27 e 30/30.
- **Docker:** 6 su 6 nel giro completo.
  - **Varianti nel container:** con `calcola` in versione locale e `calcola_scadenza` in versione FastAPI la scadenza dà 29 dicembre 2026, e il meteo funziona con la rete del container.
  - **Note:** una nota scritta in un container si ritrova sull'host e da un container nuovo.
  - **Senza rete:** in un container senza rete il meteo risponde in 0,0 secondi «Servizio meteo non disponibile… name resolution».
- **Avvio diretto** (`python -m assistente`, ingresso da una pipe): eseguito; l'uscita, con dieci strumenti, è nel README.

**Revisione finale del passo 7:** nessun problema Critical e nessun percorso che cancelli dati dell'utente. Corretti con test che prima fallivano:

- **Spostamento di `logs/` e `archivio/` più robusto:** ora annulla le rinomine se qualcosa fallisce a metà, elimina solo le cartelle create dalla prova e ripristina comunque. Uno dei nuovi test ha colto un caso pericoloso nella prima versione della correzione, risolto prima del commit.
- **Comando del README per Docker:** verificato nella sua forma esatta.
- **Test senza rete:** la descrizione ora dichiara solo quello che misura davvero.
- **Documentazione:** allineata.

**Rimandati** (Minor):

- la regola «in questo turno» del messaggio di sistema può essere letta in modo troppo stretto;
- alcuni controlli della prova Docker sono deboli (riga di arresto, esito del meteo);
- il nome dell'immagine Docker è fisso nel test;
- `FUSO_ORARIO` non compare tra le variabili in `CLAUDE.md`;
- nel README ci sono due tabelle consecutive.

Gli altri minori rimandati sono nei checkpoint dei passi 1–6.

## Da fare

1. **Tu approvi il merge** di `dev-docker-docs` in `main`.
2. **Tu aggiorni il `.env`** con `MCP_PORTA=8765`, `VARIANTE_CALCOLATRICE=mcp`, `VARIANTE_SCADENZE=mcp` e, per FastAPI, `API_PORTA=8766`. Senza queste righe `python -m assistente` e Docker si fermano subito con un messaggio che le elenca. Tutte le prove sono state fatte passando le variabili solo al processo di test.
3. **Il modello lo decidi tu:** con dieci strumenti `google/gemma-4-e2b` ogni tanto dichiara un'azione senza chiamare lo strumento, in particolare il salvataggio delle note. Il codice lo rende visibile (nel terminale manca la riga `[add_note · mcp: …]`), ma non può impedirlo. Un modello più grande si prova cambiando solo `LMSTUDIO_MODEL`.
4. **Branch `dev`:** è fermo a prima del passo 1, mentre `CLAUDE.md` dice che i branch partono da `dev`. I passi 2–7 sono partiti da `main`. Decidi tu se riallineare `dev` a `main` o cambiare la regola.
5. **Non verificato:**
   - l'avvio interattivo da tastiera di `.\avvia.ps1`;
   - il meteo con rete presente ma senza Internet: la scadenza di 8 secondi è coperta solo dai test automatici.
6. **`.gitattributes`** alla radice della repository risulta cancellato nella copia di lavoro. Non l'ho toccato perché è fuori da `assistente-laboratorio/`.
7. **Estensioni escluse dalla specifica** (sezione 3), se vorrai riprenderle: trasporto stdio, due server MCP, prompt e resources MCP, conferma umana prima di eliminare.

## Stato attuale

- **Branch:** `dev-docker-docs`, creato da `main` (`5806352`). Nessun push.
- **`main`** contiene i passi 1–6.
- **Ultimo commit:** quello di questo checkpoint, che segue `d92d7bb`.
- **Cartelle `logs/` e `archivio/`:** al loro posto, senza riserve rimaste.
