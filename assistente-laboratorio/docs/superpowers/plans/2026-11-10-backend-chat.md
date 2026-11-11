# Back-end delle chat con PostgreSQL — piano di implementazione

> **Per chi esegue:** usare superpowers:subagent-driven-development oppure superpowers:executing-plans, un task alla volta. I passi usano le caselle (`- [ ]`).

**Obiettivo:** un servizio `servizio_backend` che salva progetti, chat e messaggi in PostgreSQL, cerca nei messaggi e inoltra al browser in streaming la risposta dell'agente, salvando il turno solo a risposta completa.

**Architettura:** l'agente (`servizio_agente`) riceve le istruzioni del progetto e un endpoint SSE `/chat/stream`. Il back-end FastAPI parla con l'agente via HTTP (`client_agente.py`), con PostgreSQL via `psycopg` e SQL scritto a mano (`archivio.py`), e gestisce ogni turno in un thread che salva anche se il browser si scollega (`turni.py`). PostgreSQL gira nel servizio Compose `database`.

**Tecnologie:** Python 3.14, FastAPI 0.162.2, uvicorn, httpx, `psycopg` 3.3.8 (con `psycopg-binary` 3.3.8), `postgres:18.6-alpine`, pytest.

**Specifica:** [`specs/2026-11-10-backend-chat-design.md`](../specs/2026-11-10-backend-chat-design.md). Branch `dev-backend` (già creato da `dev`).

## Vincoli globali

