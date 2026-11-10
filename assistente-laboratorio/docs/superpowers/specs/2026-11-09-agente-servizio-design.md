# Lezione 6, step 6 — L'agente come servizio HTTP

Data: 2026-11-09 · Branch: `dev-grafica-gui` (da `dev`, che contiene router e streaming)

## Obiettivo (slide)

L'agente risponde anche via HTTP. Evidenza: **stessa risposta dalla CLI e dall'API**.

È il primo dei passi verso l'interfaccia grafica (step 7 back-end con PostgreSQL, step 8 front-end, step 9 quattro container). Gli step 2–5 (revisore, riassunto, resource, prompt) restano da fare: l'utente ha scelto di procedere con lo step 6.

## Che cosa si costruisce

Un nuovo pacchetto `servizio_agente/`, accanto a `servizio_api/`, con un'applicazione FastAPI (FastAPI e uvicorn sono già dipendenze fissate: nessuna dipendenza nuova).

- **Lo stesso agente della CLI.** Il servizio prepara strumenti, modello, router e ambito con le stesse funzioni di `python -m assistente` (`prepara_strumenti`, `crea_modello`, `crea_router`, `carica_ambito`, `crea_grafo`). Per non duplicare il codice, la costruzione del grafo passa in una funzione comune `crea_agente(config, strumenti)` in `assistente/agente.py`, usata da `__main__.py`, da `tests/reale.py` e dal servizio.
- **Senza stato.** Il servizio non conserva le conversazioni: la cronologia la tiene chi chiama, come oggi la tiene il terminale. Così lo step 7 (back-end con le chat in PostgreSQL) potrà salvarla senza cambiare l'agente. Nessuna sessione in memoria.

## API

| Metodo e percorso | Richiesta | Risposta |
|---|---|---|
| `GET /salute` | — | `200 {"stato": "ok", "modello": "...", "fuso": "...", "strumenti": {"nome": "origine", ...}}` |
| `POST /chat` | `{"messaggio": "testo", "cronologia": [...]}` (`cronologia` facoltativa, vuota se manca) | `200 {"risposta": "testo", "strumenti": [{"nome", "origine", "argomenti"}], "cronologia": [...]}` |

- `cronologia` è l'elenco dei messaggi LangChain serializzati con `messages_to_dict` (compresi richieste e risultati degli strumenti): il client la rimanda così com'è al turno dopo. È opaca per il client; `risposta` è il testo da mostrare.
- `strumenti` elenca le chiamate eseguite con successo nel turno, le stesse che la CLI stampa come `[nome · origine: ...]`.
- La risposta è intera, non in streaming (lo streaming via HTTP non è richiesto dallo step).
- Il fuso è quello rilevato all'avvio del servizio, come per la CLI.

## Errori (in italiano, sempre `{"errore": "..."}`)

- Corpo non valido (messaggio mancante o vuoto, cronologia non deserializzabile): `400`, anche per gli errori di validazione che FastAPI darebbe come `422` (come `servizio_api`).
- LM Studio non raggiungibile durante il turno (`openai.APIConnectionError`): `503`, con il messaggio dell'eccezione.
- Altri errori del turno: `500` con il messaggio; la cronologia del client non cambia, come nella CLI.

## Avvio e configurazione

- `python -m servizio_agente`: legge il `.env` come la CLI, controlla LM Studio (`verifica_server`), avvia il server MCP (e il servizio FastAPI delle scadenze se `VARIANTE_SCADENZE=fastapi`) e li spegne all'uscita.
- Nuova variabile `AGENTE_PORTA` (obbligatoria solo per il servizio, intero tra 1024 e 65535, diversa da `MCP_PORTA` e `API_PORTA`), aggiunta a `.env.example`. Ascolta solo su `127.0.0.1`.
- Un turno alla volta (`threading.Lock`): le richieste contemporanee aspettano. Basta per un laboratorio con un solo utente ed evita turni sovrapposti su LM Studio e sull'archivio delle note.
- Log: lo stesso `logs/assistente.log` (router, nodi, strumenti), più una riga per richiesta: `richiesta endpoint=/chat esito=ok|errore durata=...`.
- La CLI non cambia. Docker resta com'è: i container separati sono lo step 9.

## Evidenza e test

- **Automatici** (modello e router finti, `TestClient` di FastAPI): `/salute`; `/chat` restituisce **la stessa risposta e la stessa cronologia** di `esegui_turno` con le stesse risposte preparate; la cronologia restituita, rimandata, continua la conversazione; strumenti eseguiti nell'elenco; rifiuto del router via HTTP; errori `400`, `503`, `500` in italiano; il lock serializza i turni.
- **Prova reale** (`--lmstudio`): la stessa domanda alla CLI (`esegui_sessione` con ingresso simulato) e all'API (`/chat` su uvicorn reale):
  - «scrivimi una poesia sul mare»: rifiuto **identico** (è un testo fisso);
  - «Quanto fa (3+4)*2?»: in entrambe 14 e la chiamata a `calcola` nel log. Il testo del modello può cambiare tra due esecuzioni: si confrontano il risultato e lo strumento, non la frase.

## Fuori da questo step

Persistenza delle chat (step 7), front-end (step 8), container (step 9), streaming via HTTP, autenticazione.
