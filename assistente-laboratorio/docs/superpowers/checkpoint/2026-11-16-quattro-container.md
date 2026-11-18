# Checkpoint — quattro container con un solo comando (lezione 6, step 9)

Specifica: [`2026-11-16-quattro-container-design.md`](../specs/2026-11-16-quattro-container-design.md). Piano: [`2026-11-16-quattro-container.md`](../plans/2026-11-16-quattro-container.md).

## Fatto

Il motivo: dal 14 novembre circa Smart App Control di Windows blocca le DLL di `psycopg-binary` (`libssl` e `libcrypto`). Il doppio clic su `avvia-chat.cmd` si fermava con un traceback, `python -m servizio_backend` non partiva sull'host e `python -m pytest` si interrompeva alla raccolta. L'utente ha scelto lo step 9, tutto in Docker, invece di spegnere Smart App Control.

- **Task 1 · La suite in un container** (`695570a`, `3390428`). `Dockerfile.test` e il servizio Compose `test` (profilo `test`, cartella del progetto montata in `/app`): `docker compose run --rm test`. `tests/compose_prova.py` raccoglie i pezzi comuni delle prove con Compose senza importare `psycopg`, così i test di `docker compose config` si caricano sull'host. Un test del servizio vale solo su Windows (porta in `TIME_WAIT` su Linux).
- **Task 2 · Indirizzi del back-end da variabili** (`dcf6535`). `BACKEND_HOST`, `POSTGRES_HOST`, `AGENTE_INDIRIZZO`, facoltative, predefinite `127.0.0.1`: fuori da Docker non cambia nulla. `leggi_valori_backend` controlla il `.env` senza importare `psycopg`; i messaggi d'avvio dicono l'indirizzo vero.
- **Task 3 · Compose, Dockerfile e nginx** (`3d441cd`). `docker compose up -d` accende `database`, `agente`, `backend` e `frontend`; `assistente` (la CLI) ha il profilo `cli`. `agente` e `backend` con `restart: on-failure` e controllo di salute su `/salute`; `backend` senza porte pubblicate, `depends_on` database sano e agente avviato. Il `Dockerfile` copia `servizio_backend/`. nginx inoltra a `${BACKEND_INDIRIZZO}:${BACKEND_PORTA}` (predefinito `backend`) e risolve il nome a ogni richiesta (`resolver 127.0.0.11 valid=10s`): parte anche con il back-end spento. `tests/frontend_prova.py` usa `--no-deps` e `BACKEND_INDIRIZZO=host.docker.internal`.
- **Task 4 · Il launcher accende e spegne i container** (`16cb6df`, poi `68afb71` dopo la revisione). Quattro passi: Docker, LM Studio, `docker compose up -d --wait` (con `--ricostruisci` anche `--build`), `/api/salute` attraverso nginx tutto `ok` entro 90 secondi. Guarda prima con `docker compose ps` che cosa è acceso e ferma con `docker compose stop` solo l'agente e il back-end che ha acceso, anche dopo un `up` fallito o un Ctrl+C. Alla scadenza di `up` chiude tutto l'albero di processi di Compose. Un `503` del back-end nomina il database. Solo libreria standard e `python-dotenv` (`assistente/lmstudio.py` contiene `verifica_server` senza langchain; un test controlla che dopo l'import non ci siano `psycopg`, `langchain_core`, `httpx`). Spariscono i processi Python sull'host e i log `logs/avvio_agente.log` e `logs/avvio_backend.log`.
- **Task 5 · La chiusura con la X** (`a5f0267`). `avvio_chat/console.py`: un gestore degli eventi della console, registrato prima di `up`, lancia `docker compose stop …` in un processo staccato (`CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`, non `DETACHED_PROCESS`, che faceva aprire una finestra al plugin `compose`).
- **Task 6 · L'avviso delle note** (`21a8b5f`). Con il container `agente` acceso, `.\avvia.ps1` avvisa che le note sono condivise e chiede «Aprire comunque la CLI? (S/N)»; con `-SenzaTty` non chiede.
- **Task 7 · Prove reali**, fatte dal controllore il 18 novembre (sotto, in «Stato attuale»).
- **Task 8 · Documenti.** `README.md` (requisiti, variabili, log, Docker, back-end, chat nel browser, test, diagnosi), `AVVIO-RAPIDO.md` (doppio clic in quattro passi, modo B con un comando, `docker compose build assistente`, test nel container), `CLAUDE.md` alla radice (struttura, comandi di test, variabili; tolta la riga «Non è lo step 9» e i log `avvio_*.log`), capitoli 00, 02, 08 (scheda, 6.1, 7.9–7.12, slide), 09 (sezione 10.6 e slide), 14 (sezione 13), 15 (nginx, prove, limiti), presentazioni `lezione-6.html` (slide nuova sullo step 9), `atlante.html`, `index.html`, `progetto-in-15-minuti.html` e gli schemi `sistema` e `processi` in `schemi.js`. I riferimenti `file:riga` che il codice dello step ha spostato sono aggiornati anche negli altri capitoli: `assistente/modello.py` (il controllo di LM Studio è passato in `assistente/lmstudio.py`), `compose.yaml`, `avvia.ps1`, `frontend/nginx/default.conf.template`, `servizio_backend/configurazione.py`. Indice `docs/superpowers/README.md` aggiornato.

## Da fare

- **Prove reali dell'utente** (numeri della specifica):
  - **3 · Clic vero sulla X.** Doppio clic, attesa di «La chat è accesa», chiusura con la X: entro 30 secondi `agente` e `backend` fermi (`docker compose ps`). Da fare due volte: da una finestra classica (conhost) e da una scheda di Windows Terminal. Se Windows Terminal uccidesse anche lo `stop` staccato, provare `CREATE_BREAKAWAY_FROM_JOB` con un ripiego.
  - **6 · Subito dopo l'accensione del PC.** Doppio clic appena compare il desktop, con Docker Desktop e LM Studio ancora in avvio: la chat deve aprirsi al primo colpo.
- **Non provati dal vivo:** `--ricostruisci`; Docker spento e LM Studio spento (solo test con comandi finti); un Ctrl+C in una console vera; la X premuta durante `docker compose up`; `.\avvia.ps1` da tastiera (provato con la risposta `N` da una pipe); la prima costruzione delle immagini senza cache.
- **Prove esistenti non eseguibili finché Smart App Control è attivo** (avviano il back-end come processo Python sull'host): `tests/test_reale_backend.py`, `tests/test_reale_docker_backend.py`, `tests/test_reale_browser.py`, `tests/test_reale_browser_lmstudio.py`. Restano nel progetto; con loro resta non verificato dal vivo `--no-deps` in `tests/frontend_prova.py`.
- **Unione:** il branch `dev-quattro-container` non è unito né in `dev` né in `main`; serve l'approvazione dell'utente.
- **Minori rimandati dalle revisioni:**
  - `avvio_chat/console.py` intercetta solo `OSError` quando lancia lo `stop` (meglio `Exception`);
  - test: la docstring vuota di `test_dopo_un_uscita_normale_…`; margine di 2 secondi nel test sulla console vera (meglio 3–4); il collegamento di `_ferma_i_figli` non è fissato da un test; il ramo Ctrl+C di `esegui_comando` non è provato; un'eccezione di `http.client` mentre si legge il corpo dell'errore; il motivo di uno `stop` fallito non compare;
  - `tests/test_compose_servizi.py` non controlla `depends_on.agente`, il volume dei log e la destinazione dei controlli di salute; `tests/test_nginx.py` non controlla il buffering per SSE; il `docker` finto di `tests/test_avvia_ps1.py` riconosce `ps` solo come secondo argomento;
  - il commento di `extra_hosts` in `compose.yaml` è fuorviante (il `resolver` di nginx non legge `/etc/hosts`; funziona grazie al DNS di Docker Desktop); ordine dei `COPY` nel `Dockerfile`;
  - `HOST_AGENTE_PREDEFINITO` riusato come predefinito di `POSTGRES_HOST` e `AGENTE_INDIRIZZO` (nome); `test_valori_senza_psycopg` lancia un sottoprocesso senza `cwd`; una riga di docstring lunga in `servizio_backend/__main__.py`; `import socket` inutilizzato in `tests/postgres_prova.py`;
  - stderr in cp1252 quando è rediretto (c'era già in `assistente/console.py`);
  - i 13 avvisi `DeprecationWarning` di `langsmith` (c'erano già prima dello step).
- **Step 2–5** della lezione 6: invariati.
- La cartella `.superpowers/`, alla radice della repository, non è tracciata né ignorata.

## Stato attuale

- **Branch:** `dev-quattro-container`, da `dev`. Codice fino a `21a8b5f`; questo checkpoint è nel commit dei documenti che lo segue. Nessun push, nessuna unione.
- **Test nel container**, 18 novembre 2026, `docker compose run --rm test`: **717 passati, 98 saltati, 0 falliti** (120 secondi). I saltati sono le prove reali e i test che valgono solo su Windows.
- **Test sull'host**, 18 novembre 2026, con `.venv`:
  - `python -m pytest tests/test_avvio_chat.py tests/test_avvia_ps1.py tests/test_nginx.py -q`: **104 passati, 1 saltato** (`test_fuori_da_windows_non_fa_nulla`, che vale solo fuori da Windows);
  - `python -m pytest --docker tests/test_compose_servizi.py tests/test_compose_frontend.py -q`: **7 passati**.
- **Prove reali** del 18 novembre 2026 (Task 7, sul progetto Compose dell'utente; numeri della specifica):
  - **1 · Avvio con agente e back-end spenti**, `avvia-chat.cmd --senza-browser`: [1/4]…[4/4] in 14,8 secondi, `/api/salute` `{stato ok, database ok, agente ok}`, quattro servizi accesi. Passata.
  - **2 · `esci`:** «Fermo ciò che ho acceso (backend, agente)», codice 0, poi accesi solo `database` e `frontend`. Passata.
  - **4 · Tutto già acceso:** «Agente e back-end erano già accesi…», codice 0, quattro servizi ancora accesi. Passata.
  - **5 · Turno vero con LM Studio attraverso nginx** (chat 8 nel database dell'utente, lasciata lì): 18 eventi `testo` e `fine` in 1 minuto e 34 secondi, risposta con lo strumento dell'ora («Ora sono le 17:05 nel fuso orario Europe/Rome»); dopo `docker compose restart backend` la chat 8 ha ancora i due messaggi. Passata.
  - **7 · `'N' | powershell -File .\avvia.ps1`** con l'agente acceso: avviso e «Aprire comunque la CLI? (S/N)», codice 0, CLI non aperta. Passata (ingresso da una pipe, non una tastiera).
  - **3 (X vera) e 6 (dopo l'accensione del PC):** da fare, con l'utente. Coperture parziali: un test automatico chiude una console vera; una prova del Task 5 su un progetto Compose separato ha fermato il container 4 secondi dopo la chiusura della console.
- **Prove del Task 3** (16 novembre): `docker compose up -d --build --wait` con codice 0; con il back-end fermo la pagina risponde `200` e `/api/salute` `502`; riacceso, di nuovo tutto `ok`; `.\avvia.ps1 -SenzaTty` con il profilo `cli` funziona.
- **Documenti verificati così:** ogni `file:riga` scritto o spostato controllato con `grep -n` sul codice di `21a8b5f`; `docker compose config --services` e `docker compose --dry-run build` (con e senza `assistente`) per il profilo `cli`; le pagine HTML modificate lette con `html.parser` (nessun tag non chiuso, collegamenti locali esistenti), `node --check schemi.js`, e tutte e sei le pagine caricate con jsdom eseguendo gli script: tutti gli schemi disegnati, nessun errore. Non aperte in un browser vero.
- **Servizi dell'utente:** non fermati né ricreati durante la scrittura dei documenti; `/api/salute` alla fine `{"stato":"ok","database":"ok","agente":"ok"}`.