- Tutti i comandi da `assistente-laboratorio/`, in PowerShell, con `.\.venv\Scripts\Activate.ps1`.
- Testi per l'utente ed errori in italiano; errori HTTP sempre `{"errore": "..."}`; i `422` di validazione diventano `400`; JSON con `charset=utf-8`.
- Back-end e agente ascoltano solo su `127.0.0.1`; PostgreSQL pubblicato solo su `127.0.0.1:${POSTGRES_PORTA:-5432}`.
- Nessuna password nel codice, in `compose.yaml` o in `.env.example` (dove `POSTGRES_PASSWORD=` resta vuota).
- Le variabili `POSTGRES_*` in `compose.yaml` **senza** `:?`: `.\avvia.ps1`, `.\avvia-agente.ps1` e le prove Docker esistenti non devono cambiare.
- Limiti: `nome` del progetto 1–100 caratteri; `istruzioni` fino a 4000 (anche nell'agente); `messaggio` non vuoto dopo `strip()` e senza BOM; `q` almeno 2 caratteri; ricerca al massimo 50 risultati; titolo fino a 60 caratteri più «…»; titolo predefinito «Nuova chat».
- Tempi verso l'agente: 5 s per collegarsi, 180 s di lettura tra un evento e l'altro.
- Il turno si salva in **una** transazione e solo dopo l'evento `fine` dell'agente; dopo `errore` o interruzione non si salva nulla, nemmeno la domanda.
- Il log del back-end non contiene mai il testo dei messaggi né le istruzioni.
- Una nuova dipendenza: `psycopg==3.3.8` e `psycopg-binary==3.3.8` in `requirements.txt`.
- Conventional Commits in italiano, **senza** righe `Co-Authored-By`; prima di ogni commit `git status`, controllo del diff, staging selettivo. Niente push; niente merge in `main` senza approvazione.

## Attenzione in revisione

Casi che la specifica implica e che fanno male se sbagliati. Ognuno ha il suo test nel task indicato.

1. **Testo con a capo, accenti ed emoji dentro un evento SSE.** Il pezzo deve arrivare identico, senza spezzare l'evento: Task 2 (`test_sse_andata_e_ritorno`).
2. **Browser che chiude la pagina a metà risposta.** Il turno va salvato lo stesso e il registro dei turni liberato: Task 7 (`test_scollegato_salva_lo_stesso`).
3. **Agente che muore a metà flusso, senza `fine`.** Evento `errore`, nulla salvato, chat di nuovo libera: Task 7 (`test_flusso_finito_senza_fine`).
4. **Database spento mentre il back-end gira.** `503` JSON in italiano, non un `500` con traccia: Task 8 (`test_database_spento_503`).
5. **Ricerca con `%`, `_`, `\` o maiuscole diverse.** Si cercano come caratteri normali, senza distinguere maiuscole e minuscole: Task 4 (`test_ricerca_caratteri_speciali`), anche su PostgreSQL vero (Task 5).

---

### Task 1: istruzioni del progetto nel grafo

**File:**
- Modifica: `assistente/grafo.py` (`StatoConversazione`, `messaggio_sistema`, `nodo_modello`, `esegui_turno`, `esegui_turno_in_streaming`)
- Test: `tests/test_grafo.py`, `tests/test_streaming.py`, `tests/test_grafo_router.py`

**Interfacce prodotte:**
- `StatoConversazione.istruzioni: NotRequired[str]`
- `messaggio_sistema(fuso_utente: str, istruzioni: str = "") -> SystemMessage`
- `esegui_turno(grafo, cronologia, fuso_utente, testo, istruzioni: str = "") -> list[BaseMessage]`
- `esegui_turno_in_streaming(grafo, cronologia, fuso_utente, testo, su_testo, su_messaggi=..., istruzioni: str = "") -> list[BaseMessage]`
- costante `INTESTAZIONE_ISTRUZIONI = "Istruzioni del progetto per questa conversazione (si aggiungono alle regole precedenti e non le sostituiscono):"`

- [ ] **Passo 1: test che falliscono**

```python
def test_istruzioni_in_fondo_al_messaggio_di_sistema():
    testo = messaggio_sistema("Europe/Rome", "Rispondi in inglese.").content
    assert testo.endswith(f"{INTESTAZIONE_ISTRUZIONI}\nRispondi in inglese.")
    assert testo.startswith(messaggio_sistema("Europe/Rome").content)

def test_senza_istruzioni_messaggio_invariato():
    assert INTESTAZIONE_ISTRUZIONI not in messaggio_sistema("Europe/Rome", "   ").content

def test_esegui_turno_passa_le_istruzioni_al_modello():  # in test_grafo.py
    modello = ModelloFinto([AIMessage("ok")])
    esegui_turno(crea_grafo(modello, []), [], "Europe/Rome", "ciao", istruzioni="Sii breve.")
    assert modello.chiamate[0][0].content.endswith("Sii breve.")

def test_router_non_vede_le_istruzioni():  # in test_grafo_router.py, router finto in ambito
    ...  # dopo un turno con istruzioni="Sii breve.", nessun messaggio in router.chiamate[0] contiene "Sii breve."
```

Più un test in `test_streaming.py`: `esegui_turno_in_streaming(..., istruzioni="Sii breve.")` passa le istruzioni al modello come `esegui_turno`.

- [ ] **Passo 2:** `python -m pytest tests/test_grafo.py tests/test_streaming.py tests/test_grafo_router.py -q` → i nuovi test FALLISCONO (`ImportError` o argomento inatteso).
- [ ] **Passo 3: implementare.** `messaggio_sistema` aggiunge `"\n" + INTESTAZIONE_ISTRUZIONI + "\n" + istruzioni.strip()` solo se `istruzioni.strip()` non è vuota. `nodo_modello` usa `stato.get("istruzioni", "")`. Le due funzioni di turno mettono `"istruzioni": istruzioni` nello stato iniziale. Il router non cambia.
- [ ] **Passo 4:** `python -m pytest -q` → tutto PASS (la CLI non passa `istruzioni` e non cambia).
- [ ] **Passo 5: commit** `feat(grafo): istruzioni del progetto in fondo al messaggio di sistema, non viste dal router`

### Task 2: agente — `istruzioni` in `/chat` e nuovo `/chat/stream`

**File:**
- Crea: `assistente/sse.py`
- Modifica: `servizio_agente/app.py`
- Test: `tests/test_sse.py`, `tests/test_servizio_agente.py`, crea `tests/test_servizio_agente_stream.py`

**Interfacce:**
- Consuma: Task 1 (`esegui_turno(..., istruzioni=)`, `esegui_turno_in_streaming(..., istruzioni=)`); `chiamate_riuscite` da `assistente/terminale.py`.
- Produce:
  - `formatta_sse(evento: str, dati: dict) -> str`: `f"event: {evento}\ndata: {json.dumps(dati, ensure_ascii=False)}\n\n"` (il JSON resta su una riga: gli a capo diventano `\n`).
  - `leggi_sse(righe: Iterable[str]) -> Iterator[tuple[str, dict]]`: legge righe `event:` e `data:` e restituisce una coppia a ogni riga vuota; ignora le righe che iniziano con `:`.
  - `RichiestaChat.istruzioni: str = Field(default="", max_length=4000)`.
  - `POST /chat/stream`: richiesta come `/chat`. Eventi `testo {"pezzo"}`, `strumento {"nome","origine","argomenti"}`, `fine {"risposta","strumenti","cronologia"}`, `errore {"errore","stato"}`. `Content-Type: text/event-stream; charset=utf-8`, `Cache-Control: no-cache`.
  - Agente occupato: `409 {"errore": "L'agente sta già rispondendo a un'altra richiesta."}` prima del flusso.

- [ ] **Passo 1: test di `sse.py`**

```python
def test_sse_andata_e_ritorno():
    eventi = [("testo", {"pezzo": "riga 1\nriga 2 è 🙂"}), ("fine", {"risposta": "ok"})]
    testo = "".join(formatta_sse(e, d) for e, d in eventi)
    assert list(leggi_sse(testo.splitlines())) == eventi

def test_sse_ignora_commenti():
    assert list(leggi_sse([": ping", "event: testo", 'data: {"pezzo": "a"}', ""])) == [("testo", {"pezzo": "a"})]
```

- [ ] **Passo 2: test dello stream** (in `tests/test_servizio_agente_stream.py`, con gli stessi `ModelloFinto`/`RouterFinto` e lo stesso `client(...)` di `test_servizio_agente.py`; con `ModelloFinto` ogni `AIMessage` con testo arriva come **un** pezzo, come in `tests/test_streaming.py`)
  - `test_stream_stessa_risposta_e_cronologia_di_chat`: con le stesse risposte preparate, l'evento `fine` ha `risposta`, `strumenti` e `cronologia` (senza `id`) uguali alla risposta di `/chat`.
  - `test_stream_eventi_in_ordine`: con una chiamata a `ora_corrente` e poi `AIMessage("Sono le 19:00.")`, gli eventi sono esattamente `strumento`, `testo {"pezzo": "Sono le 19:00."}`, `fine`.
  - `test_stream_rifiuto_senza_pezzi`: con il router fuori ambito, nessun evento `testo` e `fine.risposta == AMBITO.rifiuto`.
  - `test_stream_errore_lm_studio`: con `openai.APIConnectionError` dal modello, ultimo evento `errore` con `stato == 503`; con `RuntimeError("guasto")`, `stato == 500` e il messaggio contiene «guasto».
  - `test_stream_400_prima_del_flusso`: messaggio vuoto e cronologia illeggibile danno `400` JSON, come `/chat`.
  - `test_stream_409_se_occupato`: con un modello finto che si blocca su un `threading.Event` durante un `/chat` in un thread, `POST /chat/stream` risponde subito `409` con il testo indicato sopra; poi si sblocca il primo turno.
  - `test_istruzioni_arrivano_al_modello` (in `test_servizio_agente.py`): `/chat` con `"istruzioni": "Sii breve."` → il primo messaggio passato al modello finisce con «Sii breve.»; `istruzioni` oltre 4000 caratteri → `400`.
- [ ] **Passo 3:** `python -m pytest tests/test_sse.py tests/test_servizio_agente.py tests/test_servizio_agente_stream.py -q` → FALLISCONO.
- [ ] **Passo 4: implementare.** In `/chat/stream`: validazione come `/chat`; `turno_in_corso.acquire(blocking=False)` e, se fallisce, `409`. Poi un thread esegue `esegui_turno_in_streaming` con callback che mettono eventi in una `queue.Queue`. `su_messaggi` calcola `chiamate_riuscite` sui messaggi nuovi e mette in coda solo quelle non ancora mandate. Alla fine il thread mette `fine` oppure `errore` (`503` per `openai.APIConnectionError`, `500` per le altre) e un segnale di chiusura, e nel `finally` rilascia il lock. La `StreamingResponse` legge la coda e produce `formatta_sse(...)`. Se il client si scollega, il thread finisce comunque il turno e rilascia il lock. Una riga di log per richiesta, come `/chat`, con `endpoint=/chat/stream`. `/chat` passa `istruzioni` a `esegui_turno`.
- [ ] **Passo 5:** `python -m pytest -q` → tutto PASS.
- [ ] **Passo 6: commit** `feat(servizio-agente): istruzioni del progetto e risposta in streaming su /chat/stream (SSE)`

### Task 3: configurazione, dipendenza e log del back-end

**File:**
- Crea: `servizio_backend/__init__.py`, `servizio_backend/configurazione.py`
- Modifica: `assistente/registro.py`, `requirements.txt`, `.env.example`, `tests/test_requisiti.py`
- Test: crea `tests/test_configurazione_backend.py`; `tests/test_registro.py`

**Interfacce prodotte:**
- `@dataclass(frozen=True) class ConfigurazioneBackend: porta: int; url_agente: str; dsn: str; porta_postgres: int`
- `carica_configurazione_backend(env: Mapping[str, str]) -> ConfigurazioneBackend`. Usa `leggi_porta` e `ErroreConfigurazione` di `assistente/configurazione.py`. Obbligatorie: `BACKEND_PORTA`, `AGENTE_PORTA`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`. Facoltativa: `POSTGRES_PORTA`, predefinita `5432`. `BACKEND_PORTA` deve essere diversa da `AGENTE_PORTA`, e da `MCP_PORTA` e `API_PORTA` se sono presenti. `url_agente = f"http://127.0.0.1:{AGENTE_PORTA}"`. `dsn` con `psycopg.conninfo.make_conninfo(host="127.0.0.1", port=..., user=..., password=..., dbname=..., connect_timeout=5)`.
- Messaggio per le mancanti, sul modello di `carica_configurazione`: `"Variabili d'ambiente mancanti: <nomi>. Aggiungile al file .env prendendole da .env.example; per POSTGRES_PASSWORD scegli tu una password."`
- `registro.py`: `LOG_BACKEND = CARTELLA_LOG / "servizio_backend.log"`; `configura_registro(percorso=LOG_ASSISTENTE, nome: str = "assistente")` configura il logger `nome` (il comportamento attuale non cambia).

- [ ] **Passo 1: test.** Valori completi → oggetto atteso (anche il `dsn` contiene `host=127.0.0.1` e `dbname=`); manca `POSTGRES_PASSWORD` → `ErroreConfigurazione` con «POSTGRES_PASSWORD» e «scegli tu una password»; `BACKEND_PORTA == AGENTE_PORTA` → errore; `BACKEND_PORTA == MCP_PORTA` → errore; `POSTGRES_PORTA` assente → `5432`; `POSTGRES_PORTA="abc"` → errore di `leggi_porta`. In `test_registro.py`: `configura_registro(tmp_path / "b.log", nome="servizio_backend")` scrive le righe del logger `servizio_backend` e non tocca il logger `assistente`. In `test_requisiti.py`: aggiungere `"psycopg"` all'elenco.
- [ ] **Passo 2:** test FALLISCONO.
- [ ] **Passo 3: implementare;** `requirements.txt` con `psycopg==3.3.8` e `psycopg-binary==3.3.8`; `pip install -r requirements-dev.txt`. `.env.example`: righe commentate `BACKEND_PORTA=8768`, `POSTGRES_USER=assistente`, `POSTGRES_DB=assistente`, `POSTGRES_PASSWORD=` (commento «scegli una password: resta solo nel tuo .env»), `POSTGRES_PORTA=5432`.
- [ ] **Passo 4:** `python -m pytest -q` → PASS.
- [ ] **Passo 5: commit** `feat(backend): configurazione del back-end, psycopg 3.3.8 e log servizio_backend.log`

### Task 4: testi comuni, contratto dell'archivio e archivio in memoria

**File:**
- Crea: `servizio_backend/testi.py`, `servizio_backend/archivio.py` (eccezioni e `Protocol`), `tests/finti_backend.py` (`ArchivioInMemoria`)
- Test: crea `tests/test_testi_backend.py`, `tests/test_archivio_chat.py`

**Interfacce prodotte:**
- `testi.py`: `TITOLO_PREDEFINITO = "Nuova chat"`; `titolo_da(domanda: str) -> str` (spazi compressi; se più di 60 caratteri, taglio all'ultimo spazio entro 60 quando c'è, poi `"…"`); `estratto(testo: str, q: str, larghezza: int = 80) -> str` (finestra di `larghezza` caratteri centrata sulla prima occorrenza, senza distinguere maiuscole e minuscole, con «…» sui lati tagliati; testo intero se ci sta).
- `archivio.py`: `class ErroreArchivio(Exception)`, `ChatInesistente`, `ProgettoInesistente`, `DatabaseNonRaggiungibile` (sottoclassi). `class Archivio(Protocol)` con:
  - `prepara() -> None` (crea le tabelle), `controlla() -> None` (solleva `DatabaseNonRaggiungibile`)
  - `elenca_progetti() -> list[dict]` (chiavi `id, nome, istruzioni, numero_chat, creato, aggiornato`, ordinati per nome senza distinguere maiuscole e minuscole)
  - `crea_progetto(nome: str, istruzioni: str) -> dict`, `leggi_progetto(id: int) -> dict | None`
  - `aggiorna_progetto(id: int, nome: str | None, istruzioni: str | None) -> dict | None`, `cancella_progetto(id: int) -> bool`
  - `elenca_chat(progetto_id: int | None = None, senza_progetto: bool = False) -> list[dict]` (chiavi `id, titolo, progetto_id, creata, aggiornata`, da `aggiornata` decrescente e poi `id` decrescente; `titolo` già sostituito con `TITOLO_PREDEFINITO` se nullo)
  - `crea_chat(progetto_id: int | None) -> dict` (solleva `ProgettoInesistente`), `leggi_chat(id: int) -> dict | None` (con `messaggi`: `id, ruolo, testo, strumenti, creato`)
  - `contesto_turno(chat_id: int) -> tuple[list[dict], str] | None` (cronologia salvata e istruzioni del progetto, `""` se non c'è)
  - `sposta_chat(id: int, progetto_id: int | None) -> dict | None` (solleva `ProgettoInesistente`), `cancella_chat(id: int) -> bool`
  - `salva_turno(chat_id: int, domanda: str, risposta: str, strumenti: list[dict], cronologia: list[dict]) -> dict` (`messaggio_utente_id, messaggio_assistente_id, titolo`; solleva `ChatInesistente`)
  - `cerca(q: str) -> list[dict]` (`chat_id, titolo, progetto_id, messaggio_id, ruolo, estratto`, al massimo 50, da `messaggio_id` decrescente)
  - Date restituite come stringhe ISO 8601.
- `tests/finti_backend.py`: `ArchivioInMemoria()` che rispetta il contratto, con in più `spento: bool` (se vero, ogni metodo solleva `DatabaseNonRaggiungibile`).

- [ ] **Passo 1: test dei testi.** `titolo_da("  ciao   mondo ") == "ciao mondo"`; una domanda di 100 caratteri fatta di parole da 9 lettere e spazi → risultato lungo al massimo 61, finisce con «…» e senza spazio prima; una parola unica di 100 caratteri → i primi 60 più «…». `estratto("a" * 200 + "Gatto" + "b" * 200, "gatto")` contiene «Gatto», inizia e finisce con «…» ed è lungo 82; `estratto("il gatto", "GATTO") == "il gatto"`.
- [ ] **Passo 2: test del contratto** in `tests/test_archivio_chat.py`, con il fixture `archivio` parametrizzato. Per ora solo `"memoria"`; il Task 5 aggiunge `pytest.param("postgres", marks=pytest.mark.docker)`.
  - `test_progetti_crea_elenca_aggiorna`: `numero_chat` corretto; ordine per nome; `aggiorna_progetto` cambia solo i campi passati e aggiorna `aggiornato`.
  - `test_chat_vuota_ha_titolo_predefinito`
  - `test_salva_turno_messaggi_titolo_cronologia`: dopo due turni ci sono quattro messaggi in ordine; il titolo viene dalla prima domanda e non cambia al secondo turno; `contesto_turno` restituisce l'ultima cronologia; `aggiornata` cresce.
  - `test_salva_turno_chat_inesistente` → `ChatInesistente`
  - `test_elenca_filtri`: con `progetto_id`, con `senza_progetto=True`, senza filtri; ordine per `aggiornata`.
  - `test_sposta_chat` (anche a `None`) e `test_sposta_in_progetto_inesistente` → `ProgettoInesistente`
  - `test_cancella_progetto_cancella_chat_e_messaggi`: dopo, `leggi_chat` → `None` e `cerca` non trova più i loro messaggi.
  - `test_ricerca_caratteri_speciali`: messaggi «100% sicuro», «a_b», «c\\d», «Gatto»; `cerca("%")` trova solo «100% sicuro»; `cerca("_")` solo «a_b»; `cerca("\\")` solo «c\\d»; `cerca("GATTO")` trova «Gatto».
  - `test_ricerca_al_massimo_50_dai_piu_recenti`
  - `test_istruzioni_nel_contesto_turno`
- [ ] **Passo 3:** FALLISCONO. **Passo 4:** implementare `testi.py`, il `Protocol` e `ArchivioInMemoria`. **Passo 5:** `python -m pytest -q` → PASS.
- [ ] **Passo 6: commit** `feat(backend): contratto dell'archivio delle chat, titolo ed estratto, archivio in memoria per i test`

### Task 5: archivio PostgreSQL e servizio Compose `database`

**File:**
- Crea: `servizio_backend/schema.sql`, `tests/postgres_prova.py`
- Modifica: `servizio_backend/archivio.py` (`ArchivioPostgres`), `compose.yaml`, `tests/test_archivio_chat.py`

**Interfacce:**
- Consuma: Task 3 (`dsn`), Task 4 (contratto e test).
- Produce: `ArchivioPostgres(dsn: str)`. Una connessione per chiamata: `psycopg.connect(dsn, row_factory=dict_row)` in un blocco `with`, che fa il commit alla fine. `psycopg.OperationalError` diventa `DatabaseNonRaggiungibile(f"il database PostgreSQL non risponde ({motivo})")`. Per il JSON si usa `psycopg.types.json.Jsonb`. `prepara()` esegue `schema.sql`. Ricerca: `testo ILIKE %s ESCAPE '\'`, con `\`, `%` e `_` di `q` preceduti da `\`. `salva_turno`: due `INSERT` in `messaggi`, `UPDATE chat SET cronologia, aggiornata = now(), titolo = COALESCE(titolo, %s)`, tutto in una transazione; se la chat non c'è (`UPDATE` con 0 righe, o violazione della chiave esterna), `ROLLBACK` e `ChatInesistente`.
- `schema.sql`: le tre tabelle della specifica, con `GENERATED ALWAYS AS IDENTITY`, `ON DELETE CASCADE` e `CHECK (ruolo IN ('utente','assistente'))`; indici `chat(progetto_id)` e `messaggi(chat_id, id)`; tutto con `IF NOT EXISTS`.
- `compose.yaml`, nuovo servizio e volume:

```yaml
  # Lezione 6, step 7: il database delle chat. Avvio: docker compose up -d database
  database:
    image: postgres:18.6-alpine
    environment:
      # Senza :? perché Compose controlla tutto il file: .\avvia.ps1 e .\avvia-agente.ps1 non devono fermarsi.
      POSTGRES_USER: ${POSTGRES_USER:-}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-}
      POSTGRES_DB: ${POSTGRES_DB:-}
    ports:
      - "127.0.0.1:${POSTGRES_PORTA:-5432}:5432"
    volumes:
      # Dalla versione 18 l'immagine vuole il volume su /var/lib/postgresql (non su .../data).
      - dati_postgres:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \"$${POSTGRES_USER}\" -d \"$${POSTGRES_DB}\""]
      interval: 2s
      timeout: 3s
      retries: 30

