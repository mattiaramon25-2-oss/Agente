# Chat nel browser installabile come app — piano di implementazione

> **Per chi esegue:** usare superpowers:subagent-driven-development oppure superpowers:executing-plans, un task alla volta. I passi usano le caselle (`- [ ]`).

**Obiettivo:** una chat in TypeScript/Svelte 5, installabile come app (PWA), servita da un container nginx che inoltra `/api` al back-end dello step 7, con streaming, progetti, ricerca, cancellazione ed errori sempre visibili.

**Architettura:** `frontend/` contiene un'app Vite + Svelte 5. La logica senza interfaccia (lettura SSE, client dell'API, markdown, tema, stato dell'app) sta in moduli TypeScript testati con Vitest. I componenti Svelte la usano. Un'immagine a due fasi (Node per compilare, nginx per servire) diventa il servizio Compose `frontend` su `127.0.0.1`, e nginx inoltra `/api/*` a `host.docker.internal:${BACKEND_PORTA}`. Le prove nel browser usano Playwright per Python, dentro pytest.

**Tecnologie:** Node 24.21, TypeScript, Svelte 5, Vite, Vitest con jsdom, marked, DOMPurify, nginx-unprivileged 1.30.6, Playwright per Python 1.65.0.

**Specifica:** [`specs/2026-11-11-frontend-chat-design.md`](../specs/2026-11-11-frontend-chat-design.md). Branch `dev-frontend`, già creato da `dev`.

## Vincoli globali

- Comandi Python da `assistente-laboratorio/` con `.venv`; comandi npm da `assistente-laboratorio/frontend/`.
- **Versioni npm esatte**, senza `^` né `~`, con `package-lock.json` versionato. Per ogni pacchetto si prende la versione più recente pubblicata **almeno 14 giorni prima** di oggi (`npm view <pacchetto> time`), purché sia compatibile con le altre. In particolare, se `svelte-check` non supporta TypeScript 7, si usa l'ultima 5.x. Le versioni scelte si riportano nel commit del Task 1.
- Pacchetti npm ammessi:
  - per l'esecuzione: `svelte`, `marked`, `dompurify`;
  - per lo sviluppo: `vite`, `@sveltejs/vite-plugin-svelte`, `typescript`, `svelte-check`, `@tsconfig/svelte`, `vitest`, `jsdom`.
  Nient'altro senza approvazione.
- Python: una dipendenza nuova, solo per lo sviluppo: `playwright==1.65.0` in `requirements-dev.txt`. Chromium si installa con `python -m playwright install chromium`.
- Testi dell'interfaccia, messaggi d'errore, nomi in codice e commenti **in italiano**.
- Stile:
  - tema chiaro «acqua e salvia»: `#f6f8f6`, `#eef3f0`, `#d9ece7`, `#5fb3a6`, `#2f3e3c`;
  - tema scuro «acqua di notte»: `#16211f`, `#121b19`, `#1f3a35`, `#4fb3a2`, `#dfe9e6`;
  - angoli **8–12 px**, niente forme a pillola, font di sistema, verde acqua solo per pulsante principale, chat aperta e righe degli strumenti;
  - errori in un rosso-terracotta smorzato, per esempio `#c0705a` nel chiaro e `#d08a75` nello scuro.
- Il testo del modello entra nella pagina **solo** attraverso `rendiMarkdown` (Task 3). Nessun `{@html}` su altro testo.
- Il back-end resta su `127.0.0.1`; il front-end si pubblica solo su `127.0.0.1:${FRONTEND_PORTA:-8780}`; in `compose.yaml` niente `:?` per le variabili del servizio `frontend`.
- Testi fissi:
  - back-end spento: «Il back-end non risponde: avvialo con python -m servizio_backend.»;
  - flusso finito senza `fine`: «La risposta si è interrotta: il messaggio non è stato salvato.»;
  - errore senza `{"errore"}`: «Errore inatteso del back-end (stato N).»
- Conventional Commits in italiano, **senza** righe `Co-Authored-By`; staging selettivo; niente push; niente merge senza approvazione.

