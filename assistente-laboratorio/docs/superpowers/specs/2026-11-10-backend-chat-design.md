# Lezione 6, step 7 — Il back-end delle chat con PostgreSQL

Data: 2026-11-10 · Branch: `dev-backend` (da `dev`, che contiene router, streaming, servizio dell'agente e il suo container)

## Obiettivo (slide)

API per le chat, salvate in PostgreSQL. Evidenza: **le chat ci sono ancora dopo il riavvio**.

È il servizio che la chat nel browser (step 8) userà. Il browser non parla mai direttamente con l'agente: parla con il back-end, che salva tutto in PostgreSQL e chiama l'agente via HTTP. L'agente resta senza stato, come nello step 6: la cronologia gliela passa il back-end a ogni turno.

## Che cosa deve poter fare l'utente (richiesta dell'utente)

Dal browser dello step 8, attraverso questo back-end:

- **vedere** le chat in elenco e riaprirle con tutti i messaggi;
- **cancellarle**;
- **cercarle** per parole contenute nei messaggi;
- **creare progetti** che raggruppano le chat, ognuno con delle **istruzioni** facoltative che valgono per tutte le sue conversazioni;
- vedere la risposta del modello **in streaming**: il testo arriva nel browser man mano che il modello lo scrive, e nel database si salva solo il messaggio completo.

Decisioni dell'utente sulle proposte di Claude:

- un progetto **raggruppa soltanto** le chat (niente file comuni); può avere istruzioni proprie;
- tecnologia approvata: PostgreSQL in un container Docker con un volume; back-end FastAPI avviato con `python -m servizio_backend`; libreria `psycopg` 3 con SQL scritto a mano e tabelle create all'avvio, senza SQLAlchemy; streaming con Server-Sent Events; ricerca direttamente in PostgreSQL; in questo step solo il database va in un container.

Proposte di Claude non contestate dall'utente (da confermare leggendo questa specifica):

- il titolo di una chat sono le prime parole della prima domanda;
- la ricerca restituisce le chat che contengono la parola, indicando quale messaggio l'ha trovata;
- una chat può stare fuori da qualsiasi progetto e si può spostare da un progetto all'altro;
- cancellare un progetto cancella anche le sue chat.

## Non obiettivi

- Front-end (step 8), back-end e agente in container (step 9).
- Utenti, autenticazione, condivisione. Un solo utente; i servizi ascoltano solo su `127.0.0.1`.
- File allegati ai progetti, rinomina delle chat, modifica o rigenerazione di un messaggio, esportazione.
- Riassunto della cronologia (step 3): la cronologia passata all'agente cresce come nella CLI.
- Cambiamenti alla CLI: i progetti e le chat salvate esistono solo per il back-end.

## Anti-obiettivi (sarebbe un fallimento anche se funziona)

- Una risposta interrotta a metà salvata come se fosse completa, o una domanda salvata senza la sua risposta.
- Le istruzioni di un progetto che scavalcano le regole dell'agente: il router dell'ambito decide come prima e il rifiuto resta il testo fisso di `risorse/ambito.json`.
- Una password scritta nel codice, in `compose.yaml` o in `.env.example`.
- La porta di PostgreSQL o del back-end aperta su interfacce diverse da `127.0.0.1`.

---

## Architettura dello step

```
browser (step 8) ──HTTP/SSE──► servizio_backend (127.0.0.1:BACKEND_PORTA) ──HTTP/SSE──► servizio_agente (127.0.0.1:AGENTE_PORTA)
                                      │                                                     │
                                      ▼                                                     ▼
                         PostgreSQL in Docker (127.0.0.1:POSTGRES_PORTA)          LM Studio e server MCP, come oggi
```

- **`servizio_backend/`**, nuovo pacchetto accanto a `servizio_api/` e `servizio_agente/`: applicazione FastAPI (`app.py`), accesso al database (`archivio.py`, SQL scritto a mano), client dell'agente (`client_agente.py`), schema (`schema.sql`), avvio (`__main__.py`). Nessuna dipendenza da `assistente/` per il grafo: il back-end conosce l'agente solo attraverso HTTP. Può usare le funzioni comuni di configurazione e registro (`leggi_porta`, `configura_registro`, `formatta`).
- **`servizio_agente/`** riceve due aggiunte (sezione «Che cosa cambia nell'agente»).
- **PostgreSQL** è il servizio Compose `database`. Il back-end e l'agente in questo step girano fuori da Docker, con `python -m`.

## Dati in PostgreSQL

Tre tabelle, create all'avvio del back-end con `CREATE TABLE IF NOT EXISTS` da `servizio_backend/schema.sql`. Nessun sistema di migrazioni.

| Tabella | Colonne | Note |
|---|---|---|
| `progetti` | `id` (intero, identità), `nome` (testo, non vuoto), `istruzioni` (testo, vuoto se assenti), `creato`, `aggiornato` (`timestamptz`) | |
| `chat` | `id` (intero, identità), `progetto_id` (riferimento a `progetti`, nullo = fuori da ogni progetto, `ON DELETE CASCADE`), `titolo` (testo, nullo finché non c'è il primo messaggio), `cronologia` (`jsonb`, la cronologia dell'agente così come la restituisce), `creata`, `aggiornata` | |
| `messaggi` | `id` (intero, identità), `chat_id` (riferimento a `chat`, `ON DELETE CASCADE`), `ruolo` (`utente` o `assistente`), `testo`, `strumenti` (`jsonb`, solo per `assistente`: le chiamate riuscite, come il campo `strumenti` dell'agente), `creato` | quello che il browser mostra e che la ricerca legge |

- **Perché la cronologia e i messaggi sono separati.** La cronologia dell'agente contiene anche richieste e risultati degli strumenti in formato LangChain: serve per continuare la conversazione esattamente come nella CLI, ma non è adatta né da mostrare né da cercare. I messaggi sono il testo pulito di domanda e risposta.
- **Un turno si salva tutto insieme.** Alla fine di un turno riuscito, in una sola transazione: il messaggio `utente`, il messaggio `assistente`, la nuova `cronologia` della chat, `aggiornata`, e il `titolo` se era nullo. Se il turno non arriva alla fine non si salva nulla, nemmeno la domanda: è lo stesso comportamento della CLI, dove un turno fallito non entra nella cronologia.
- **Titolo.** Le prime parole della prima domanda, al massimo 60 caratteri, tagliate su uno spazio quando possibile e con «…» se accorciate. Finché è nullo, il back-end restituisce «Nuova chat».
- **Cancellazioni.** Cancellare una chat cancella i suoi messaggi; cancellare un progetto cancella le sue chat e i loro messaggi (a cascata nel database). Le note salvate dall'agente con `add_note` stanno nell'archivio SQLite delle note e **non** si cancellano con la chat.

## API del back-end

Errori sempre `{"errore": "..."}` in italiano, come gli altri servizi; gli errori di validazione che FastAPI darebbe come `422` diventano `400`. JSON con `charset=utf-8` dichiarato (come `servizio_agente`, per `Invoke-RestMethod` di PowerShell 5.1).

| Metodo e percorso | Richiesta | Risposta |
|---|---|---|
| `GET /salute` | — | `200 {"stato": "ok", "database": "ok", "agente": "ok" \| "non raggiungibile"}`; `503` se il database non risponde |
| `GET /progetti` | — | elenco `{id, nome, istruzioni, numero_chat, creato, aggiornato}`, per nome |
| `POST /progetti` | `{nome, istruzioni?}` | `201` con il progetto |
| `GET /progetti/{id}` | — | il progetto; `404` se non esiste |
| `PATCH /progetti/{id}` | `{nome?, istruzioni?}` | il progetto aggiornato |
| `DELETE /progetti/{id}` | — | `204`; cancella anche le sue chat |
| `GET /chat` | filtro facoltativo `?progetto=<id>` oppure `?progetto=nessuno` | elenco `{id, titolo, progetto_id, creata, aggiornata}`, dalla più recente (`aggiornata`) |
| `POST /chat` | `{progetto_id?}` | `201` con la chat vuota, titolo «Nuova chat» |
| `GET /chat/{id}` | — | la chat con i suoi `messaggi` in ordine (`id, ruolo, testo, strumenti, creato`); la `cronologia` interna non viene esposta |
| `PATCH /chat/{id}` | `{progetto_id}` (anche `null`) | la chat spostata; `404` se il progetto non esiste |
| `DELETE /chat/{id}` | — | `204` |
| `POST /chat/{id}/messaggi` | `{messaggio}` | flusso SSE, sezione seguente |
| `GET /ricerca` | `?q=testo` | elenco `{chat_id, titolo, progetto_id, messaggio_id, ruolo, estratto}` |

Limiti (scelta di Claude): `nome` di un progetto da 1 a 100 caratteri; `istruzioni` fino a 4000 caratteri; `messaggio` non vuoto; `q` almeno 2 caratteri.

### Un turno in streaming: `POST /chat/{id}/messaggi`

Prima di cominciare il flusso, il back-end controlla e risponde con JSON normale:

- chat inesistente: `404`; messaggio vuoto: `400`;
- un turno già in corso sulla stessa chat: `409` (un turno alla volta per chat);
- agente non raggiungibile, già occupato con un altro turno, o che rifiuta la richiesta prima di cominciare: `503` con il motivo (per l'agente occupato: «L'agente sta già rispondendo a un'altra chat: riprova tra poco.»).

Poi risponde `200` con `Content-Type: text/event-stream`. Gli eventi, ognuno con un `data` JSON:

| Evento | Dati | Quando |
|---|---|---|
| `testo` | `{"pezzo": "..."}` | ogni pezzo di testo del modello, appena arriva |
| `strumento` | `{"nome", "origine", "argomenti"}` | dopo ogni chiamata a uno strumento riuscita |
| `fine` | `{"risposta", "strumenti", "messaggio_utente_id", "messaggio_assistente_id", "titolo"}` | il turno è finito **ed è salvato** |
| `errore` | `{"errore": "..."}` | il turno si è interrotto; nulla è stato salvato |

- `risposta` in `fine` è il testo definitivo, quello salvato: il client sostituisce con questo il testo composto dai pezzi. Serve perché il rifiuto e il messaggio del limite non arrivano a pezzi, e perché il modello può scrivere qualcosa prima di chiamare uno strumento.
- Il back-end passa all'agente la `cronologia` salvata della chat e le `istruzioni` del suo progetto (se c'è).
- **Se il browser si scollega a metà**, il back-end continua a leggere il flusso dell'agente fino alla fine e salva il turno. Il turno ormai è stato eseguito, magari con effetti (una nota salvata): perderne la risposta lascerebbe la chat incoerente con quello che è successo. Se invece si interrompe l'agente, non si salva nulla.
- Tempi massimi verso l'agente (scelta di Claude): 5 s per collegarsi, 180 s di attesa tra un evento e l'altro (LM Studio ne ha 120). Poiché l'agente occupato risponde subito (sezione «Che cosa cambia nell'agente»), il flusso non resta mai fermo in coda dietro un altro turno.
- **Cancellare durante un turno** (scelta di Claude): `DELETE /chat/{id}` su una chat con un turno in corso, e `DELETE /progetti/{id}` su un progetto che ne contiene una, rispondono `409`. Così un turno che ha già avuto effetti trova sempre la sua chat quando deve salvarsi. Se invece il salvataggio fallisce (per esempio database spento), il client riceve `errore` e il turno non è salvato.

### Ricerca

- Cerca il testo `q` nei messaggi (domande e risposte) senza distinguere maiuscole e minuscole (`ILIKE`, con `%`, `_` e `\` di `q` trattati come caratteri normali).
- Un risultato per messaggio trovato, dai più recenti, al massimo 50. `estratto`: circa 80 caratteri attorno alla prima occorrenza, con «…» ai lati se tagliati.

## Che cosa cambia nell'agente

1. **Istruzioni del progetto.** `/chat` accetta un campo facoltativo `istruzioni` (stringa, fino a 4000 caratteri, vuota se manca). Lo stato del grafo riceve `istruzioni`; `messaggio_sistema` le aggiunge in fondo, sotto un'intestazione che dice che valgono per questa conversazione e che non sostituiscono le regole precedenti. Il router non le vede: l'ambito resta deciso da `risorse/ambito.json`. `esegui_turno` ed `esegui_turno_in_streaming` ricevono `istruzioni` come argomento facoltativo; la CLI non lo passa e non cambia.
2. **Risposta in streaming.** Nuovo endpoint `POST /chat/stream`, stessa richiesta di `/chat` (`messaggio`, `cronologia`, `istruzioni`). Gli errori di validazione e lo stato del servizio prima del turno danno lo stesso JSON di `/chat`; poi il flusso SSE ha gli eventi `testo`, `strumento`, `fine` (`{"risposta", "strumenti", "cronologia"}`, come la risposta di `/chat`) ed `errore` (`{"errore", "stato"}`, con `503` per LM Studio non raggiungibile e `500` per gli altri errori). Usa `esegui_turno_in_streaming` e lo stesso lock di `/chat`: un turno alla volta. A differenza di `/chat`, che aspetta il lock, `/chat/stream` **non aspetta** (scelta di Claude): se un altro turno è in corso risponde subito `409` con `{"errore": "..."}`, prima di aprire il flusso. Così il flusso non resta muto in coda e un limite di attesa non scatta per un motivo che non è un guasto. `/chat` resta com'è.

Il servizio `agente` in Docker riceve queste aggiunte senza altre modifiche.

## Configurazione

Nuove variabili nel `.env` e in `.env.example`:

| Variabile | Uso |
|---|---|
| `BACKEND_PORTA` | porta del back-end (intero tra 1024 e 65535, diversa da `MCP_PORTA`, `API_PORTA`, `AGENTE_PORTA`); ascolta solo su `127.0.0.1` |
| `POSTGRES_USER`, `POSTGRES_DB` | utente e nome del database (per esempio `assistente`); li leggono sia il container sia il back-end |
| `POSTGRES_PASSWORD` | password scelta dall'utente; in `.env.example` resta **vuota**, con un commento che dice di sceglierla. Se manca, il back-end si ferma con un messaggio in italiano e il container del database non parte (lo dice il suo log) |
| `POSTGRES_PORTA` | porta dell'host su cui è pubblicato PostgreSQL, solo su `127.0.0.1` (per esempio `5432`) |

Il back-end raggiunge l'agente su `http://127.0.0.1:<AGENTE_PORTA>` e il database su `127.0.0.1:<POSTGRES_PORTA>`; legge `AGENTE_PORTA` come il servizio dell'agente.

## Docker: il database

Nuovo servizio `database` in `compose.yaml`:

- immagine ufficiale `postgres` con versione fissata (la più recente stabile al momento del piano, verificata);
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` e `POSTGRES_PORTA` dal `.env`, scritte **senza** `:?` (con `${...:-}` o un valore predefinito per la porta). Motivo: Compose controlla le variabili di tutto il file, non solo del servizio avviato; con `:?` un `.env` senza password bloccherebbe anche `.\avvia.ps1`, `.\avvia-agente.ps1` e le prove Docker esistenti, che invece non devono cambiare. Il controllo della password lo fa il back-end;
- porta pubblicata solo su `127.0.0.1:${POSTGRES_PORTA}:5432`;
- volume **con nome** `dati_postgres` (non una cartella del progetto: su Windows i permessi di una cartella montata creano problemi a PostgreSQL). Il volume sopravvive a `docker compose down` e si cancella solo con `docker compose down -v`;
- `healthcheck` con `pg_isready`.

Avvio dello step, in tre terminali (PowerShell, da `assistente-laboratorio/`):

```powershell
docker compose up -d database
python -m servizio_agente
python -m servizio_backend
```

`python -m servizio_backend`: legge il `.env`, si collega al database (se non risponde, errore in italiano che indica `docker compose up -d database`), crea le tabelle se mancano, controlla l'agente e, se non risponde, **avvisa senza fermarsi** (l'agente si può avviare dopo; `/salute` lo riporta). `Ctrl+C`, `SIGTERM` e `SIGBREAK` lo fermano in modo ordinato, come gli altri servizi. Una connessione al database per richiesta (nessun pool: basta per un utente solo).

## Log

Nuovo `logs/servizio_backend.log`: avvio e arresto, e una riga per richiesta con endpoint, esito, stato e durata. Per i turni anche `chat_id`, gli strumenti usati e se il browser si è scollegato prima della fine. Mai il testo dei messaggi né le istruzioni (stanno nel database).

## Test e evidenza

**Automatici** (`python -m pytest`, senza Docker né LM Studio):

- agente: `istruzioni` nel messaggio di sistema solo quando ci sono, e non nel router; `/chat/stream` con modello e router finti: eventi `testo` dal solo nodo `modello`, `strumento`, `fine` con la stessa risposta e la stessa cronologia di `/chat`; rifiuto senza pezzi ma con `risposta` in `fine`; `errore` con stato `503` e `500`; errori `400` prima del flusso;
- back-end con un archivio in memoria e un agente finto: tutte le rotte, i codici di errore, il titolo, il `409` per due turni sulla stessa chat, il salvataggio solo dopo `fine`, nessun salvataggio dopo `errore`, il salvataggio anche se il client si scollega, le istruzioni del progetto passate all'agente;
- configurazione: le nuove variabili, con i messaggi d'errore.

**Prove con PostgreSQL vero** (`--docker`): lo SQL di `archivio.py` (creazione, ricerca con caratteri speciali e maiuscole, cascata di progetti e chat, transazione del turno).

**Il database delle prove è separato da quello dell'utente** (scelta di Claude): le prove avviano il servizio `database` in un **progetto Compose a parte** (`docker compose -p <nome di prova>`), con il suo volume, una porta libera scelta dalla prova e una password di prova. Il container e il volume dell'utente non vengono né fermati né letti, e le prove funzionano anche con lo stack dell'utente acceso. Alla fine le prove cancellano container e volume di prova (`down -v` sul solo progetto di prova).

**Evidenza dello step** (`--docker`): con un agente finto, si creano un progetto e una chat con un turno, si fermano il back-end e il container del database di prova (`stop`), si riavviano entrambi, e chat, messaggi e progetto ci sono ancora. Lo stesso si mostra a mano sul database dell'utente, riportando l'esito nel checkpoint.

**Prova reale** (`--lmstudio` e `--docker`): agente vero, back-end e database. Un progetto con un'istruzione verificabile (per esempio «rispondi sempre in inglese»); un turno «Quanto fa (3+4)*2?» arriva in più pezzi, la risposta salvata contiene 14 e `calcola` tra gli strumenti, e segue l'istruzione; la ricerca di «14» trova il messaggio; la domanda fuori ambito dà il rifiuto fisso anche dentro il progetto.

Si verifica a mano anche il flusso da PowerShell con `curl.exe -N` (lo streaming non si vede con `Invoke-RestMethod`), riportando i comandi nel README.

## Documentazione

- README: avvio dei tre pezzi, variabili nuove, API del back-end, prove, diagnosi (database spento, agente spento, porta occupata).
- `CLAUDE.md`: `servizio_backend/`, il comando di avvio, `logs/servizio_backend.log`, le variabili nuove.
- `docs/studio`: nuovo capitolo `14-backend-delle-chat.md` (con scheda in 5 minuti e scaletta per le slide); aggiornati 00 (stato e mappa), 13 (`/chat/stream` e `istruzioni`), 08 (servizio `database` e variabili), 09 (prove nuove).
- Checkpoint `docs/superpowers/checkpoint/2026-11-10-backend.md` e riga nell'indice `docs/superpowers/README.md`.

## Lasciato a chi costruisce

- Come trasformare le funzioni di callback di `esegui_turno_in_streaming` in un flusso SSE (thread e coda o altro), purché il lock resti preso per tutto il turno.
- Come il back-end continua a leggere l'agente dopo che il browser si è scollegato.
- La versione esatta di `psycopg` e dell'immagine `postgres`, da fissare nel piano.
- I nomi delle funzioni e la divisione dei test in file.