volumes:
  dati_postgres:
```

- `tests/postgres_prova.py`:
  - `PROGETTO_PROVA = "assistente-laboratorio-prova"`;
  - `@contextmanager database_di_prova() -> Iterator[str]`: sceglie una porta libera; esegue `docker compose -p PROGETTO_PROVA up -d --wait database` con `POSTGRES_USER=prova`, `POSTGRES_PASSWORD=prova`, `POSTGRES_DB=prova` e `POSTGRES_PORTA=<porta>`, più valori finti per le variabili `:?` degli altri servizi (come `ENV_COME_DA_DOTENV` in `test_reale_docker_agente.py`, con in più `LMSTUDIO_BASE_URL_DOCKER`). Restituisce il `dsn`; alla fine fa sempre `docker compose -p PROGETTO_PROVA down -v`;
  - `svuota(dsn)`: `TRUNCATE messaggi, chat, progetti RESTART IDENTITY CASCADE`;
  - `ferma(env)` e `riavvia(env)` per l'evidenza del Task 9.

- [ ] **Passo 1:** aggiungere il parametro `postgres` al fixture di `test_archivio_chat.py`. Il database di prova vale per tutto il modulo; prima di ogni test `prepara()` e poi `svuota()`.
- [ ] **Passo 2:** `python -m pytest --docker tests/test_archivio_chat.py -v` → i casi `postgres` FALLISCONO (manca `ArchivioPostgres`).
- [ ] **Passo 3: implementare** `schema.sql`, `ArchivioPostgres` e il servizio in `compose.yaml`.
- [ ] **Passo 4:** `python -m pytest --docker tests/test_archivio_chat.py -v` → tutti PASS, sia `memoria` sia `postgres`. Poi `docker volume ls`: il volume del progetto di prova non c'è più, e i container e i volumi dell'utente sono quelli di prima.
- [ ] **Passo 5: le altre configurazioni non si rompono.** Con un `.env` temporaneo senza `POSTGRES_*` (oppure con le variabili tolte dall'ambiente), `docker compose config --quiet` termina con codice 0. Poi `python -m pytest -q` → PASS.
- [ ] **Passo 6: commit** `feat(backend): archivio delle chat in PostgreSQL e servizio Compose database su 127.0.0.1`

### Task 6: client dell'agente

**File:**
- Crea: `servizio_backend/client_agente.py`
- Test: crea `tests/test_client_agente.py`

**Interfacce:**
- Consuma: Task 2 (`/chat/stream`, `leggi_sse`).
- Produce:
  - `class AgenteNonDisponibile(Exception)`, `class AgenteInterrotto(Exception)`; il messaggio è il motivo in italiano.
  - `TEMPI = httpx.Timeout(connect=5, read=180, write=10, pool=5)`
  - `class ClientAgente: __init__(self, url: str, client: httpx.Client | None = None)`; `salute(self) -> bool`; `apri_turno(self, messaggio: str, cronologia: list[dict], istruzioni: str) -> TurnoAgente`
  - `class TurnoAgente: eventi(self) -> Iterator[tuple[str, dict]]` (chiude la risposta alla fine); `chiudi(self) -> None`
  - `apri_turno` invia la richiesta in streaming e, **prima** di restituire, controlla lo stato. Errore di collegamento: `AgenteNonDisponibile("L'agente non risponde su <url>: avvialo con python -m servizio_agente.")`. `409`: `AgenteNonDisponibile("L'agente sta già rispondendo a un'altra chat: riprova tra poco.")`. Altri stati: `AgenteNonDisponibile` con il campo `errore` del JSON. `eventi()` trasforma `httpx.ReadTimeout` e gli altri `httpx.HTTPError` in `AgenteInterrotto`.

- [ ] **Passo 1: test.** Usare come `client` un `TestClient` dell'app dell'agente con modello finto (Task 2): è un `httpx.Client`.
  - `test_turno_completo`: gli eventi finiscono con `fine` e `risposta` è quella attesa;
  - `test_istruzioni_inoltrate`: il modello finto riceve «Sii breve.»;
  - `test_agente_spento`: `ClientAgente("http://127.0.0.1:9")` → `AgenteNonDisponibile` con «python -m servizio_agente»; `salute()` → `False`;
  - `test_agente_occupato`: con un `httpx.MockTransport` che risponde `409` → il messaggio dell'agente occupato;
  - `test_flusso_interrotto`: con un `MockTransport` il cui corpo solleva `httpx.ReadError` dopo un evento `testo` → `AgenteInterrotto`, dopo aver restituito quel `testo`.
- [ ] **Passo 2:** FALLISCONO. **Passo 3:** implementare. **Passo 4:** `python -m pytest -q` → PASS.
- [ ] **Passo 5: commit** `feat(backend): client HTTP dell'agente con flusso SSE, agente spento, occupato o interrotto`