## Attenzione in revisione

1. **Un evento SSE spezzato tra due pezzi della rete**, anche a metà di un carattere accentato UTF-8. Deve arrivare intero e corretto: Task 1, `evento spezzato tra due pezzi` e `carattere multibyte spezzato`.
2. **Il testo del modello contiene `<script>`, `<img onerror>` o un link `javascript:`.** Non deve finire nella pagina: Task 3, `toglie script e attributi pericolosi`.
3. **Il primo invio di una chat nuova fallisce.** Il nuovo invio deve usare la stessa chat, senza crearne una seconda: Task 4, `riprova sulla stessa chat`.
4. **nginx risponde 502 con una pagina HTML** (back-end spento). Va riconosciuto come «back-end spento», senza tentare di leggerlo come JSON: Task 2, `502 HTML è back-end spento`.
5. **Domanda inviata due volte** (doppio Invio o clic ripetuto) mentre un turno è in corso. Il secondo invio va ignorato: Task 4, `ignora un secondo invio durante il turno`.

---

### Task 1: progetto `frontend/` e lettura del flusso SSE

**File:**
- Crea: `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/svelte.config.js`, `frontend/index.html`, `frontend/src/main.ts`, `frontend/src/App.svelte` (per ora un segnaposto), `frontend/src/lib/sse.ts`, `frontend/src/lib/sse.test.ts`, `frontend/.gitignore` (`node_modules/`, `dist/`)

**Interfacce prodotte:**
- Script npm:
  - `dev`: Vite, con proxy `/api` verso `http://127.0.0.1:${BACKEND_PORTA ?? 8768}` che toglie `/api`;
  - `build`;
  - `check` (`svelte-check`);
  - `test` (`vitest run`).
- `type EventoSse = { evento: string; dati: unknown }`
- `class LettoreSse { aggiungi(pezzo: Uint8Array): EventoSse[]; fine(): void }`. Decodifica UTF-8 in modo incrementale con `TextDecoder` e `stream: true`. Divide gli eventi sulla riga vuota. Accetta `\n` e `\r\n`. Ignora le righe che iniziano con `:`. Senza `event:` l'evento si chiama `message`. Il campo `data` è JSON.
- Con Vite il dev server ascolta solo su `127.0.0.1`.

- [ ] **Passo 1:** creare i file di configurazione con le versioni scelte come da vincoli, poi `npm install`.
- [ ] **Passo 2: test che falliscono** in `sse.test.ts`:
  - `un evento completo`: `event: testo\ndata: {"pezzo":"ciao"}\n\n` dà `[{evento:"testo", dati:{pezzo:"ciao"}}]`;
  - `evento spezzato tra due pezzi`: lo stesso testo diviso in due `Uint8Array` a metà di `data:` dà `[]` al primo pezzo e l'evento al secondo;
  - `carattere multibyte spezzato`: «è» diviso tra due pezzi arriva intatto;
  - `più eventi in un pezzo`, `righe CRLF`, `commenti ignorati`, `U+2028 come escape JSON resta nella stringa` (dati `{"r":"a\\u2028b"}` → `"a b"`).
- [ ] **Passo 3:** `npm test` → FALLISCONO. **Passo 4:** implementare `sse.ts`. **Passo 5:** `npm test`, `npm run check` e `npm run build` → tutto verde.
- [ ] **Passo 6: commit** `feat(frontend): progetto Svelte 5 + Vite e lettura del flusso SSE` (nel corpo, le versioni scelte).

### Task 2: client dell'API del back-end

**File:** crea `frontend/src/lib/api.ts`, `frontend/src/lib/api.test.ts`

**Interfacce:**
- Consuma: `LettoreSse` (Task 1).
- Produce i tipi, con le forme del back-end, vedi la specifica dello step 7:
  - `Strumento {nome, origine, argomenti: Record<string, unknown>}`;
  - `Progetto {id, nome, istruzioni, numero_chat, creato, aggiornato}`;
  - `ChatBreve {id, titolo, progetto_id: number | null, creata, aggiornata}`;
  - `Messaggio {id, ruolo: "utente" | "assistente", testo, strumenti: Strumento[] | null, creato}`;
  - `Chat = ChatBreve & {messaggi: Messaggio[]}`;
  - `RisultatoRicerca {chat_id, titolo, progetto_id, messaggio_id, ruolo, estratto}`;
  - `FineTurno {risposta, strumenti: Strumento[], messaggio_utente_id, messaggio_assistente_id, titolo}`.
