# Avvio rapido e materiale di studio visuale — specifica breve

Data: 15 novembre 2026. Branch: `dev-docs-avvio-studio`, da `dev`.

## Intento

L'utente vuole due cose:

1. avviare il progetto in modo semplice, senza cercare i comandi in un README di 732 righe;
2. studiare tutto il progetto con materiale visivo: presentazioni e schemi grafici.

Oggi `docs/studio/` ha 16 capitoli (circa 16.000 righe). Ogni capitolo ha una «Scaletta per le slide», che è solo testo: nessuna presentazione esiste davvero. I 79 diagrammi sono blocchi Mermaid, visibili solo con un programma che li disegna.

## Obiettivi

- Una guida di avvio di una pagina, con i soli comandi già verificati nel README.
- Quattro presentazioni che si aprono con doppio clic e funzionano senza Internet.
- Un atlante con gli schemi principali del progetto, disegnati davvero.
- Ogni numero e ogni nome viene dai capitoli di studio o dal codice attuale.

## Non obiettivi

- Nessuna modifica al codice dell'applicazione, ai test o a `compose.yaml`.
- Nessun comando unico di avvio: è lo step 9 della lezione 6 e richiede specifica e piano propri.
- Nessuna riscrittura dei 16 capitoli: restano la fonte dei dettagli.
- Nessun file PowerPoint.

## Anti-obiettivi

- Una guida che riporta comandi mai eseguiti.
- Slide con fatti diversi da quelli dei capitoli.
- Pagine che caricano qualcosa da Internet: devono funzionare offline.
- Nuove dipendenze npm o Python.

## Approcci considerati

| Scelta | Opzioni | Scelta dell'utente |
|---|---|---|
| Formato | pagine HTML · PowerPoint `.pptx` · entrambi | **pagine HTML**: si aprono nel browser, stanno in Git, niente file binari |
| Quante presentazioni | una per lezione più il riassunto · una per capitolo (15) · solo il riassunto | **una per lezione più il riassunto** (4) |
| Avvio semplice | solo la guida · guida più script unico | **solo la guida** |

## Che cosa si costruisce

| File | Contenuto |
|---|---|
| `AVVIO-RAPIDO.md` | tre percorsi: chat da terminale, chat nel browser, Docker. Per ognuno: che cosa serve acceso, comandi numerati, che cosa si deve vedere, come fermare, errori più comuni. Collegata dal README |
| `docs/studio/presentazioni/index.html` | pagina d'ingresso: le quattro presentazioni, l'atlante, i tasti |
| `docs/studio/presentazioni/progetto-in-15-minuti.html` | tutto il progetto, circa 15 slide |
| `docs/studio/presentazioni/lezione-4.html` | l'assistente di base |
| `docs/studio/presentazioni/lezione-5.html` | gli strumenti via MCP |
| `docs/studio/presentazioni/lezione-6.html` | router, servizio, back-end, chat nel browser |
| `docs/studio/presentazioni/atlante.html` | tutti gli schemi su una pagina, con didascalia e riferimento al capitolo |
| `docs/studio/presentazioni/stile.css`, `slide.js`, `schemi.js` | aspetto, navigazione delle slide, disegno degli schemi |

In più: una sezione nuova in `docs/studio/00-indice.md`, una riga nella struttura di `CLAUDE.md`, la riga nell'indice `docs/superpowers/README.md`, il checkpoint.

## Scelte di costruzione (decise da Claude, correggibili)

- **Tre file comuni** (`stile.css`, `slide.js`, `schemi.js`) invece di pagine autosufficienti: un solo punto da correggere. La cartella `presentazioni/` si copia intera.
- **Schemi disegnati in SVG da `schemi.js`**, senza librerie: ogni schema è descritto una volta sola (nodi, frecce, etichette) e compare sia nell'atlante sia nelle slide. Mermaid non si usa perché andrebbe scaricato da Internet o aggiunto come dipendenza.
- **Slide a dimensione fissa 1280×720**, ridimensionate alla finestra: l'impaginazione non cambia tra schermo e proiettore.
- **Note «Da dire a voce»** in ogni slide (tasto `N`): servono per ripassare l'orale.
- **Tema chiaro e scuro**, che segue il sistema, con un tasto per cambiarlo.
- **Stampa in PDF** dal browser: una slide per pagina.
- Testo in italiano, stesso lessico dei capitoli.

## Verifica

- Ogni pagina aperta con Chromium di Playwright (già in `requirements-dev.txt`) da `file://`: nessun errore in console, nessuna richiesta di rete, immagine di ogni slide controllata a vista in tema chiaro e scuro.
- Controllo che nessun testo esca dalla slide.
- Fatti delle slide confrontati con i capitoli e, per i valori chiave, con il codice (`grep -n`).
- Comandi di `AVVIO-RAPIDO.md` confrontati uno per uno con il README. Quelli che si possono eseguire senza LM Studio vengono eseguiti; gli altri sono dichiarati «dal README, non rieseguiti».
- `python -m pytest` resta verde: il codice non cambia.

## Lasciato a chi costruisce

Numero esatto di slide per presentazione, scelta degli schemi per slide, disposizione dei nodi.