### Task 7: il turno in un thread

**File:**
- Crea: `servizio_backend/turni.py`
- Modifica: `tests/finti_backend.py` (`AgenteFinto`)
- Test: crea `tests/test_turni.py`

**Interfacce:**
- Consuma: Task 4 (`Archivio`, `ChatInesistente`, `ErroreArchivio`), Task 6 (`TurnoAgente`, `AgenteInterrotto`), `formatta_sse` (Task 2).
- Produce:
  - `class RegistroTurni`, sicura tra thread: `occupa(chat_id: int) -> bool`, `libera(chat_id: int) -> None`, `in_corso(chat_id: int) -> bool`.
  - `class Turno: __init__(self, chat_id: int, domanda: str, turno_agente, archivio, al_termine: Callable[[], None])`; `avvia() -> None` (thread daemon); `eventi_sse() -> Iterator[str]`; `attendi(limite: float) -> None`. Attributi `esito: str` (`"ok"` o `"errore"`), `scollegato: bool`, `strumenti: list[str]`.
  - Comportamento del thread:
    - inoltra in coda `testo` e `strumento`;
    - all'evento `fine` chiama `archivio.salva_turno(chat_id, domanda, risposta, strumenti, cronologia)` e mette in coda `fine` con `risposta`, `strumenti` e i tre campi restituiti;
    - un `errore` dell'agente diventa `errore {"errore": ...}`;
    - `AgenteInterrotto`, un flusso finito senza `fine` (`"La risposta dell'agente si è interrotta: il turno non è stato salvato."`) o un `ErroreArchivio` durante il salvataggio danno `errore`, e nulla è salvato;
    - nel `finally` chiama `al_termine()` (che libera il registro) e scrive la riga di log.
  - `eventi_sse()` legge la coda fino al segnale di chiusura. Su `GeneratorExit` mette `scollegato = True` ed esce, senza fermare il thread.
  - Log (logger `servizio_backend`): `richiesta endpoint=/chat/{id}/messaggi chat_id=… esito=… strumenti=[…] scollegato=… durata=…`.