- `class ErroreApi extends Error { stato: number | null; backendSpento: boolean }`.
- Funzioni, tutte con base `"/api"`; il `fetch` è iniettabile per i test con `impostaFetch(f)`:
  - `salute()`;
  - `elencaProgetti()`, `creaProgetto(nome, istruzioni)`, `aggiornaProgetto(id, campi: {nome?, istruzioni?})`, `cancellaProgetto(id)`;
  - `elencaChat(filtro?: number | "nessuno")`, `creaChat(progetto_id: number | null)`, `leggiChat(id)`, `spostaChat(id, progetto_id: number | null)`, `cancellaChat(id)`;
  - `cerca(q)`;
  - `inviaMessaggio(chatId, testo, gestori: {suTesto(pezzo: string), suStrumento(s: Strumento)}, segnale?: AbortSignal): Promise<FineTurno>`.
- Regole d'errore:
  - errore di rete, oppure `502`/`503`/`504` con corpo non JSON → `ErroreApi(testo fisso back-end spento, backendSpento=true)`;
  - corpo `{"errore": m}` → `ErroreApi(m, stato)`;
  - altro → «Errore inatteso del back-end (stato N).».
  - Durante il flusso: un evento `errore` → `ErroreApi(dati.errore, null)`; un flusso finito senza `fine` → `ErroreApi(testo fisso interruzione)`.

- [ ] **Passo 1: test**, con un `fetch` finto che restituisce `Response` costruite nel test, anche con corpo `ReadableStream` a più pezzi:
  - `elenca progetti`;
  - `crea chat manda progetto_id`;
  - `cancella 204 senza corpo`;
  - `errore 409 in italiano dal back-end`;
  - `502 HTML è back-end spento`;
  - `errore di rete è back-end spento`;
  - `turno completo`: i gestori ricevono strumento, poi testo, poi testo; risolve con `FineTurno`;
  - `turno con evento errore`;
  - `turno finito senza fine`;
  - `cerca codifica la query` (`q=a b&c` → `q=a%20b%26c`).
- [ ] **Passo 2:** FALLISCONO. **Passo 3:** implementare. **Passo 4:** `npm test` e `npm run check` → verde.
- [ ] **Passo 5: commit** `feat(frontend): client dell'API del back-end con errori in italiano e turno in streaming`

### Task 3: markdown sicuro e tema

**File:** crea `frontend/src/lib/markdown.ts`, `frontend/src/lib/markdown.test.ts`, `frontend/src/lib/tema.ts`, `frontend/src/lib/tema.test.ts`. Ambiente Vitest `jsdom` per questi file.

**Interfacce prodotte:**
- `rendiMarkdown(testo: string): string`: `marked` (GFM, interruzioni di riga) seguito da `DOMPurify.sanitize`. I link si aprono in una nuova finestra con `rel="noopener noreferrer"`.
- `type SceltaTema = "automatico" | "chiaro" | "scuro"`.
- `temaEffettivo(scelta, preferisceScuro: boolean): "chiaro" | "scuro"`.
- `leggiScelta(): SceltaTema` e `salvaScelta(s)` su `localStorage`, chiave `"tema"`. Se `localStorage` non c'è o solleva un errore si usa `"automatico"`.
- `applicaTema(t)`: imposta `document.documentElement.dataset.tema`.

- [ ] **Passo 1: test.**
  - `grassetto ed elenchi`.
  - `codice in blocco`.
  - `toglie script e attributi pericolosi`: `<script>alert(1)</script>`, `<img src=x onerror=alert(1)>`, `[x](javascript:alert(1))`. Nel risultato non ci sono `<script`, `onerror` né `javascript:`.
  - `link esterno con noopener`.
  - Tema: tutte e sei le combinazioni di `temaEffettivo`; `scelta salvata e riletta`; `localStorage che solleva un errore dà automatico`.
