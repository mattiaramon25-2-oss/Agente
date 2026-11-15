# Checkpoint — avvio rapido e materiale di studio visuale

## Fatto

- **`AVVIO-RAPIDO.md`**, alla radice del progetto: una pagina con i tre modi di avvio (chat da terminale, chat nel browser, terminale in Docker), che cosa si deve vedere, come fermare e gli errori più comuni. Collegata dal README con una riga in cima.
- **`docs/studio/presentazioni/`**, pagine HTML che si aprono con doppio clic e funzionano senza Internet:
  - `index.html`: l'ingresso, con i tasti e il modo di usarle per studiare;
  - `progetto-in-15-minuti.html` (15 slide), `lezione-4.html` (16), `lezione-5.html` (20), `lezione-6.html` (21): 72 slide in tutto, ognuna con la nota «Da dire a voce» e il capitolo di riferimento; in ogni lezione una slide con tre domande d'orale;
  - `atlante.html`: 18 schemi su una pagina, con che cosa guardare e dove approfondire;
  - `stile.css`, `slide.js`, `schemi.js`: aspetto, navigazione e schemi. Nessuna libreria. Gli schemi sono descritti una volta sola in `schemi.js` e disegnati in SVG nel browser, quindi atlante e slide mostrano sempre lo stesso disegno.
- **Comandi delle presentazioni:** frecce, `Spazio`, `Home`, `Fine`; `N` note; `E` elenco di tutte le slide con le note; `F` schermo intero; `T` tema chiaro o scuro, che resta tra una pagina e l'altra; l'indirizzo segue la slide (`#7`); `Ctrl+P` stampa una slide per pagina, sempre in chiaro.
- **Documenti aggiornati:** `docs/studio/00-indice.md` (la sezione «Come preparare una presentazione» è diventata «Presentazioni e schemi pronti»; riga per la guida in «Le altre fonti»), `CLAUDE.md` (struttura: `presentazioni/` e `AVVIO-RAPIDO.md`), `docs/superpowers/README.md` (specifica, piano e checkpoint di questo passo).
- **Password del database riallineata.** Verificando la guida, il back-end non partiva: `password authentication failed for user "assistente"`. Il file `.env` era stato modificato il 15 novembre alle 18:45 e conteneva una password diversa da quella con cui il volume era stato creato il 10 novembre. Su scelta dell'utente la password del database è stata portata a quella del `.env` con `ALTER USER`, eseguito dentro il container. Dopo: back-end avviato, `/salute` con `database ok` e `agente ok`, le 3 chat ancora presenti. Il comando è ora nella guida e nella tabella «Diagnosi» del README.
- **Revisione finale indipendente** di tutto il branch, con i fatti delle slide confrontati con il codice: nessun errore grave, 3 riscontri importanti e 14 minori. Corretti:
  - lo schema dell'avvio diceva «quattro posti, poi UTC»: i posti sono tre, UTC è il quarto;
  - la chat da terminale e il servizio dell'agente usano la stessa `MCP_PORTA`, quindi non si usano insieme: ora lo dicono la guida, l'atlante, lo schema `processi` e la nota della mappa. Provato: con il servizio dell'agente acceso, `python -m assistente` esce con `Porta 8765 già in uso`;
  - il ponte MCP restituisce un testo, il `ToolMessage` e la riga di log nascono nel nodo `strumenti` (schema `viaggio-mcp`); le quattro richieste MCP valgono per una chiamata riuscita; l'`origine` compare anche nelle risposte dell'API; il `threading.Lock` vale per `/chat`; `Europe/Berlin` è la traduzione di `W. Europe Standard Time`; i file di `risorse/` sono tre; dopo il cambio della password il back-end va riavviato;
  - la stampa: solo le presentazioni usano pagine 16:9, indice e atlante no; il tasto `N` su una slide di titolo non lascia più una fascia vuota;
  - la legenda dei colori: il bordo spesso segna «il punto da guardare», il verde resta a chi esegue gli strumenti.
- **Capitolo 09 riallineato.** La revisione ha trovato che `docs/studio/09-test-e-verifiche.md` riportava ancora i numeri di prima della revisione finale dello step 8 (73 saltati, 85 test Vitest in 9 file, 6 prove nel browser). Corretti in tre punti con i numeri del README: 74 saltati, 108 test in 11 file, 7 prove. Verificato il 15 novembre: `npm test` 108 passati in 11 file; 7 funzioni di prova in `tests/test_reale_browser.py` e 2 in `tests/test_compose_frontend.py`.
- **Decisioni dell'utente (15 novembre):** pagine HTML e non PowerPoint; una presentazione per lezione più il riassunto; solo la guida, senza script di avvio unico; esecuzione del piano nella stessa sessione.

