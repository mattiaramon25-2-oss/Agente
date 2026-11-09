# Documenti di lavoro, lezione per lezione

Questa cartella contiene i documenti del metodo di lavoro: prima la **specifica** (che cosa costruire e perché), poi il **piano** (in quali passi e con quali test), infine un **checkpoint** a ogni passo (che cosa è stato fatto davvero e con quale esito).

I file restano nelle tre sottocartelle `specs/`, `plans/` e `checkpoint/`, con la data nel nome: lo prevedono il metodo e il `CLAUDE.md`, e molti documenti si citano a vicenda con questi percorsi. Questo indice li raggruppa per lezione.

Per studiare il progetto parti da [`docs/studio/00-indice.md`](../studio/00-indice.md). Questi documenti servono quando vuoi sapere che cosa era stato deciso, in che ordine si è costruito o com'è andata una prova reale.

---

## Lezione 4 · L'assistente di base (2 novembre)

Chat da terminale con un modello di LM Studio, grafo LangGraph con i nodi `modello`, `strumenti` e `limite`, orologio come unico strumento, avvio diretto e con Docker.

| Tipo | Documento | In una riga |
|---|---|---|
| Specifica | [2026-11-02-assistente-laboratorio-design.md](specs/2026-11-02-assistente-laboratorio-design.md) | obiettivi, comportamento della sessione, fuso dell'utente, grafo, Docker |
| Piano | [2026-11-02-assistente-laboratorio.md](plans/2026-11-02-assistente-laboratorio.md) | gli 8 task con cui è stato costruito l'assistente di base |

Nessun checkpoint: la regola dei checkpoint è arrivata con la lezione 5.

---

## Lezione 5 · Gli strumenti via MCP (3–9 novembre)

Un server MCP con dieci strumenti, tre modi di collegarli (MCP, `@tool` locale, FastAPI con wrapper), note in SQLite, meteo, log su tre file.

### Il convertitore, primo strumento MCP (3 novembre)

| Tipo | Documento | In una riga |
|---|---|---|
| Specifica | [2026-11-03-convertitore-unita-mcp-design.md](specs/2026-11-03-convertitore-unita-mcp-design.md) | il primo strumento via MCP e tutta l'infrastruttura: server FastMCP, ponte sincrono, avvio, log |
| Piano | [2026-11-03-convertitore-unita-mcp.md](plans/2026-11-03-convertitore-unita-mcp.md) | i task del convertitore; dal Task 2 in poi è stato sostituito dai piani dei sette passi |

### I dieci strumenti in sette passi (8 novembre)

La specifica vale per tutti i passi. Ogni passo ha il suo piano, il suo branch e il suo checkpoint.

| Tipo | Documento | In una riga |
|---|---|---|
| Specifica | [2026-11-08-strumenti-lezione-5-design.md](specs/2026-11-08-strumenti-lezione-5-design.md) | gli strumenti della lezione 5 nelle tre varianti; dove contraddice la specifica del convertitore, vale questa |
| Checkpoint | [2026-11-08-documentazione-iniziale.md](checkpoint/2026-11-08-documentazione-iniziale.md) | specifica e piani pronti, correzione del convertitore, prima del passo 1 |

| Passo | Piano | Checkpoint | Test alla fine del passo |
|---|---|---|---|
| 1 · Infrastruttura MCP, convertitore e orologio nel server | [piano](plans/2026-11-08-passo-1-infrastruttura-mcp.md) | [checkpoint](checkpoint/2026-11-08-infrastruttura-mcp.md) | 151 passati, 14 saltati |
| 2 · Calcolatrice sicura (MCP e locale) | [piano](plans/2026-11-08-passo-2-calcolatrice.md) | [checkpoint](checkpoint/2026-11-08-calcolatrice.md) | 213 passati, 18 saltati |
| 3 · Giorni e scadenze (MCP e FastAPI) | [piano](plans/2026-11-08-passo-3-scadenze.md) | [checkpoint](checkpoint/2026-11-08-scadenze.md) | 291 passati, 22 saltati |
| 4 · Catalogo locale | [piano](plans/2026-11-08-passo-4-catalogo.md) | [checkpoint](checkpoint/2026-11-08-catalogo.md) | 332 passati, 26 saltati |
| 5 · Note persistenti | [piano](plans/2026-11-08-passo-5-note.md) | [checkpoint](checkpoint/2026-11-08-note.md) | 377 passati, 30 saltati |
| 6 · Meteo da Open-Meteo | [piano](plans/2026-11-08-passo-6-meteo.md) | [checkpoint](checkpoint/2026-11-08-meteo.md) | 412 passati, 33 saltati |
| 7 · Docker completo e documentazione finale | [piano](plans/2026-11-08-passo-7-docker-documentazione.md) | [checkpoint](checkpoint/2026-11-08-docker-docs.md) | 419 passati, 36 saltati |

I «saltati» sono le prove reali con LM Studio e Docker, che partono solo se le chiedi.

### La revisione finale (8–9 novembre)

Nove correzioni sul branch `dev-revisione`, unite in `main` il 9 novembre (`846b02a`). Non hanno un piano né un checkpoint propri: sono raccontate in [`docs/studio/11-storia-del-progetto.md`](../studio/11-storia-del-progetto.md), sezione 7. Dopo l'unione: 467 test passati e 36 saltati.

---

## Lezione 6 · Evolvere l'agente (in corso)

Router, revisore e riassunto della cronologia, poi resource e prompt MCP, infine l'agente come servizio con interfaccia web. Il riepilogo dei nove step è in [`docs/studio/00-indice.md`](../studio/00-indice.md).

| Tipo | Documento | In una riga |
|---|---|---|
| Checkpoint | [2026-11-09-documentazione-studio.md](checkpoint/2026-11-09-documentazione-studio.md) | documenti di studio aggiornati e riordinati prima di cominciare la lezione |
| Specifica | [2026-11-09-router-ambito-design.md](specs/2026-11-09-router-ambito-design.md) | step 1: router «conversazione» o «fuori ambito», ambito in `risorse/ambito.json` |
| Piano | [2026-11-09-router-ambito.md](plans/2026-11-09-router-ambito.md) | i cinque task dello step 1 |
| Checkpoint | [2026-11-09-router.md](checkpoint/2026-11-09-router.md) | step 1 completato, prove reali passate |
| Specifica | [2026-11-09-streaming-rifiuto-design.md](specs/2026-11-09-streaming-rifiuto-design.md) | richiesta extra: risposta in streaming e rifiuto che rimanda a un altro provider |
| Piano | [2026-11-09-streaming-rifiuto.md](plans/2026-11-09-streaming-rifiuto.md) | i cinque task dello streaming |
| Checkpoint | [2026-11-09-streaming.md](checkpoint/2026-11-09-streaming.md) | streaming e nuovo rifiuto fatti, due correzioni emerse dalle prove |

Specifica e piani degli step arriveranno qui, con lo stesso schema: `specs/AAAA-MM-GG-<argomento>-design.md`, `plans/AAAA-MM-GG-<argomento>.md`, `checkpoint/AAAA-MM-GG-<passo>.md`.