- [ ] **Passo 2:** FALLISCONO. **Passo 3:** implementare. **Passo 4:** verde.
- [ ] **Passo 5: commit** `feat(frontend): markdown ripulito con DOMPurify e scelta del tema`

### Task 4: stato dell'app

**File:** crea `frontend/src/lib/stato.svelte.ts`, `frontend/src/lib/stato.test.ts`

**Interfacce:**
- Consuma: l'API del Task 2, che il costruttore riceve come oggetto, così i test possono passare un'API finta.
- Produce `class StatoApp`, con i campi reattivi `$state`:
  - `progetti`, `recenti` (chat senza progetto), `vista` (`{tipo: "chat", chatId: number | null, progettoId: number | null} | {tipo: "progetto", progettoId: number}`), `chatAperta: Chat | null`;
  - `turno: {domanda, testo, strumenti: Strumento[]} | null`;
  - `erroreTurno: string | null`, `bozza: string` (testo della casella), `backendSpento: boolean`;
  - `ricerca: {q, risultati: RisultatoRicerca[]} | null`, `avvisi: {id, testo}[]`.
- Metodi:
  - `carica()`;
  - `nuovaChat(progettoId?: number)`, `apriChat(id)`, `apriProgetto(id)`;
  - `invia(): Promise<void>`;
  - `cerca(q)`, con attesa di 300 ms gestita dal componente;
  - `creaProgetto(nome)`, `salvaProgetto(id, campi)`, `eliminaChat(id)`, `eliminaProgetto(id)`, `spostaChat(id, progettoId)`;
  - `controllaBackend()`, usata dal ciclo di 5 s finché `backendSpento`.
- Regole di `invia`:
  - si ignora con bozza vuota o con un turno già in corso;
  - una chat nuova si crea al primo invio e il suo id si ricorda subito;
  - a `fine`, il messaggio si aggiunge a `chatAperta`, il titolo si aggiorna e le liste si ricaricano;
  - con un errore, `erroreTurno` prende il messaggio, la bozza torna la domanda e la chat già creata resta aperta; un back-end spento imposta anche `backendSpento`.

- [ ] **Passo 1: test con un'API finta.**
  - `invia in una chat nuova crea la chat e salva il turno`.
  - `riprova sulla stessa chat`: primo turno con errore, secondo riuscito; `creaChat` è chiamata una volta sola.
  - `ignora un secondo invio durante il turno`.
  - `errore del turno rimette la bozza`.
  - `back-end spento accende la striscia e controllaBackend la spegne`.
  - `nuova chat dentro un progetto passa progetto_id`.
  - `elimina la chat aperta torna a una chat vuota`.
  - `errore di un'azione va negli avvisi`: per esempio un 409 su `eliminaChat`.
  - `ricerca sotto i 2 caratteri non chiama l'API`.
- [ ] **Passo 2:** FALLISCONO. **Passo 3:** implementare. **Passo 4:** verde.
- [ ] **Passo 5: commit** `feat(frontend): stato dell'app con turno, riprova, errori e back-end spento`

### Task 5: interfaccia, cioè barra laterale, chat, progetti, ricerca ed errori

**File:**
- Crea `frontend/src/stile.css`, con variabili per i due temi su `:root[data-tema=…]`, raggi `--raggio: 10px` e `--raggio-piccolo: 8px`.
- Crea i componenti in `frontend/src/componenti/`: `BarraLaterale.svelte`, `VistaChat.svelte`, `Messaggio.svelte`, `RigaStrumento.svelte`, `Casella.svelte`, `VistaProgetto.svelte`, `RisultatiRicerca.svelte`, `MenuAzioni.svelte`, `Conferma.svelte`, `Avvisi.svelte`, `StrisciaBackend.svelte`, `SceltaTema.svelte`.
- Modifica `App.svelte`.