## Da fare

- Lo **script di verifica** delle pagine non è nel repository: è stato usato dalla cartella temporanea della sessione. Se le presentazioni verranno modificate spesso, conviene portarlo tra i test (con Playwright, come le prove del browser): è una modifica alla suite, quindi va decisa con l'utente.
- **Step 9** della lezione 6 (un solo comando per quattro container) e **step 2–5**: invariati. Quando saranno fatti, vanno aggiornati `AVVIO-RAPIDO.md` (il modo B avrà un comando solo), la slide dei nove step di `lezione-6.html` e gli schemi `processi` e `lezioni`.
- **Riscontri della revisione lasciati aperti:** il README dice ancora «quattro terminali» per la chat nel browser, la guida ne usa tre (i due comandi `docker compose up -d` tornano al prompt); con l'esecuzione degli script disabilitata in PowerShell fallisce anche `Activate.ps1`, e né il README né la guida dicono come fare; le slide di titolo non hanno la nota «Da dire a voce».
- Dei 16 capitoli di `docs/studio/` sono stati toccati solo l'indice e tre righe del capitolo 09: le loro «Scalette per le slide» restano come materiale per nuove presentazioni.
- La cartella `.superpowers/`, alla radice della repository, non è tracciata né ignorata: come nel checkpoint del 12 novembre, da aggiungere al `.gitignore` se l'utente lo vuole.

## Stato attuale

- **Branch:** `dev-docs-avvio-studio`, da `dev` (`8061ac1`), unito in `dev` il 15 novembre 2026 su richiesta dell'utente, dopo che ha guardato il materiale. Non unito in `main`. Nessun push.
- **Codice dell'applicazione:** non modificato. `git diff --stat 8061ac1..HEAD` tocca solo `AVVIO-RAPIDO.md`, `README.md`, `CLAUDE.md` e file sotto `docs/`.
- **Schemi:** 18, uno in più dei 17 del piano (`markdown-sicuro`). Le presentazioni hanno 16, 20 e 21 slide invece di circa 14, 18 e 18.
- **Test:** `python -m pytest -q` il 15 novembre 2026: 625 passati, 74 saltati, come il 12 novembre.
- **Verifica delle pagine**, con Chromium di Playwright, da `file://`:
  - 6 pagine, 0 problemi: nessun errore in console, nessuna richiesta di rete, collegamenti relativi tutti esistenti;
  - in nessuna delle 72 slide il contenuto esce dai bordi; in ogni schema il testo sta dentro i nodi e le etichette non coprono i nodi;
  - a 1024×768 la slide resta nella finestra; la vista a elenco mostra tutte le slide; la stampa produce una pagina per slide (15, 16, 20, 21);
  - 24 prove dei comandi passate su 24 (tasti, indirizzo, note, elenco, pulsanti, tema che resta, collegamenti tra indice e presentazioni);
  - dopo le correzioni della revisione: 43 controlli sulle correzioni passati, e di nuovo 6 pagine con 0 problemi e 24 prove su 24;
  - le istantanee di tutte le slide sono state guardate in tema chiaro; in tema scuro quelle della lezione 6 e lo schema del sistema.
- **Verifica della guida**, il 15 novembre 2026: modo A avviato e chiuso (`"esci" | python -m assistente`, uscita 0, dieci strumenti elencati); modo B con `python -m servizio_agente` e `python -m servizio_backend` avviati e fermati in modo ordinato (uscita 0), `/salute` ok anche attraverso nginx su `http://127.0.0.1:8780/api/salute`.
- **Non verificato:**
  - una conversazione completa con il modello (nessun turno è stato eseguito);
  - i comandi 1 e 4 del modo B, perché i container `database` e `frontend` erano già accesi;
  - il modo C (Docker), né da tastiera né da pipe;
  - le pagine in Edge e in Firefox: sono state aperte solo con Chromium di Playwright;
  - lo schermo intero (`F`) e la stampa su carta: della stampa è stato contato solo il numero di pagine del PDF;
  - il comando `ALTER USER` con una password che contiene apici.
- **Servizi:** i container `database` e `frontend` sono rimasti accesi per tutta la sessione. Agente e back-end sono stati avviati e fermati per la verifica; dopo l'unione in `dev` l'utente ha chiesto di avviare la chat nel browser.
