# Avvio rapido e materiale di studio visuale — piano

> **Per chi esegue:** SOTTO-SKILL RICHIESTA: usare superpowers:subagent-driven-development (consigliata) oppure superpowers:executing-plans per eseguire il piano un task alla volta. I passi usano le caselle (`- [ ]`).

**Obiettivo:** una guida di avvio di una pagina, quattro presentazioni HTML e un atlante di schemi per studiare il progetto.

**Architettura:** la guida è un file Markdown alla radice del progetto. Le presentazioni sono pagine HTML statiche in `docs/studio/presentazioni/`, con tre file comuni: `stile.css` (aspetto), `slide.js` (navigazione), `schemi.js` (schemi SVG descritti una volta e disegnati nel browser). Nessuna libreria, nessuna richiesta di rete.

**Tecnologie:** Markdown, HTML, CSS, JavaScript senza dipendenze, SVG. Verifica con Chromium di Playwright, già in `requirements-dev.txt`.

**Specifica:** `docs/superpowers/specs/2026-11-15-avvio-rapido-materiale-studio-design.md`

## Vincoli globali

- Lavorare solo su `dev-docs-avvio-studio`. Nessun merge in `main` e nessun push senza richiesta.
- Nessuna modifica a codice dell'applicazione, test, `compose.yaml`, `requirements*.txt`, `frontend/`.
- Nessuna dipendenza nuova. Nessun `http://` o `https://` in `src`, `href` di risorse, `@import`, `fetch`.
- Ogni numero e ogni nome viene dalle «Schede in 5 minuti» dei capitoli o dal codice attuale. I riferimenti `file:riga` si scrivono solo dopo `grep -n`.
- La guida riporta solo comandi presenti nel README. Si dichiara quali sono stati rieseguiti.
- Testo in italiano, lessico dei capitoli (strumento, giro, turno, variante, origine, esito).
- Commit: Conventional Commits in italiano, staging selettivo, nessuna riga `Co-Authored-By`.
- I file si salvano in UTF-8 senza BOM.

## Punti da controllare

1. **Pagina aperta con doppio clic (`file://`).** Deve funzionare senza server: niente `fetch`, niente moduli ES. Verifica: ogni pagina caricata da `file://` senza errori in console.
2. **Finestra piccola o proiettore 4:3.** La slide si ridimensiona intera, senza barre di scorrimento. Verifica: istantanee a 1280×720 e a 1024×768.
3. **Testo che esce dalla slide.** Verifica: per ogni slide `scrollHeight <= clientHeight` e nessun elemento oltre i bordi.
4. **Tema scuro.** Testo e frecce degli schemi leggibili in tutti e due i temi. Verifica: istantanee con `color_scheme="dark"`.
5. **Stampa.** `Ctrl+P` produce una slide per pagina, con gli schemi. Verifica: `page.pdf()` e numero di pagine uguale al numero di slide.

---

### Task 1: La guida `AVVIO-RAPIDO.md`

**File:**
- Crea: `AVVIO-RAPIDO.md`
- Modifica: `README.md` (una riga dopo il primo paragrafo, con il collegamento alla guida)

**Contenuto, nell'ordine:**

1. «Scegli come usarlo»: tabella con tre righe (chat da terminale · chat nel browser · terminale in Docker), che cosa serve acceso, quanti comandi.
2. «La prima volta»: ambiente virtuale, `pip install -r requirements-dev.txt`, `Copy-Item .env.example .env`, password di PostgreSQL, identificativo del modello con `(Invoke-RestMethod http://localhost:1234/v1/models).data.id`.
3. «A · Chat da terminale»: `python -m assistente`, la riga di benvenuto attesa, come uscire.
4. «B · Chat nel browser»: i quattro comandi nell'ordine del README, un terminale per ciascun programma che resta in primo piano, l'indirizzo `http://127.0.0.1:8780`, come si controlla ogni pezzo (`/salute`), come si ferma.
5. «C · Terminale in Docker»: `docker compose build`, `.\avvia.ps1`.
6. «Se qualcosa non parte»: i sei errori più frequenti, ognuno con la frase esatta del README e il rimedio; rimando alla sezione «Diagnosi» del README.
7. «Dove andare dopo»: collegamenti a `docs/studio/00-indice.md` e a `docs/studio/presentazioni/index.html`.

- [ ] **Passo 1:** scrivere la guida, copiando comandi e messaggi dal README.
- [ ] **Passo 2:** eseguire i comandi verificabili e annotare l'esito: `"esci" | python -m assistente`; `python -m servizio_agente` e `python -m servizio_backend` avviati e interrogati su `/salute`; `http://127.0.0.1:8780/api/salute` attraverso nginx. Fermare i processi avviati.
- [ ] **Passo 3:** in fondo alla guida, la riga «Verificato il 15 novembre 2026» con l'elenco di che cosa è stato rieseguito e che cosa no.
- [ ] **Passo 4:** aggiungere il collegamento nel README.
- [ ] **Passo 5:** commit `docs: guida di avvio rapido in una pagina`.

---

### Task 2: La base delle presentazioni