- `AgenteFinto(eventi: list[tuple[str, dict]], *, non_disponibile: str | None = None, interrompi_dopo: int | None = None, cancello: threading.Event | None = None)`. Registra le chiamate `(messaggio, cronologia, istruzioni)` in `chiamate`. `salute()` restituisce `non_disponibile is None`. Se c'è `cancello`, `eventi()` lo aspetta prima di mandare `fine`.

- [ ] **Passo 1: test.**
  - `test_turno_ok_salva_e_finisce`: gli eventi SSE letti con `leggi_sse` sono `testo`, `strumento`, `fine`; l'archivio ha i due messaggi; `al_termine` è stato chiamato una volta;
  - `test_errore_agente_non_salva`
  - `test_flusso_finito_senza_fine`: evento `errore` con «non è stato salvato»; archivio vuoto; `al_termine` chiamato;
  - `test_scollegato_salva_lo_stesso`: si legge il primo evento da `eventi_sse()`, poi `.close()`, `attendi(5)`; l'archivio ha il turno, `scollegato is True` ed `esito == "ok"`;
  - `test_salvataggio_fallito`: con un archivio `spento` al momento del salvataggio → `errore`, `esito == "errore"`;
  - `test_log_senza_testi`: la riga di log non contiene né la domanda né la risposta.
