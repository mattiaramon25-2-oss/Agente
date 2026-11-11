# Lezione 6, step 8 — La chat nel browser, installabile come app

Data: 2026-11-11 · Branch: `dev-frontend` (da `dev`, che contiene il back-end delle chat dello step 7)

## Obiettivo (slide)

Interfaccia di chat nel browser. Evidenza: **conversazione completa dal browser, errori mostrati**.

La chat parla **solo** con il back-end dello step 7 (`servizio_backend`), mai direttamente con l'agente.

## Che cosa vuole l'utente (decisioni dell'utente)

- **Simile a Claude, ma che sembri un'app e non una pagina web.** L'utente voleva all'inizio un'app installata non web; ha scelto, sapendo che altrimenti cambiavano `CLAUDE.md` e lo step 9, una **chat nel browser installabile come app** (PWA): finestra propria senza barra degli indirizzi né schede, icona nella barra delle applicazioni e nel menu Start, apertura con doppio clic. Così restano valide le slide, `CLAUDE.md` e i quattro container dello step 9.
- **Non in Python.** Interfaccia in **TypeScript**.
- **Disposizione «A»** (vista nelle bozze): una sola barra laterale a sinistra con «Nuova chat», ricerca, progetti e chat recenti; a destra il percorso (progetto › titolo), i messaggi e la casella per scrivere.
- **Stile zen**: molto spazio vuoto, niente icone superflue, poche linee, verde acqua solo per ciò che conta (pulsante principale, chat aperta, strumenti usati).
- **Angoli tra 8 e 12 px**, un po' spigolosi: niente forme a pillola.
- **Due temi, giorno e notte**:
  - chiaro «acqua e salvia»: fondo `#f6f8f6`, barra laterale `#eef3f0`, selezione `#d9ece7`, accento `#5fb3a6`, testo `#2f3e3c`;
  - scuro «acqua di notte»: fondo `#16211f`, barra laterale `#121b19`, selezione `#1f3a35`, accento `#4fb3a2`, testo `#dfe9e6`.
  
  (Valori delle bozze approvate; chi costruisce può ritoccarli per il contrasto, restando nella stessa famiglia.)
- Approvate dall'utente anche tutte le ipotesi di comportamento e le scelte tecniche delle sezioni seguenti.

## Non obiettivi