**Interfacce:** consuma `StatoApp` (Task 4), `rendiMarkdown` e il tema (Task 3). Per i test end-to-end (Task 8) aggiunge attributi `data-test`: `nuova-chat`, `casella`, `invia`, `messaggio-utente`, `messaggio-assistente`, `riga-strumento`, `errore-turno`, `striscia-backend`, `ricerca`, `risultato`, `progetto`, `chat`, `menu`, `elimina`, `conferma`, `istruzioni`, `salva-istruzioni`.

- [ ] **Passo 1:** costruire la disposizione e il comportamento descritti nelle sezioni «Com'è fatta la finestra» e «Come si comporta» della specifica, con lo stile dei vincoli globali.
  - `RigaStrumento` mostra `nome · valori` con i valori uniti da `, `, come la CLI.
  - `Invio` invia, `Maiusc+Invio` va a capo.
  - Il selettore del tema sta in fondo alla barra laterale.
- [ ] **Passo 2:** `npm run check`, `npm test` e `npm run build` → verde, senza avvisi di accessibilità di `svelte-check`.
- [ ] **Passo 3: verifica a vista.**
  - Avviare database, agente e back-end, poi `npm run dev`.
  - Nel browser integrato: una conversazione, un progetto con istruzioni, una ricerca, l'eliminazione con conferma.
  - Fermare il back-end e controllare che compaia la striscia; poi riavviarlo e controllare che la striscia sparisca.
  - Provare i temi chiaro e scuro.
  - Allegare al report due schermate, una per tema.
- [ ] **Passo 4: commit** `feat(frontend): interfaccia zen con barra laterale, chat in streaming, progetti, ricerca ed errori`

### Task 6: app installabile

**File:**
- Crea `frontend/public/manifest.webmanifest`, `frontend/public/sw.js`, `frontend/public/icone/icona.svg`, `icona-192.png`, `icona-512.png`.
- Crea `frontend/src/lib/manifest.test.ts`.
- Modifica `index.html` (link al manifest, `theme-color` per i due temi) e `main.ts`, che registra `sw.js` solo in produzione.

- [ ] **Passo 1: test.** Il test legge `public/manifest.webmanifest` e verifica:
  - `name: "Assistente del laboratorio"`, `short_name: "Assistente"`, `display: "standalone"`, `start_url: "/"`;
  - `theme_color: "#5fb3a6"`, `background_color: "#f6f8f6"`;
  - le icone 192 e 512 PNG esistono, con quelle dimensioni lette dall'intestazione del PNG.
- [ ] **Passo 2:** creare le icone: un simbolo semplice in verde acqua su fondo chiaro, generato una volta e versionato. Scrivere un `sw.js` minimo: `install`/`activate` e un gestore `fetch` che lascia passare tutto senza cache, `/api/` compreso.
- [ ] **Passo 3:** `npm test`, `npm run build` → verde; in `dist/` ci sono manifest, icone e `sw.js`.
- [ ] **Passo 4: commit** `feat(frontend): manifest, icone e service worker per installare la chat come app`

### Task 7: container `frontend` con nginx

**File:** crea `frontend/Dockerfile`, `frontend/nginx/default.conf.template`, `frontend/.dockerignore` e `tests/test_compose_frontend.py`; modifica `compose.yaml` e `.env.example`

**Interfacce prodotte:**
- Servizio Compose `frontend`:
  - `build: ./frontend`;
  - `environment: BACKEND_PORTA: ${BACKEND_PORTA:-8768}`;
  - `ports: ["127.0.0.1:${FRONTEND_PORTA:-8780}:8080"]`;
  - `extra_hosts: ["host.docker.internal:host-gateway"]`.
- nginx, che ascolta su 8080:
  - `location /api/` → `proxy_pass http://host.docker.internal:${BACKEND_PORTA}/;` con `proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 300s`, `proxy_http_version 1.1`, `Connection ""`;
  - fallback a `index.html`;
  - `index.html`, `sw.js` e `manifest.webmanifest` con `Cache-Control: no-cache`; `/assets/` con cache lunga e `immutable`.