- [ ] **Passo 2:** FALLISCONO. **Passo 3:** implementare. **Passo 4:** `python -m pytest -q` → PASS.
- [ ] **Passo 5: commit** `feat(backend): turno in un thread, salvato solo a risposta completa anche se il browser si scollega`

### Task 8: l'applicazione FastAPI del back-end

**File:**
- Crea: `servizio_backend/app.py`
- Test: crea `tests/test_servizio_backend.py`

**Interfacce:**
- Consuma: Task 4, 6, 7. `RispostaJson` e il gestore della validazione si copiano dal modello di `servizio_agente/app.py`; se il codice diventa uguale, spostarlo in un modulo comune, per esempio `assistente/http.py`.
- Produce: `crea_app(archivio, agente) -> FastAPI`, con titolo «Back-end delle chat». Rotte, codici e corpi come nella tabella della specifica. In più:
  - `ErroreArchivio` di tipo `DatabaseNonRaggiungibile` dà `503` su ogni rotta (con un gestore di eccezioni);
  - `GET /chat?progetto=` accetta un intero o `nessuno`, altrimenti `400`;
  - `DELETE` di una chat in corso, o di un progetto che ne contiene una, dà `409 {"errore": "C'è un turno in corso in questa chat: aspetta che finisca."}`;
  - `POST /chat/{id}/messaggi`, nell'ordine: `400` messaggio vuoto, `404` chat, `409` registro occupato (`"C'è già una risposta in corso in questa chat."`), `503` da `AgenteNonDisponibile` (liberando il registro), poi `Turno.avvia()` e `StreamingResponse(turno.eventi_sse(), media_type="text/event-stream; charset=utf-8", headers={"Cache-Control": "no-cache"})`;
  - `/salute`: `controlla()` (`503` se fallisce) e `agente.salute()`.

