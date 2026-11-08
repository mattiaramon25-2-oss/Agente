# Passo 7 — Docker completo e documentazione finale — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** l'immagine Docker contiene tutti i pacchetti e i dati, e il container gestisce le due varianti, `fastapi` compresa. Log e note restano sull'host, e README e `CLAUDE.md` descrivono il progetto finito.

**Architecture:** un solo container con l'agente, il server MCP e, se serve, il servizio FastAPI, come nella sezione 9 della specifica. I volumi montano `./logs` e `./archivio`. `avvia.ps1` resta invariato: la prova della variante FastAPI passa le variabili con `docker compose run -e`.

**Tech Stack:** Docker Compose; il resto come nel passo 1.

**Spec:** `docs/superpowers/specs/2026-11-08-strumenti-lezione-5-design.md`, sezioni 9, 13 (Docker) e 14.

**Branch:** `dev-docker-docs`, creato da `dev`. Se il passo 6 non è ancora unito, il branch parte da `dev-meteo`.

## Global Constraints

Valgono quelli del passo 1. In più:

- **`Dockerfile`:** copia `assistente/`, `logica/`, `server_mcp/`, `servizio_api/` e `risorse/`, e nient'altro di nuovo.
- **`compose.yaml`:** volumi `./logs:/app/logs` e `./archivio:/app/archivio`. Nessuna porta pubblicata.
- **`.dockerignore`:** contiene `logs`, `archivio`, `tests`, `docs`, `.env` e `.venv`.
- **README e `CLAUDE.md`:** riportano solo comandi eseguiti con successo in questo passo o nei precedenti.

## Review Focus

1. **Container senza Internet:** il meteo deve rispondere con un errore di servizio non disponibile, mentre gli altri strumenti continuano a funzionare. Lo verifica il Task 1 (osservazione riportata nel checkpoint, se la rete del container viene a mancare).
2. **Prima esecuzione senza `logs/` e `archivio/` sull'host:** Compose crea le cartelle e l'assistente parte. Lo verifica il Task 1 (`test_varianti_in_docker`, eseguito dopo aver tolto le due cartelle).
3. **Processi orfani nel container all'uscita:** con `--rm` il container termina, e il codice di uscita 0 e la riga di arresto nei log lo dimostrano. Lo verifica il Task 1.
4. **Note scritte nel container visibili sull'host e al riavvio successivo.** Lo verifica il Task 1.
5. **Comandi del README non eseguiti:** si confronta ogni comando con i resoconti dei passi. Lo verifica il Task 2.

---

### Task 0: branch

- [ ] **Step 1:** `git switch -c dev-docker-docs`, partendo dal branch indicato nell'intestazione.

---

### Task 1: Docker completo e prova reale

**Files:**
- Modify: `Dockerfile`, `compose.yaml`, `.dockerignore`, `tests/test_reale_docker.py`

- [ ] **Step 1: aggiornare i tre file** secondo i Global Constraints.
- [ ] **Step 2: scrivere `test_varianti_in_docker`** in `tests/test_reale_docker.py`.
  - Prima di eseguire, rinominare temporaneamente `logs/` e `archivio/` se esistono, e ripristinarle in un `finally`. Così si prova la prima esecuzione senza toccare i dati dell'utente.
  - Comando: `docker compose run --rm -T -e FUSO_HOST_WINDOWS=<fuso> -e VARIANTE_SCADENZE=fastapi -e API_PORTA=8766 -e VARIANTE_CALCOLATRICE=locale assistente`.
  - Ingresso, una riga per volta:
    1. `Se parto il 23 dicembre 2026, quando scadono 3 giorni lavorativi?`
    2. `Che tempo fa a Udine?`
    3. `Ricordami di provare Docker`
    4. `esci`
  - **Controlli:**
    - codice 0;
    - nello stdout compaiono `calcola_scadenza (fastapi)`, `calcola (locale)`, `[calcola_scadenza · fastapi:` e `[get_weather · mcp:`;
    - sull'host `logs/servizio_api.log` contiene `endpoint=/scadenza` e `logs/server_mcp.log` contiene `tool=get_weather` e `operazione=aggiunta`;
    - `archivio/note.sqlite3` esiste.
  - **Seconda esecuzione** con l'ingresso `Quali note ho salvato?\nesci\n`: la risposta contiene `Docker`.
  - **Pulizia:** cancellare le cartelle create dal test e ripristinare quelle dell'utente.
- [ ] **Step 3:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 4:** `python -m pytest --docker -m docker -v -s`. Atteso: tutti PASS, compresi i test Docker dei passi precedenti.
- [ ] **Step 5:** commit `build(docker): includi tutti gli strumenti, il servizio FastAPI e i volumi di log e note`.

---

### Task 2: documentazione finale e checkpoint conclusivo

**Files:**
- Modify: `README.md`, `../CLAUDE.md`, `.env.example` (rilettura)
- Create: `docs/superpowers/checkpoint/AAAA-MM-GG-docker-docs.md`

- [ ] **Step 1: README, rilettura completa.**
  - **Struttura:** una sezione «Strumenti e varianti», con una tabella di dieci righe. Per ogni strumento: nome, variante possibile, dove gira e dove guardare nei log.
  - **Confronto delle varianti:** stessa domanda, `.env` cambiato, riavvio, e dove si vede la differenza.
  - **Diagnosi per livelli,** che unisce le tabelle dei passi precedenti:
    - server MCP;
    - servizio FastAPI;
    - rete del meteo;
    - archivio delle note;
    - modello.
  - **Verifica dei comandi:** ogni comando del README viene confrontato con i resoconti e i checkpoint dei passi 1–7, e si tolgono quelli non eseguiti.
- [ ] **Step 2: `../CLAUDE.md`.**
  - **Struttura e comandi:**
    - i pacchetti `logica/`, `server_mcp/`, `servizio_api/` e `risorse/`;
    - le cartelle `archivio/` e `logs/`;
    - i comandi di avvio del solo server e del solo servizio.
  - **Obiettivo:** gli strumenti della lezione 5, con le tre varianti.
  - **Scelte tecniche:** codice sincrono tranne il ponte MCP; la logica degli strumenti è scritta una sola volta e riusata dalle varianti.
- [ ] **Step 3: checkpoint conclusivo,** con tre sezioni:
  - **Fatto:** tutti i passi, con i branch e il loro stato di merge;
  - **Da fare:** ciò che non è verificato e le estensioni facoltative escluse dalla specifica;
  - **Stato attuale:** gli esiti delle ultime esecuzioni automatiche, LM Studio e Docker.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `docs: documentazione finale degli strumenti della lezione 5 e checkpoint conclusivo`.
- [ ] **Step 6:** **chiedere all'utente l'approvazione esplicita** per unire `dev-docker-docs` in `main`.