**File:**
- Crea: `docs/studio/presentazioni/stile.css`, `slide.js`, `index.html`

**Interfacce prodotte (le usano i task 3–7):**

Scheletro di una presentazione:

```html
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lezione 4 · Assistente del laboratorio</title>
  <link rel="stylesheet" href="stile.css">
</head>
<body class="mazzo">
  <section class="slide titolo"> … </section>
  <section class="slide"> <p class="occhiello">…</p> <h2>…</h2> … <aside class="note">…</aside> <p class="fonte">Capitolo 04 · sezione 3</p> </section>
  <script src="schemi.js"></script>
  <script src="slide.js"></script>
</body>
</html>
```

Classi di contenuto: `punti` (elenco), `colonne` (due colonne), `schede` con figli `scheda` (riquadri affiancati), `tabella`, `codice` (blocco `<pre>`), `numero` (cifra grande con didascalia), `domanda` (domanda d'orale con risposta), `figure.schema[data-schema="nome"]`.

Comportamento di `slide.js`:

| Azione | Tasti |
|---|---|
| avanti / indietro | `→` `Spazio` `PagGiù` / `←` `PagSu`, e i due pulsanti a schermo |
| prima / ultima | `Home` / `Fine` |
| note «Da dire a voce» | `N` |
| tutte le slide in elenco | `E` |
| schermo intero | `F` |
| tema chiaro / scuro | `T` |

La slide corrente sta nell'indirizzo (`#7`). Barra di avanzamento e contatore «7 / 15». Dimensione logica 1280×720, ridimensionata con `transform: scale()`. In stampa: una slide per pagina, note nascoste.

- [ ] **Passo 1:** scrivere lo script di verifica `verifica_presentazioni.py` (fuori dal repository): per ogni pagina `.html` della cartella, caricata da `file://`, controlla zero errori in console, zero richieste non `file://`, per ogni slide nessun contenuto oltre i bordi, una `aside.note` per slide di contenuto, un `<svg>` dentro ogni `figure[data-schema]`; salva un'istantanea per slide in tema chiaro e scuro.
- [ ] **Passo 2:** eseguirlo su una cartella vuota: deve fallire con «nessuna pagina trovata».
- [ ] **Passo 3:** scrivere `stile.css`, `slide.js` e una pagina di prova con tre slide.
- [ ] **Passo 4:** eseguire la verifica e guardare le istantanee nei due temi e nei due formati.
- [ ] **Passo 5:** scrivere `index.html`: quattro presentazioni, atlante, tabella dei tasti, collegamento a `../00-indice.md`.
- [ ] **Passo 6:** commit `docs(studio): base delle presentazioni HTML`.

---

### Task 3: Gli schemi e l'atlante

**File:**
- Crea: `docs/studio/presentazioni/schemi.js`, `atlante.html`

**Interfacce prodotte:** `window.SCHEMI` (dizionario nome → descrizione) e `disegnaSchemi(radice)`, chiamata da sola al caricamento. Due tipi di descrizione: `flusso` (nodi su una griglia, frecce con etichetta, gruppi) e `sequenza` (attori in colonna, messaggi numerati dall'alto in basso).

**Schemi, con la fonte da cui copiare nodi ed etichette:**

| Nome | Che cosa mostra | Fonte |
|---|---|---|
| `sistema` | tutto il sistema oggi: browser, nginx, back-end, agente, CLI, LM Studio, server MCP, PostgreSQL, Open-Meteo | capitolo 02 §1.5 ter |
| `terminale` | assistente, server MCP, servizio FastAPI, LM Studio, risorse, archivio, log | capitolo 02 §1.2 |
| `grafo-base` | i tre nodi della lezione 4 | `assistente/grafo.py` |
| `grafo` | i cinque nodi con le due decisioni | `assistente/grafo.py`, capitolo 04 |
| `tool-calling` | sequenza: il modello chiede, il programma esegue, `ToolMessage` con lo stesso id | capitolo 01 §4–5 |
| `viaggio-mcp` | sequenza di «che ore sono a Tokyo?» fino al server MCP e ritorno | capitolo 03 §2 |
| `varianti` | tre strade verso `logica/` | capitolo 06 |
| `n-per-m` | 3 app × 10 servizi = 30 collegamenti contro 13 | capitolo 01 §8 |
| `processi` | chi avvia chi, con le porte | capitolo 02 §2.1 e §3 |
| `avvio` | l'ordine dei controlli all'avvio | capitolo 08, scheda |
| `turno-chat` | sequenza del turno in streaming: browser, nginx, back-end, agente, PostgreSQL | capitolo 14 §3–6 |
| `tabelle` | `progetti`, `chat`, `messaggi` con le chiavi | `servizio_backend/schema.sql` |
| `log` | quale processo scrive quale file | capitolo 10, scheda |
| `diagnosi` | i livelli, dal basso | README «Diagnosi», capitolo 10 §6 |
| `test` | test automatici e prove reali, che cosa prova ciascuno | capitolo 09, scheda |
| `dati` | dove vive ogni dato: memoria, SQLite, PostgreSQL, file di log | capitolo 00, «Persistenza» |
| `lezioni` | linea del tempo dal 2 al 12 novembre | capitolo 11, scheda |

- [ ] **Passo 1:** scrivere `schemi.js` con i due disegnatori e lo schema `grafo`; pagina `atlante.html` con quel solo schema; verifica e istantanea nei due temi.
- [ ] **Passo 2:** aggiungere gli altri schemi, a gruppi di quattro, con verifica a ogni gruppo.
- [ ] **Passo 3:** completare `atlante.html`: per ogni schema un titolo, la figura, una didascalia di una o due frasi e il capitolo dove approfondire; indice in cima.
- [ ] **Passo 4:** confrontare nodi, etichette e valori di ogni schema con la fonte indicata.
- [ ] **Passo 5:** commit `docs(studio): atlante degli schemi del progetto`.

---

### Task 4: «Tutto il progetto in 15 minuti»

**File:** crea `docs/studio/presentazioni/progetto-in-15-minuti.html`

Circa 15 slide: che cos'è · la mappa (`sistema`) · il modello locale · tool calling (`tool-calling`) · il grafo (`grafo`) · MCP e i dieci strumenti · le tre varianti (`varianti`) · il router e l'ambito · l'agente come servizio · il back-end e il turno (`turno-chat`) · la chat nel browser · i test (`test`) · log e diagnosi (`diagnosi`) · limiti noti e che cosa manca · che cosa ricordare.

- [ ] **Passo 1:** scrivere le slide dalle schede dei capitoli 00–15.
- [ ] **Passo 2:** verifica e istantanee; correggere le slide troppo piene.
- [ ] **Passo 3:** confronto dei fatti con le schede e con il codice.
- [ ] **Passo 4:** commit `docs(studio): presentazione del progetto in 15 minuti`.

---

### Task 5: «Lezione 4 · L'assistente di base»

**File:** crea `docs/studio/presentazioni/lezione-4.html`

Fonti: capitolo 01 slide 1–6, capitolo 04 slide 1–10, capitolo 08 slide 1–9, capitolo 09 slide 1–6, capitolo 11 slide 3. Schemi: `grafo-base`, `tool-calling`, `avvio`, `test`. Circa 14 slide.

- [ ] **Passo 1:** scrivere le slide unendo le scalette e togliendo le ripetizioni.
- [ ] **Passo 2:** verifica e istantanee.
- [ ] **Passo 3:** confronto dei fatti.
- [ ] **Passo 4:** commit `docs(studio): presentazione della lezione 4`.

---

### Task 6: «Lezione 5 · Gli strumenti via MCP»

**File:** crea `docs/studio/presentazioni/lezione-5.html`

Fonti: capitolo 01 slide 7–9, capitolo 02 slide 1–9, capitolo 03, capitolo 05, capitolo 06, capitolo 07, capitolo 10. Schemi: `n-per-m`, `terminale`, `processi`, `viaggio-mcp`, `varianti`, `log`, `diagnosi`. Circa 18 slide.

- [ ] **Passi 1–4** come nel task 5; commit `docs(studio): presentazione della lezione 5`.

---

### Task 7: «Lezione 6 · Evolvere l'agente»

**File:** crea `docs/studio/presentazioni/lezione-6.html`

Fonti: capitolo 00 (tabella dei nove step), capitolo 04 slide 11–13, capitoli 13, 14, 15, capitolo 08 slide 10 bis–quater, capitolo 11 slide 9 bis–ter. Schemi: `grafo`, `sistema`, `turno-chat`, `tabelle`, `dati`, `lezioni`. Circa 18 slide. La slide degli step dichiara che cosa è fatto (1, 6, 7, 8) e che cosa manca (2–5, 9).

- [ ] **Passi 1–4** come nel task 5; commit `docs(studio): presentazione della lezione 6`.

---

### Task 8: Collegamenti e chiusura

**File:**
- Modifica: `docs/studio/00-indice.md` (la sezione «Come preparare una presentazione» diventa «Presentazioni e schemi pronti», con i collegamenti; riga nuova in «Le altre fonti»)
- Modifica: `../CLAUDE.md` (in «Struttura e comandi»: `AVVIO-RAPIDO.md` e `docs/studio/presentazioni/`, con la regola di aggiornarle quando cambiano i capitoli)
- Modifica: `docs/superpowers/README.md` (riga per specifica, piano e checkpoint)
- Crea: `docs/superpowers/checkpoint/2026-11-15-docs-avvio-studio.md`

- [ ] **Passo 1:** verifica completa di tutte le pagine nei due temi e nei due formati; stampa in PDF di una presentazione.
- [ ] **Passo 2:** controllo di tutti i collegamenti relativi (ogni `href` porta a un file che esiste).
- [ ] **Passo 3:** `python -m pytest -q`: stesso esito di prima (il codice non è cambiato).
- [ ] **Passo 4:** aggiornare indice, `CLAUDE.md`, indice di `docs/superpowers/`.
- [ ] **Passo 5:** scrivere il checkpoint (Fatto, Da fare, Stato attuale) e fare il commit `docs: collegamenti al materiale visuale e checkpoint`.