- `.env.example`: riga `FRONTEND_PORTA=8780` con un commento.

- [ ] **Passo 1: test Python**, senza Docker in esecuzione ma con `docker compose config`:
  - `test_frontend_solo_su_127`: la configurazione mostra `host_ip: 127.0.0.1` per il servizio `frontend`;
  - `test_config_senza_frontend_porta`: con un `--env-file` temporaneo senza `FRONTEND_PORTA` né `POSTGRES_*`, il codice di uscita è 0.
  - Marcarli `docker`, perché richiedono il comando `docker`.
- [ ] **Passo 2:** implementare. `docker compose build frontend` → immagine creata.
- [ ] **Passo 3: verifica**, con database, agente e back-end accesi:
  - `docker compose up -d frontend`;
  - `curl.exe -s http://127.0.0.1:8780/api/salute` dà il JSON del back-end;
  - un turno con `curl.exe -N` attraverso `/api/chat/<id>/messaggi` mostra gli eventi arrivare uno alla volta, cioè nessun buffering;
  - `curl.exe -I http://127.0.0.1:8780/sw.js` ha `no-cache`.
  - Poi `docker compose stop frontend`.
- [ ] **Passo 4:** `python -m pytest -q` → verde, con i test nuovi saltati senza `--docker`; `python -m pytest --docker tests/test_compose_frontend.py` → verde.
- [ ] **Passo 5: commit** `feat(docker): servizio frontend con nginx su 127.0.0.1 e inoltro di /api al back-end`

### Task 8: prove nel browser con Playwright (agente finto)

**File:** crea `tests/test_reale_browser.py` e `tests/frontend_prova.py`; modifica `requirements-dev.txt`

**Interfacce:**
- Consuma:
  - `database_di_prova()`, che restituisce `DatabaseProva(dsn, env)`, e `ferma`/`riavvia` da `tests/postgres_prova.py`;
  - `servizio_agente.app.crea_app` con `ModelloFinto`/`RouterFinto`, come in `tests/test_reale_docker_backend.py`;
  - `servizio_backend.app.crea_app`, `ArchivioPostgres` e `ClientAgente`;
  - i `data-test` del Task 5.
- Produce `tests/frontend_prova.py` con `@contextmanager frontend_di_prova(porta_backend: int) -> Iterator[str]`. Avvia `docker compose -p assistente-laboratorio-prova-frontend up -d --build frontend` con `BACKEND_PORTA=<porta_backend>` e `FRONTEND_PORTA=<porta libera>`, aspetta che `/` risponda e restituisce l'URL. Alla fine fa sempre `down`. Avverte se la pulizia fallisce, come `postgres_prova.py`.

- [ ] **Passo 1:** aggiungere `playwright==1.65.0` a `requirements-dev.txt`, installarlo e lanciare `python -m playwright install chromium`.
- [ ] **Passo 2: prove**, con `pytestmark = pytest.mark.docker`. Agente finto e back-end girano in uvicorn su porte libere di `127.0.0.1`, il database è quello di prova; Chromium è senza finestra.
  - `test_conversazione_completa`:
    - si apre l'app e si invia «Quanto fa (3+4)*2?»;
    - con l'agente finto che risponde con `calcola`, poi «Il risultato è **14**.», compaiono la riga dello strumento e il messaggio con `<strong>14</strong>`;
    - il titolo nella barra laterale diventa «Quanto fa (3+4)*2?»;
    - dopo `page.reload()` la chat c'è ancora con i due messaggi.
  - `test_progetto_con_istruzioni`: si crea un progetto, si salvano le istruzioni e si apre una chat nel progetto; dopo un turno, le istruzioni sono quelle ricevute dall'agente finto.
  - `test_ricerca_e_eliminazione`: la ricerca «14» trova la chat; si elimina con conferma e la chat non c'è più.
  - `test_errore_agente_spento`: si ferma l'agente finto e si invia un messaggio; compare `errore-turno` con «non risponde» e la casella contiene di nuovo la domanda.
  - `test_striscia_back_end_spento`: si ferma il back-end e compare `striscia-backend` con il testo fisso; si riavvia il back-end sulla stessa porta e la striscia sparisce entro 15 s.
  - `test_installabile`: `/manifest.webmanifest` risponde con JSON valido e `navigator.serviceWorker.ready` si risolve.