- [ ] **Passo 1: test** con `TestClient(crea_app(ArchivioInMemoria(), AgenteFinto(...)))`:
  - una prova per ogni rotta, con il caso riuscito e i suoi errori (`400`, `404`, `409`);
  - `test_validazione_400_in_italiano`: `nome` vuoto o di 101 caratteri, `istruzioni` di 4001 caratteri, `q` di 1 carattere;
  - `test_turno_streaming_e_salvato`: gli eventi finiscono con `fine`; poi `GET /chat/{id}` mostra i due messaggi e il titolo;
  - `test_istruzioni_del_progetto_all_agente`: le istruzioni arrivano in `AgenteFinto.chiamate`; senza progetto arriva `""`;
  - `test_seconda_domanda_usa_la_cronologia_salvata`
  - `test_agente_non_disponibile_503`: dopo, la stessa chat accetta un nuovo turno;
  - `test_409_durante_un_turno`: il primo turno, bloccato con `cancello`, gira in un thread; un secondo `POST` sulla stessa chat dà `409`; anche `DELETE` della chat e del suo progetto dà `409`; un'altra chat invece è libera;
  - `test_database_spento_503`: con `archivio.spento = True`, `GET /chat` e `GET /salute` danno `503` con «non risponde»;
  - `test_salute`: `"agente": "non raggiungibile"` quando `AgenteFinto` non è disponibile.
- [ ] **Passo 2:** FALLISCONO. **Passo 3:** implementare. **Passo 4:** `python -m pytest -q` → PASS.
- [ ] **Passo 5: commit** `feat(backend): API di progetti, chat, ricerca e turno in streaming`

### Task 9: avvio `python -m servizio_backend` ed evidenza dopo il riavvio

**File:**
- Crea: `servizio_backend/__main__.py`, `tests/test_avvio_servizio_backend.py`, `tests/test_reale_docker_backend.py`

**Interfacce:**
- Consuma: Task 3, 5, 6, 8.
- Produce: `main() -> int`, sul modello di `servizio_agente/__main__.py`:
  1. `configura_flussi()` e `load_dotenv(override=False)`;
  2. `carica_configurazione_backend(os.environ)` e `configura_registro(LOG_BACKEND, nome="servizio_backend")`;
  3. se la porta è occupata, `ErroreAvvio` con «BACKEND_PORTA»;
  4. `ArchivioPostgres(dsn)`: `controlla()`, poi `prepara()`. Se il database non risponde, l'errore stampato è `"Il database PostgreSQL non risponde su 127.0.0.1:<porta>: avvialo con docker compose up -d database."` e l'uscita è `1`;
  5. `ClientAgente(url).salute()`: se è falso, stampa `"Attenzione: l'agente non risponde su <url>. Avvialo con python -m servizio_agente; il back-end intanto parte."` e prosegue;
  6. segnali `SIGBREAK` e `SIGTERM` come arresto ordinato; righe di log `avvio servizio backend porta=…` e `arresto servizio backend`;
  7. `uvicorn.run(app, host="127.0.0.1", port=porta, log_level="warning", access_log=False)`.
- [ ] **Passo 1: test di avvio,** senza Docker, sul modello di `test_avvio_servizio_agente.py`: `ArchivioPostgres` sostituito da `ArchivioInMemoria`, `uvicorn.run` finto che interroga l'app.
  - config mancante → uscita `1` con il messaggio;
  - database spento → uscita `1` con «docker compose up -d database»;
  - agente spento → avviso e avvio comunque;
  - avvio regolare → `host == "127.0.0.1"`, nel log la riga di avvio e quella di arresto.
- [ ] **Passo 2:** FALLISCONO. **Passo 3:** implementare. **Passo 4:** `python -m pytest -q` → PASS.
- [ ] **Passo 5: evidenza dello step** in `tests/test_reale_docker_backend.py` (`pytestmark = pytest.mark.docker`; `cartelle_da_parte(CARTELLA, ("logs",))`).
  - **Preparazione:** `database_di_prova()`; agente finto via HTTP, cioè l'app di `servizio_agente.app.crea_app` con `ModelloFinto` (abbastanza risposte per un turno) servita da uvicorn in un thread su una porta libera; back-end come **processo vero**: `python -m servizio_backend` con `BACKEND_PORTA`, `AGENTE_PORTA`, `POSTGRES_*` di prova e `creationflags=CREATE_NEW_PROCESS_GROUP` su Windows.
  - **Prima del riavvio:** un progetto con istruzioni, una chat nel progetto, un turno via `httpx.stream` finito con `fine`.
  - **Riavvio:** arresto del back-end con `CTRL_BREAK_EVENT` (uscita `0`, nel log «arresto servizio backend»); `docker compose -p PROGETTO_PROVA stop database` e poi `up -d --wait database`; nuovo avvio del back-end.
  - **Controllo:** `GET /progetti`, `GET /chat` e `GET /chat/{id}` restituiscono gli stessi dati di prima, con i due messaggi. Stampare i dati con `-s`.