- Back-end, agente e database in container (step 9: qui va in container solo il front-end).
- Utenti, login, condivisione, uso da altri computer: tutto resta su `127.0.0.1`.
- Allegati, rinomina delle chat, modifica o rigenerazione di un messaggio, esportazione, voce.
- Funzionamento senza rete o senza back-end (il service worker serve all'installazione, non a lavorare offline).
- Cambiamenti alla CLI.

## Anti-obiettivi (un fallimento anche se funziona)

- Una pagina che sembra un sito: barra degli indirizzi, layout da pagina web, colori saturi o tante icone.
- Testo del modello inserito nella pagina come HTML non ripulito (rischio di script nella pagina).
- Errori silenziosi: un turno fallito che sparisce senza spiegazione, o il testo scritto dall'utente perso.
- Il back-end aperto alla rete per far funzionare il front-end.

---

## Com'è fatta la finestra

- **Barra laterale** (larghezza fissa, circa 240 px):
  - pulsante «Nuova chat» (accento);
  - casella «Cerca nelle chat»;
  - sezione «Progetti» con l'elenco e un «+» discreto per crearne uno;
  - sezione «Recenti» con le chat **fuori da ogni progetto**, dalla più recente;
  - in fondo, discreto, il selettore del tema (Automatico · Chiaro · Scuro).
- **Zona centrale**: in alto il percorso (`Progetto › titolo` oppure solo il titolo); poi i messaggi; in fondo la casella per scrivere (si allarga fino a qualche riga; `Invio` invia, `Maiusc+Invio` va a capo).
- **Messaggi**: quelli dell'utente a destra in un riquadro tenue; quelli dell'assistente a sinistra senza riquadro, con il testo formattato (markdown: grassetto, elenchi, codice, tabelle). Sopra la risposta, per ogni strumento usato, una riga piccola e discreta `nome · valori` (per esempio `calcola · (3+4)*2`), come la CLI.
- **Stato vuoto**: una chat nuova mostra al centro una frase breve di benvenuto e la casella.

## Come si comporta

- **Streaming.** Inviato un messaggio, la domanda compare subito; la risposta compare man mano che arrivano gli eventi `testo`; le righe degli strumenti compaiono all'evento `strumento`; all'evento `fine` il testo viene sostituito con `risposta` (il testo definitivo e salvato), il titolo della chat si aggiorna e la chat sale in cima ai recenti. Durante il turno la casella resta modificabile ma l'invio è disattivato.
- **Nuova chat.** «Nuova chat» apre una chat vuota senza crearla subito sul back-end: la chat si crea (`POST /chat`) al primo invio. Da dentro un progetto, «Nuova chat» crea la chat in quel progetto.
- **Progetti.** Cliccando un progetto la zona centrale mostra: nome (modificabile), istruzioni in un riquadro modificabile con «Salva», pulsante «Nuova chat in questo progetto» e l'elenco delle sue chat. Le chat dei progetti non compaiono tra i «Recenti».
- **Ricerca.** Scrivendo almeno 2 caratteri nella casella di ricerca (con una breve attesa dopo l'ultimo tasto), la barra laterale mostra al posto degli elenchi i risultati: titolo della chat, ruolo e l'estratto con la parola evidenziata. Cliccando si apre la chat. Svuotando la casella tornano gli elenchi.
- **Cancellazione.** Accanto al nome di chat e progetti, al passaggio del mouse, un menu «…» con «Elimina» (per le chat anche «Sposta in progetto…»). Prima di eliminare compare una conferma; per un progetto la conferma dice che verranno eliminate anche le sue chat. Il `409` del back-end (turno in corso) si mostra come errore.
- **Errori (evidenza dello step).** Gli errori si vedono sempre, in italiano, in un riquadro tenue con l'accento d'errore (un rosso-terracotta smorzato in tema con la palette):
  - durante un turno (`503` prima del flusso, evento `errore`, connessione caduta): il riquadro compare sotto la domanda, la domanda non risulta salvata e **il testo torna nella casella**, pronto da reinviare;
  - back-end non raggiungibile: una striscia discreta in cima alla finestra («Il back-end non risponde: avvialo con `python -m servizio_backend`»), che sparisce da sola quando torna;
  - altri errori delle azioni (creare, salvare istruzioni, eliminare, cercare): il messaggio `errore` del back-end in un avviso che si chiude da solo.
  - Il testo mostrato è il campo `errore` restituito dal back-end quando c'è; altrimenti un messaggio generico in italiano.
- **Tema.** «Automatico» segue il tema di Windows (`prefers-color-scheme`); la scelta si ricorda nel browser (`localStorage`).

## Tecnologia (approvata dall'utente)

- **TypeScript con Svelte 5**, compilato con **Vite**. Versioni fissate esatte in `package.json` (niente `^`) con `package-lock.json` versionato. Node 24 sul computer per compilare.
- **`marked`** per il markdown e **`DOMPurify`** per ripulire l'HTML prima di inserirlo.
- **Nessun'altra libreria di interfaccia** (niente framework CSS né librerie di componenti): lo stile è CSS scritto a mano con variabili per i due temi.
- **PWA**: `manifest.webmanifest` (nome «Assistente del laboratorio», nome breve «Assistente», `display: standalone`, `theme_color`/`background_color` del tema chiaro, icone PNG 192 e 512 più una SVG, con un simbolo semplice in verde acqua) e un **service worker scritto a mano**, minimo, che rende l'app installabile in Edge e Chrome. Non deve mettere in cache le chiamate `/api/`.
- **Nessuna dipendenza nuova per il back-end.**

## Dove sta e come si avvia

- Nuova cartella **`frontend/`** dentro `assistente-laboratorio/` (`package.json`, `src/`, `public/`, `nginx/`, `Dockerfile`).
- **In Docker**: nuovo servizio Compose **`frontend`**, immagine a due fasi (`node:24.21.0-alpine` per compilare, `nginxinc/nginx-unprivileged:1.30.6-alpine` per servire, entrambe già presenti sul computer). nginx:
  - serve i file compilati;
  - inoltra `/api/...` al back-end sull'host: `http://host.docker.internal:${BACKEND_PORTA}/...` (togliendo `/api`), con il buffering disattivato per lo streaming e un tempo di lettura lungo (almeno 300 s). Verificato il 2026-11-11: da un container `host.docker.internal` raggiunge un servizio dell'host in ascolto su `127.0.0.1`, quindi il back-end resta solo su `127.0.0.1`;
  - porta pubblicata **solo** su `127.0.0.1:${FRONTEND_PORTA:-8780}`;
  - `sw.js` e `index.html` senza cache, gli altri file con cache lunga.
- Browser e back-end hanno così la **stessa origine**: nessuna configurazione CORS sul back-end.
- **Nuova variabile** `FRONTEND_PORTA` (facoltativa, predefinita 8780) in `.env.example`; in `compose.yaml` le variabili del servizio `frontend` sono scritte **senza** `:?`, per non bloccare `.\avvia.ps1`, `.\avvia-agente.ps1` e le prove esistenti.
- **Avvio dello step** (PowerShell, da `assistente-laboratorio/`):

  ```powershell
  docker compose up -d database
  python -m servizio_agente
  python -m servizio_backend
  docker compose up -d --build frontend
  ```

  poi `http://127.0.0.1:8780` in Edge o Chrome e «Installa app». Il README spiega l'installazione e la disinstallazione.
- **Sviluppo**: `npm run dev` (Vite) con lo stesso inoltro di `/api` verso il back-end.

## Test e evidenza

- **Automatici, in TypeScript con Vitest** (`npm test` in `frontend/`, senza back-end): lettura del flusso SSE (eventi spezzati a metà tra due pezzi, accenti, U+2028), gestione degli eventi del turno (testo, strumento, fine, errore, flusso interrotto senza `fine`), client dell'API con errori `{"errore"}` e risposte non JSON, ripulitura del markdown (uno `<script>` o un `onerror` nel testo del modello non arriva nella pagina), scelta del tema.
- **La suite Python non cambia** (`python -m pytest` resta verde); un test Python controlla che `compose.yaml` pubblichi `frontend` solo su `127.0.0.1` e che `docker compose config` funzioni senza `FRONTEND_PORTA`.
- **Prove nel browser con Playwright** (pacchetto Python `playwright`, versione fissata in `requirements-dev.txt`, browser Chromium scaricato con `python -m playwright install chromium`), attivate a parte come le altre prove reali:
  - con `--docker` (agente finto via HTTP, back-end vero, database di prova, container `frontend`): conversazione completa (nuova chat, streaming visibile, riga dello strumento, risposta formattata, titolo aggiornato, chat ancora presente dopo il ricaricamento della pagina); progetto con istruzioni; ricerca; eliminazione con conferma; **errori mostrati**: agente spento (riquadro d'errore e testo tornato nella casella) e back-end spento (striscia in cima);
  - con `--lmstudio --docker`: una conversazione vera con il modello (una domanda con `calcola`) dal browser;
  - il manifest è valido e il service worker si registra (requisiti dell'installazione).
- **Prova a mano**: installazione come app in Edge, finestra senza barra degli indirizzi, temi chiaro e scuro, riportata nel checkpoint.

## Documentazione

README (avvio, installazione, sviluppo, test, diagnosi), `CLAUDE.md` (struttura `frontend/`, comandi `npm`, `FRONTEND_PORTA`, servizio `frontend`), `docs/studio`: nuovo capitolo `15-chat-nel-browser.md` (scheda in 5 minuti e scaletta per le slide) e aggiornamenti di 00, 08, 09, 14; checkpoint `docs/superpowers/checkpoint/2026-11-11-frontend.md`.

## Scelte di Claude (dalla revisione della specifica)

- **Primo invio fallito.** Se il primo messaggio di una chat nuova fallisce dopo il `POST /chat`, la chat (vuota, «Nuova chat») resta creata e il nuovo invio usa la stessa chat: non se ne crea una seconda.
- **Back-end spento.** Si riconosce da un errore di rete o da una risposta `502`/`504` di nginx (corpo HTML, non `{"errore"}`). Mentre la striscia è visibile, il front-end interroga `/api/salute` ogni 5 secondi e la toglie appena risponde.
- **Configurazione di nginx.** È un modello in `/etc/nginx/templates/` che l'immagine nginx completa all'avvio con le variabili d'ambiente (`BACKEND_PORTA`). Così le prove possono puntare a un back-end di prova su un'altra porta senza ricompilare l'immagine.

## Lasciato a chi costruisce

- La divisione in componenti Svelte e in moduli TypeScript.
- Come disegnare le icone PNG dell'app (generate una volta e versionate).
- I dettagli di spaziatura, tipografia (font di sistema) e animazioni, dentro lo stile zen descritto.
- Le versioni esatte delle librerie npm e di `playwright`, da fissare nel piano.