- [ ] **Passo 3:** `python -m pytest --docker tests/test_reale_browser.py -v -s` → tutte PASS. Poi `python -m pytest -q` → verde, con le nuove saltate.
- [ ] **Passo 4: commit** `test(frontend): prove nel browser con Playwright, conversazione completa ed errori mostrati`

### Task 9: prova reale nel browser con LM Studio

**File:** crea `tests/test_reale_browser_lmstudio.py`, con `pytestmark = [pytest.mark.lmstudio, pytest.mark.docker]`

- [ ] **Passo 1:** come il Task 8, ma con l'agente vero, cioè `ambiente_reale()` servito da uvicorn. Dal browser si chiede «Quanto fa (3+4)*2?». La risposta finale contiene «14», c'è una `riga-strumento` con `calcola` e il testo compare a pezzi: durante il turno il messaggio dell'assistente cambia almeno due volte prima di `fine`. Il modello non si cambia; se fallisce per il suo comportamento, si riesegue una volta e poi si riporta con le evidenze.
- [ ] **Passo 2:** `python -m pytest --lmstudio --docker tests/test_reale_browser_lmstudio.py -v -s` → PASS.
- [ ] **Passo 3: commit** `test(frontend): prova reale nel browser con LM Studio`

### Task 10: verifica completa e prova a mano

- [ ] **Passo 1:** `npm test`, `npm run check`, `python -m pytest`, poi `python -m pytest --docker -m docker -v` e le prove LM Studio del back-end e del browser. Annotare gli esiti.
- [ ] **Passo 2: prova a mano** con il `.env` dell'utente.
  - Avvio dei quattro pezzi come nella specifica, poi in Edge `http://127.0.0.1:8780` e «Installa app».
  - Va verificato che:
    - la finestra non abbia la barra degli indirizzi;
    - ci sia l'icona nella barra delle applicazioni;
    - i temi chiaro e scuro funzionino, anche passando a quello di Windows;
    - una conversazione con LM Studio vada fino in fondo;
    - fermando il back-end compaia la striscia.
  - L'installazione la fa l'utente o il browser integrato, se lo permette: dirlo nel report.
- [ ] **Passo 3:** le eventuali correzioni vanno in commit `fix(...)` separati, ognuno con il suo test.

### Task 11: documenti e checkpoint

- [ ] **Passo 1: README.** Avvio dei quattro pezzi, installazione e disinstallazione dell'app, sviluppo con `npm run dev`, test (`npm test`, Playwright, `python -m playwright install chromium`), diagnosi (striscia rossa, porta 8780 occupata, immagine da ricostruire dopo una modifica).
- [ ] **Passo 2: `../CLAUDE.md`.** Struttura di `frontend/`, comandi npm e Docker del front-end, `FRONTEND_PORTA`, Playwright nelle prove.
- [ ] **Passo 3: `docs/studio`.**
  - Nuovo `15-chat-nel-browser.md`, con scheda e scaletta. Argomenti:
    - PWA e perché non un'app nativa;
    - Svelte 5 e rune;
    - lettura SSE incrementale;
    - markdown sicuro;
    - nginx che inoltra `/api` (stessa origine, niente CORS, niente buffering);
    - errori;
    - temi;
    - prove Playwright.
  - Aggiornare 00 (step 8 fatto e mappa), 08 (servizio `frontend`), 09 (Vitest e Playwright) e 14 (il front-end come cliente).
- [ ] **Passo 4: checkpoint** `docs/superpowers/checkpoint/2026-11-11-frontend.md` e righe in `docs/superpowers/README.md`.
- [ ] **Passo 5: commit** `docs(frontend): README, CLAUDE.md, capitolo 15 di studio e checkpoint dello step 8`
- [ ] **Passo 6:** chiedere all'utente l'approvazione esplicita per unire `dev-frontend` in `main`.
