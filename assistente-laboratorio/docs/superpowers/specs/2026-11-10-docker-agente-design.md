# Il servizio dell'agente in Docker

Data: 2026-11-10 · Branch: `dev-docker-agente` (da `dev`, che contiene router, streaming e servizio HTTP)

## Obiettivo

Richiesta dell'utente: «dockerizza tutto e assicurati che funzioni tutto». Oggi in Docker gira solo la CLI (`python -m assistente`); il servizio HTTP dell'agente (`python -m servizio_agente`, step 6) non è nemmeno copiato nell'immagine.

## Decisione dell'utente

Un **secondo servizio Compose**, `agente`, dalla stessa immagine. Ogni container avvia e spegne il suo server MCP come oggi; la CLI in Docker resta com'è. Il server MCP in un container suo e i quattro container dello step 9 non fanno parte di questo lavoro.

## Che cosa cambia

- **`Dockerfile`**: copia anche `servizio_agente/`.
- **Indirizzo di ascolto.** Nel container il servizio deve ascoltare su `0.0.0.0`, altrimenti la porta pubblicata non lo raggiunge. Nuova variabile facoltativa `AGENTE_HOST` (predefinito `127.0.0.1`, deve essere un indirizzo IP valido), letta da `leggi_host_agente` in `assistente/configurazione.py`. Fuori da Docker non cambia nulla.
- **`compose.yaml`**, nuovo servizio `agente`:
  - `build: .`, `env_file: .env`, comando `python -m servizio_agente`;
  - stesse variabili del servizio `assistente` (indirizzo di LM Studio per Docker, porte, varianti), più `AGENTE_PORTA` obbligatoria, `AGENTE_HOST: 0.0.0.0` e `FUSO_HOST_WINDOWS` (vuoto se non passato);
  - porta pubblicata **solo** su `127.0.0.1` dell'host: `127.0.0.1:${AGENTE_PORTA}:${AGENTE_PORTA}`;
  - stessi volumi `logs/` e `archivio/`, stesso `extra_hosts`.
- **`avvia-agente.ps1`**: come `avvia.ps1`, passa il fuso di Windows e lancia `docker compose up --build agente`. `Ctrl+C` ferma il container; Docker manda `SIGTERM`, che il servizio già gestisce come arresto ordinato (server MCP spento).
- **`.env.example`**: commento su `AGENTE_HOST` (non serve impostarla: la mette Compose).

## Verifica («funziona tutto»)

- Test automatici: `python -m pytest`, con i nuovi test di `leggi_host_agente` e dell'avvio con `AGENTE_HOST`.
- Prove Docker esistenti, tutte (`python -m pytest --docker -m docker -v -s`), più una nuova per il servizio: `docker compose up -d agente`, attesa di `/salute` dall'host, una domanda a `/chat` con risposta e strumento, il fuso dell'host Windows, poi `docker compose stop agente` e controllo nei log dell'arresto ordinato (`arresto servizio agente`, server MCP spento). Come le altre prove Docker, sposta da parte `logs/` e `archivio/` dell'utente.
- Prove reali con LM Studio, tutte (`python -m pytest --lmstudio -m lmstudio -v -s`).
- Prova manuale con `avvia-agente.ps1` e `Invoke-RestMethod`.

## Fuori da questo lavoro

Server MCP in un container separato, back-end, front-end, database (step 7–9), pubblicazione della porta su interfacce diverse da `127.0.0.1`.
