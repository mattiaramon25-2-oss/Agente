# Checkpoint — passo 2: calcolatrice sicura nelle varianti MCP e locale

Data: 2026-11-08 · Piano: `docs/superpowers/plans/2026-11-08-passo-2-calcolatrice.md`

## Fatto

| Task | Commit | Contenuto |
|---|---|---|
| 1 | `7c1c753`, `ffadbe5` | `logica/calcolatrice.py`: analisi `ast` su una lista chiusa di nodi, aritmetica `Decimal`, nessun `eval`; correzione per `0 ** -1`, che ora dà «Divisione per zero» |
| 2 | `f98ac16` | `calcola` nel server MCP |
| 3 | `fba55b9` | variante locale con `@tool` (`assistente/calcolatrice_locale.py`), con contratto ed esiti uguali a MCP |
| 4 | `04574ee` | `VARIANTE_CALCOLATRICE` (`mcp`/`locale`) nel `.env`; l'assistente toglie la versione MCP quando si sceglie `locale` |
| 5 | `7e3a9b9` | prove reali, `compose.yaml`, README e `CLAUDE.md` |
| revisione | `ae100c8` | interi grandi esatti e stesso schema nelle due varianti |

**Prove eseguite il 2026-11-08:**

- **Test automatici:** `python -m pytest -q` dà 213 passati e 18 saltati (le prove reali).
- **LM Studio**, modello `google/gemma-4-e2b`, con le variabili nuove passate nell'ambiente del test: 15 su 15.
  - Calcolatrice, «Quanto fa (3+4)*2?»: 14 sia con `mcp` sia con `locale`, e il log riporta l'origine giusta.
  - Errore controllato `__import__('os')`: messaggio identico nelle due varianti.
  - Orologio 5/5 più l'errore controllato; convertitore 5/5.
  - Dopo le correzioni della revisione, la prova della calcolatrice è stata rieseguita: 4 su 4.
- **Docker:**
  - prima esecuzione: il test con `avvia.ps1` è scaduto. Il container si era chiuso dopo 4 secondi, ma il comando è rimasto appeso per circa 34 minuti;
  - seconda esecuzione identica: 3 su 3 in 110 secondi, con `calcola (locale)` dentro il container.
- **Avvio diretto** con l'ingresso da una pipe, nelle varianti `locale` e `mcp`: uscite riportate nel README.

**Revisione finale indipendente:** nessun problema Critical. Due problemi Important, corretti con test che prima fallivano:

- **Interi grandi:** con 50 cifre di precisione, `2**200` e `10**60 + 1` erano arrotondati e presentati come esatti. Ora la precisione è di 400 cifre.
- **Variante locale con uno schema diverso:** mancava la descrizione dell'argomento, e un valore non testuale dava un errore in inglese. Ora usa lo stesso schema del server e lo stesso errore in italiano.

**Rimandati** (Minor):

- se `VARIANTE_CALCOLATRICE` manca, il messaggio non elenca i valori ammessi;
- i caratteri invisibili compaiono grezzi nel messaggio d'errore;
- `0 ** 0` dà «troppo grande» invece di 1;
- i valori minuscoli diventano 0 senza avviso;
- il JSON della variante locale ha gli spazi, quello MCP no;
- `max(1,2)` riceve il messaggio sulla virgola decimale;
- possibile causa del blocco Docker: il test scaduto resta in attesa delle pipe dei processi figli di PowerShell. È un'ipotesi del revisore, e riguarda codice del passo 1.

**Differenza dichiarata:** FastMCP rifiuta un argomento inventato dal modello, mentre `@tool` lo ignora. Il README la spiega.

## Da fare

1. **Tu aggiungi al tuo `.env` `MCP_PORTA=8765` e `VARIANTE_CALCOLATRICE=mcp`** (oppure `locale`). Finché mancano, `python -m assistente`, le prove reali e Docker si fermano subito con un messaggio che lo chiede. Non l'ho modificato perché il file è tuo.
2. **Tu approvi il merge** di `dev-calcolatrice` in `main`.
3. **Passo 3** (scadenze in variante MCP e FastAPI) sul branch `dev-scadenze`.

## Stato attuale

- **Branch:** `dev-calcolatrice`, creato da `main` (`a6eb059`) e non da `dev`, perché `dev` non contiene il passo 1, che è unito solo in `main`. Nessun push.
- **Ultimo commit:** quello di questo checkpoint, che segue `ae100c8`.
- **Non verificato:**
  - l'avvio interattivo da tastiera con `.\avvia.ps1`;
  - le prove con le variabili lette dal tuo `.env`;
  - la causa certa del blocco Docker della prima esecuzione.
- **Ancora in sospeso:** `.gitattributes` alla radice della repository resta cancellato nella copia di lavoro, e non l'ho toccato.