- [ ] **Passo 6:** `python -m pytest --docker -m docker -v -s` → tutte PASS (le 7 prove esistenti e le nuove).
- [ ] **Passo 7: commit** `feat(backend): avvio con python -m servizio_backend e prova Docker delle chat dopo il riavvio`

### Task 10: prova reale con LM Studio

**File:**
- Crea: `tests/test_reale_backend.py` (`pytestmark = [pytest.mark.lmstudio, pytest.mark.docker]`)

- [ ] **Passo 1: scrivere la prova.**
  - **Preparazione:** `ambiente_reale()` (agente vero, archivio delle note temporaneo), app dell'agente in uvicorn su una porta libera; `database_di_prova()`; app del back-end con `ArchivioPostgres` e `ClientAgente`, in uvicorn su un'altra porta.
  - **Turno nel progetto:** un progetto con istruzioni «Rispondi sempre in inglese.» e una chat dentro. Il turno «Quanto fa (3+4)*2?» deve avere più di un evento `testo`; `fine.risposta` contiene «14»; `calcola` sta in `fine.strumenti`. La risposta è in inglese: `re.search(r"\b(the|is|equals|result)\b", risposta.lower())`. Se questo controllo fallisce, riportarlo come comportamento del modello, con la risposta stampata.
  - **Ricerca:** `GET /ricerca?q=14` trova il messaggio dell'assistente.
  - **Rifiuto:** «scrivimi una poesia sul mare» nella stessa chat dà `fine.risposta == carica_ambito().rifiuto`.
- [ ] **Passo 2:** `python -m pytest --lmstudio --docker tests/test_reale_backend.py -v -s` → PASS. Se fallisce per il modello, riportare l'esito con le evidenze, senza cambiare il modello.
- [ ] **Passo 3: commit** `test(backend): prova reale con LM Studio, PostgreSQL e istruzioni del progetto`

### Task 11: verifica completa e prova manuale

- [ ] **Passo 1:** `python -m pytest` → annotare passati e saltati.
- [ ] **Passo 2:** `python -m pytest --docker -m docker -v -s` e `python -m pytest --lmstudio -m lmstudio -v -s` → annotare gli esiti. Un fallimento intermittente del modello si riesegue da solo e si riporta.
- [ ] **Passo 3: prova manuale** con il `.env` dell'utente. Se `POSTGRES_PASSWORD` è vuota, chiedere all'utente di sceglierla: non inventarla.
  1. `docker compose up -d database`, poi `python -m servizio_agente` e `python -m servizio_backend` in due terminali;
  2. `Invoke-RestMethod` su `/salute` e `POST /progetti`;
  3. `curl.exe -N -X POST http://127.0.0.1:<BACKEND_PORTA>/chat/<id>/messaggi -H "Content-Type: application/json" --data-binary "@domanda.json"`: si vedono i pezzi arrivare;
  4. riavvio: `Ctrl+C` sul back-end, `docker compose stop database`, `docker compose up -d database`, di nuovo il back-end; `GET /chat/<id>` mostra ancora la chat;
  5. `.\avvia.ps1` e `.\avvia-agente.ps1` partono ancora.

  Annotare i comandi che hanno funzionato davvero, da copiare nel README.
- [ ] **Passo 4:** le eventuali correzioni vanno in commit `fix(...)` separati, ognuno con il suo test.

### Task 12: documenti e checkpoint

- [ ] **Passo 1: README.** Sezione «Il back-end delle chat»: avvio dei tre pezzi, variabili, tabella delle API, esempi verificati al Task 11 (compreso `curl.exe -N`), prove, diagnosi (database spento, password mancante, agente spento o occupato, porta occupata, `docker compose down -v` che cancella le chat).
- [ ] **Passo 2: `../CLAUDE.md`.** Struttura (`servizio_backend/` e i suoi file), comando `python -m servizio_backend`, `docker compose up -d database`, `logs/servizio_backend.log`, variabili `BACKEND_PORTA` e `POSTGRES_*`.
- [ ] **Passo 3: `docs/studio`.**
  - nuovo `14-backend-delle-chat.md`, con scheda in 5 minuti, corpo con `file:riga` e scaletta per le slide: perché tre servizi; tabelle e perché cronologia e messaggi sono separati; turno in un thread; salvataggio a risposta completa; browser scollegato; SSE; evidenza dopo il riavvio;
  - aggiornare 00 (stato dello step 7 e mappa), 13 (`/chat/stream` e `istruzioni`), 08 (servizio `database`, volume, variabili), 09 (prove nuove e database di prova separato), 04 (sezione sulle istruzioni del progetto nel messaggio di sistema).
- [ ] **Passo 4: checkpoint** `docs/superpowers/checkpoint/2026-11-10-backend.md` con **Fatto**, **Da fare** (merge da approvare; step 8 e 9) e **Stato attuale** (branch, ultimo commit, esiti dei test del Task 11, cosa non è verificato). Più le righe nell'indice `docs/superpowers/README.md`.
- [ ] **Passo 5: commit** `docs(backend): README, CLAUDE.md, capitolo 14 di studio e checkpoint dello step 7`
- [ ] **Passo 6:** chiedere all'utente l'approvazione esplicita per unire `dev-backend` in `main`.
