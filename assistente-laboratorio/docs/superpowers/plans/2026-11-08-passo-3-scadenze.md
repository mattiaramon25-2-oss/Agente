# Passo 3 — Giorni e scadenze nelle varianti MCP e FastAPI — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** lo strumento `calcola_scadenza` esposto dal server MCP e, in alternativa, da un servizio FastAPI chiamato tramite un wrapper HTTP registrato con `@tool`. La variante attiva si sceglie con `VARIANTE_SCADENZE`.

**Architecture:**
- **Logica:** `logica/scadenze.py`, con le festività lette da `risorse/festivita_italia.json`.
- **Variante MCP:** il server la registra con `esegui_registrato`.
- **Variante FastAPI:**
  - il pacchetto `servizio_api/` espone `GET /scadenza` con FastAPI e gira come processo separato, avviato dall'agente con `processo_in_attesa`;
  - `assistente/wrapper_scadenze.py` è il wrapper scritto a mano: nome, descrizione e schema sono quelli del catalogo MCP, ricopiati senza discovery (slide 19).

**Tech Stack:** `fastapi` 0.162.2, `uvicorn` 0.54.0, `httpx` 0.28.1; il resto come nel passo 1.

**Spec:** `docs/superpowers/specs/2026-11-08-strumenti-lezione-5-design.md`, sezioni 5.4, 6, 7, 8 e 13.

**Branch:** `dev-scadenze`, creato da `dev`. Se il passo 2 non è ancora unito, il branch parte da `dev-calcolatrice`.

## Global Constraints

Valgono quelli del passo 1. In più:

- **Nome e argomenti** (tutti obbligatori): `calcola_scadenza`, con `data_inizio` (string), `giorni` (integer) e `lavorativi` (boolean).
- **Descrizione** (testo esatto, identico nelle due varianti): `Calcola la data di scadenza aggiungendo un numero di giorni a una data ISO (AAAA-MM-GG). Con lavorativi=true conta solo i giorni dal lunedì al venerdì esclusi i festivi nazionali italiani. Risultato indicativo, senza valore legale.`
- **Intervalli:** `giorni` va da 0 a 3650. Le festività coprono gli anni 2026, 2027 e 2028.
- **Messaggi d'errore esatti:**
  - `Data non valida: '<valore>'. Usa il formato AAAA-MM-GG, per esempio 2026-12-23.`;
  - `giorni deve essere un numero intero tra 0 e 3650.`;
  - `lavorativi deve essere true o false.`;
  - `Festività disponibili solo per gli anni 2026–2028: il calcolo dei giorni lavorativi esce da questo intervallo.`
- **Nota del risultato** (testo esatto): `Calcolo indicativo: non ha valore legale.`
- **Servizio FastAPI:**
  - titolo `Servizio scadenze`;
  - endpoint `GET /scadenza`;
  - solo su `127.0.0.1:<API_PORTA>`;
  - log del logger `servizio_api` su stderr, finisce in `logs/servizio_api.log`.
- **Wrapper:**
  - timeout HTTP di 5 s;
  - origine `fastapi`;
  - messaggi di collegamento `Servizio scadenze non raggiungibile: <Tipo>: <messaggio>` e `Servizio scadenze: nessuna risposta entro 5 secondi.`
- **Variabili:**
  - `VARIANTE_SCADENZE`, obbligatoria, con valori `mcp` o `fastapi`;
  - `API_PORTA`, obbligatoria solo con `fastapi`: intero tra 1024 e 65535, diverso da `MCP_PORTA`.

## Review Focus

1. **Stringa `"20261223"` come data:** `date.fromisoformat` la accetterebbe, ma la specifica vuole `AAAA-MM-GG`, quindi va rifiutata. Lo verifica il Task 1 (`test_date_non_valide`).
2. **Il 422 in inglese di FastAPI non deve mai arrivare al modello:** un parametro mancante o di tipo sbagliato diventa un 400 in italiano. Lo verifica il Task 3 (`test_errori_di_tipo_in_italiano`).
3. **Servizio caduto a sessione in corso:** errore di collegamento, chat che continua, nessuna eccezione. Lo verifica il Task 5 (`test_ciclo_completo_servizio`, chiamata dopo l'arresto).
4. **Un processo che fallisce all'avvio deve spegnere anche l'altro:** se il servizio FastAPI non parte, il server MCP già avviato viene spento. Lo verifica il Task 6 (`test_servizio_che_non_parte_spegne_tutto`).
5. **`API_PORTA` uguale a `MCP_PORTA`:** errore di configurazione chiaro, non «porta già in uso» a metà avvio. Lo verifica il Task 6.

---

### Task 0: branch

- [ ] **Step 1:** `git switch -c dev-scadenze`, partendo dal branch indicato nell'intestazione.

---

### Task 1: festività e logica delle scadenze

**Files:**
- Create: `risorse/festivita_italia.json`, `logica/scadenze.py`
- Test: `tests/test_scadenze.py`

**Interfaces:**
- Produces:
  - `PERCORSO_FESTIVITA: Path` (cioè `<progetto>/risorse/festivita_italia.json`);
  - `@dataclass(frozen=True) Festivita(anni: frozenset[int], date: dict[date, str])`;
  - `carica_festivita(percorso: Path = PERCORSO_FESTIVITA) -> Festivita`;
  - `calcola_scadenza(data_inizio: object, giorni: object, lavorativi: object, festivita: Festivita | None = None) -> dict`, che solleva `ErroreStrumento`. Con `None` si usa il file, caricato una sola volta.

- [ ] **Step 1: scrivere `risorse/festivita_italia.json`** nel formato `{"anni": [2026, 2027, 2028], "festivita": [{"data": "AAAA-MM-GG", "nome": "..."}]}`.
  - Per ogni anno: Capodanno (01-01), Epifania (01-06), Pasquetta, Festa della Liberazione (04-25), Festa del Lavoro (05-01), Festa della Repubblica (06-02), Ferragosto (08-15), Ognissanti (11-01), Immacolata (12-08), Natale (12-25), Santo Stefano (12-26).
  - Pasquetta, verificata: `2026-04-06`, `2027-03-29`, `2028-04-17`.
- [ ] **Step 2: scrivere i test**

```python
def test_esempio_della_specifica():
    assert calcola_scadenza("2026-12-23", 3, True) == {
        "data_inizio": "2026-12-23", "giorni": 3, "lavorativi": True, "scadenza": "2026-12-29",
        "giorno_settimana": "martedì", "festivita_saltate": ["2026-12-25 Natale", "2026-12-26 Santo Stefano"],
        "nota": "Calcolo indicativo: non ha valore legale."}

@pytest.mark.parametrize("inizio, giorni, lavorativi, scadenza", [
    ("2026-12-23", 3, False, "2026-12-26"), ("2026-11-06", 1, True, "2026-11-09"),   # venerdì → lunedì
    ("2026-11-07", 1, True, "2026-11-09"),                                            # inizio di sabato
    ("2026-04-03", 1, True, "2026-04-07"),                                            # Pasquetta 2026
    ("2026-12-31", 1, True, "2027-01-04"), ("2026-03-10", 0, True, "2026-03-10"),
    ("2028-12-29", 365, False, "2029-12-29"), ("2026-01-30", "3", False, "2026-02-02"),
])
def test_scadenze(inizio, giorni, lavorativi, scadenza):
    assert calcola_scadenza(inizio, giorni, lavorativi)["scadenza"] == scadenza

def test_calendario_senza_festivita_saltate():
    assert calcola_scadenza("2026-12-23", 3, False)["festivita_saltate"] == []

@pytest.mark.parametrize("data", ["2026-02-30", "30/01/2026", "20261223", "2026-1-5", "", None, 20261223])
def test_date_non_valide(data):
    with pytest.raises(ErroreStrumento, match="Data non valida"):
        calcola_scadenza(data, 1, True)

@pytest.mark.parametrize("giorni", [-1, 3651, 2.5, True, "tre", None])
def test_giorni_non_validi(giorni):
    with pytest.raises(ErroreStrumento, match="giorni deve essere"):
        calcola_scadenza("2026-03-10", giorni, True)

@pytest.mark.parametrize("lavorativi", ["true", 1, None])
def test_lavorativi_non_booleano(lavorativi):
    with pytest.raises(ErroreStrumento, match="lavorativi deve essere"):
        calcola_scadenza("2026-03-10", 1, lavorativi)

def test_fuori_dagli_anni_coperti():
    with pytest.raises(ErroreStrumento, match="2026–2028"):
        calcola_scadenza("2028-12-29", 5, True)

def test_file_delle_festivita():
    f = carica_festivita()
    assert f.anni == {2026, 2027, 2028} and len(f.date) == 33 and f.date[date(2027, 3, 29)] == "Pasquetta"
```

- [ ] **Step 3:** `python -m pytest tests/test_scadenze.py -v`. Atteso: FAIL.
- [ ] **Step 4: implementare.**
  - **`data_inizio`:** solo testo che corrisponde a `^\d{4}-\d{2}-\d{2}$` e che `date.fromisoformat` accetta.
  - **`giorni`:** un `int` non `bool`; un `float` con `is_integer()`; un testo fatto solo di cifre. Poi l'intervallo.
  - **`lavorativi`:** solo un `bool`.
  - **Conteggio:**
    - si avanza di un giorno alla volta da `data_inizio + 1`;
    - con `lavorativi` contano solo i giorni dal lunedì al venerdì che non sono festivi;
    - ogni festività incontrata, in qualsiasi giorno della settimana, va in `festivita_saltate` come `"AAAA-MM-GG Nome"`;
    - con `lavorativi` ogni giorno visitato deve cadere negli anni coperti, altrimenti c'è l'errore degli anni;
    - con `giorni == 0` non si visita nessun giorno.
  - **`giorno_settimana`:** si usano i nomi di `logica.orologio.GIORNI`.
  - **Nel risultato** `giorni` è l'intero normalizzato.
- [ ] **Step 5:** `python -m pytest tests/test_scadenze.py -v`. Atteso: tutti PASS.
- [ ] **Step 6:** commit `feat(logica): aggiungi il calcolo delle scadenze con le festività italiane`.

---

### Task 2: `calcola_scadenza` nel server MCP

**Files:**
- Modify: `server_mcp/server.py`
- Test: `tests/test_server_mcp.py`

**Interfaces:**
- Produces: `NOME_SCADENZE = "calcola_scadenza"` e `DESCRIZIONE_SCADENZE` (testo dei Global Constraints).

- [ ] **Step 1: test**
  - Il catalogo guadagna `calcola_scadenza`.
  - Il suo schema ha `required == ["data_inizio", "giorni", "lavorativi"]` e i tipi `string`, `integer`, `boolean`.
  - La chiamata con l'esempio della specifica dà `scadenza == "2026-12-29"`.
  - `{"data_inizio": "2026-02-30", "giorni": 1, "lavorativi": True}` dà un errore MCP con `Data non valida`.
- [ ] **Step 2:** `python -m pytest tests/test_server_mcp.py -v`. Atteso: FAIL.
- [ ] **Step 3:** registrare lo strumento con i tre parametri `Annotated[Any, WithJsonSchema({...})]`, che portano i tipi dei Global Constraints e una descrizione breve ciascuno.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(server): esponi il calcolo delle scadenze via MCP`.

---

### Task 3: servizio FastAPI

**Files:**
- Modify: `requirements.txt` (`fastapi==0.162.2`, `uvicorn==0.54.0`, `httpx==0.28.1`)
- Create: `servizio_api/__init__.py`, `servizio_api/app.py`, `servizio_api/__main__.py`
- Test: `tests/test_servizio_api.py`

**Interfaces:**
- Consumes: `logica.scadenze.calcola_scadenza`.
- Produces: `crea_app() -> FastAPI`; il comando `python -m servizio_api --porta <int>`.

- [ ] **Step 1: installare le dipendenze**: `python -m pip install -r requirements-dev.txt`, poi `python -m pip check`. Atteso: `No broken requirements found.`
- [ ] **Step 2: test** con `fastapi.testclient.TestClient(crea_app())`

```python
def test_scadenza_ok(client):
    r = client.get("/scadenza", params={"data_inizio": "2026-12-23", "giorni": 3, "lavorativi": "true"})
    assert r.status_code == 200 and r.json() == calcola_scadenza("2026-12-23", 3, True)

def test_errore_dello_strumento(client):
    r = client.get("/scadenza", params={"data_inizio": "2026-02-30", "giorni": 1, "lavorativi": "true"})
    assert r.status_code == 400 and r.json()["errore"].startswith("Data non valida")

@pytest.mark.parametrize("params", [{"giorni": 1, "lavorativi": "true"}, {"data_inizio": "2026-03-10", "giorni": "tre", "lavorativi": "true"},
                                    {"data_inizio": "2026-03-10", "giorni": 1, "lavorativi": "forse"}])
def test_errori_di_tipo_in_italiano(client, params):
    r = client.get("/scadenza", params=params)
    assert r.status_code == 400 and r.json()["errore"].startswith("Argomenti non validi per calcola_scadenza")

def test_openapi_descrive_scadenza(client):
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Servizio scadenze" and "/scadenza" in schema["paths"]
```

- [ ] **Step 3:** `python -m pytest tests/test_servizio_api.py -v`. Atteso: FAIL.
- [ ] **Step 4: implementare `app.py`.**
  - `GET /scadenza` ha parametri tipizzati: `data_inizio: str`, `giorni: int`, `lavorativi: bool`.
  - Un `ErroreStrumento` diventa `JSONResponse(400, {"errore": str(e)})`.
  - Un gestore di `RequestValidationError` restituisce 400 con `Argomenti non validi per calcola_scadenza: ` seguito, per ogni errore, da `<nome>: mancante` o `<nome>: valore non valido`, separati da `; `.
  - Ogni richiesta scrive nel log di `servizio_api` la riga `richiesta endpoint=/scadenza argomenti=<json> esito=ok|errore`, nel formato del server MCP.
- [ ] **Step 5: implementare `__main__.py`.**
  - `--porta` obbligatoria e lo stesso `basicConfig` del server MCP.
  - Le righe `avvio servizio porta=<p>` e, nel `finally`, `arresto servizio`.
  - Poi `uvicorn.run(crea_app(), host="127.0.0.1", port=porta, log_level="warning", access_log=False)`.
- [ ] **Step 6:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 7:** commit `feat(api): aggiungi il servizio FastAPI delle scadenze`.

---

### Task 4: wrapper HTTP registrato con `@tool`

**Files:**
- Create: `assistente/wrapper_scadenze.py`
- Test: `tests/test_wrapper_scadenze.py`

**Interfaces:**
- Consumes: `crea_app` (Task 3); `TIPO_STRUMENTO` e `TIPO_COLLEGAMENTO` (passo 1).
- Produces: `TIMEOUT_HTTP = 5.0`, `ORIGINE_FASTAPI = "fastapi"`, `crea_wrapper_scadenze(url_base: str, http: httpx.Client | None = None, timeout: float = TIMEOUT_HTTP) -> BaseTool`.

- [ ] **Step 1: test**
  - **Contratto identico al catalogo MCP:** stesso nome, stessa descrizione e stessi `required`. I tipi delle tre proprietà sono gli stessi, tutti presi da `tool_call_schema`, come per la calcolatrice nel passo 2.
  - **Parità con il servizio vero:** passare `http=TestClient(crea_app())`, che è un `httpx.Client`. Per gli input `("2026-12-23", 3, True)`, `("2026-12-23", 3, False)`, `("2026-02-30", 1, True)` e `("2028-12-29", 5, True)`, il wrapper restituisce lo stesso risultato, o lo stesso testo d'errore, della chiamata MCP in memoria.
  - **Collegamento, con `httpx.Client(transport=httpx.MockTransport(...))`.** Il risultato è sempre una stringa JSON e non si solleva mai un'eccezione:

```python
@pytest.mark.parametrize("gestore, tipo, frammento", [
    (lambda r: httpx.Response(400, json={"errore": "Data non valida: 'x'"}), "strumento", "Data non valida"),
    (lambda r: httpx.Response(503, text="giù"), "collegamento", "Servizio scadenze non raggiungibile"),
    (lambda r: httpx.Response(200, text="non json"), "collegamento", "Servizio scadenze non raggiungibile"),
    (solleva(httpx.ConnectError("rifiutata")), "collegamento", "ConnectError: rifiutata"),
    (solleva(httpx.ReadTimeout("lento")), "collegamento", "nessuna risposta entro 5 secondi"),
])
def test_errori(gestore, tipo, frammento): ...
```

  - **Parametri inviati:** controllare che `lavorativi=True` arrivi come `lavorativi=true` e `giorni=3` come `giorni=3`.
- [ ] **Step 2:** `python -m pytest tests/test_wrapper_scadenze.py -v`. Atteso: FAIL.
- [ ] **Step 3: implementare.**
  - Dentro `crea_wrapper_scadenze`, `@tool` su `def calcola_scadenza(data_inizio: str, giorni: int, lavorativi: bool) -> str:`, con la docstring **esattamente** uguale alla descrizione dei Global Constraints.
  - Il corpo esegue `GET {url_base}/scadenza` con `params={"data_inizio": ..., "giorni": str(giorni), "lavorativi": "true" if lavorativi else "false"}` e il timeout.
  - **Esiti:**
    - un 200 con JSON valido restituisce il JSON;
    - un 400 con `errore` dà un errore dello strumento;
    - `httpx.TimeoutException` dà il messaggio di timeout;
    - qualsiasi altro `httpx.HTTPError`, uno stato inatteso o un JSON non valido danno l'errore di collegamento.
  - Il tool ha `metadata={"origine": "fastapi"}`. Senza `http`, si crea un `httpx.Client` per ogni chiamata, chiuso con `with`.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(api): aggiungi il wrapper HTTP delle scadenze per l'agente`.

---

### Task 5: avvio e arresto del servizio FastAPI

**Files:**
- Modify: `assistente/avvio_server.py`, `assistente/registro.py` (`LOG_API = CARTELLA_LOG / "servizio_api.log"`)
- Test: `tests/test_avvio_servizio_api.py`

**Interfaces:**
- Consumes: `processo_in_attesa` (passo 1); `crea_wrapper_scadenze` (Task 4).
- Produces: `url_servizio(porta: int) -> str` (`http://127.0.0.1:<porta>`), `@dataclass(frozen=True) ServizioAvviato(processo, url: str)`, `@contextmanager avvia_servizio_api(porta, percorso_log, attesa=ATTESA_AVVIO, comando=None) -> Iterator[ServizioAvviato]`.

- [ ] **Step 1: test** con il servizio reale, come i test del server MCP nel passo 1:
  - `test_ciclo_completo_servizio`:
    - il wrapper su `avviato.url` restituisce `scadenza == "2026-12-29"` per l'esempio della specifica;
    - il log contiene `endpoint=/scadenza`;
    - dopo l'uscita il processo è terminato e una nuova chiamata dà `tipo == "collegamento"`;
  - `test_porta_occupata_servizio`: il messaggio contiene `API_PORTA`;
  - `test_nessun_output_nel_terminale_servizio`;
  - `test_servizio_che_non_risponde_viene_spento`.
- [ ] **Step 2:** `python -m pytest tests/test_avvio_servizio_api.py -v`. Atteso: FAIL.
- [ ] **Step 3: implementare `avvia_servizio_api`** su `processo_in_attesa`:
  - comando predefinito `[sys.executable, "-m", "servizio_api", "--porta", str(porta)]`;
  - `descrizione="servizio FastAPI"`, `variabile_porta="API_PORTA"`;
  - la `prova` esegue `httpx.get(f"{url}/openapi.json", timeout=t)` e considera il servizio pronto solo se `"/scadenza"` è in `json()["paths"]`.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(api): avvia, attendi e spegni il servizio FastAPI`.

---

### Task 6: scelta della variante con `VARIANTE_SCADENZE` e `API_PORTA`

**Files:**
- Modify: `assistente/configurazione.py`, `assistente/varianti.py`, `assistente/avvio.py`, `.env.example`, `tests/test_configurazione.py`, `tests/test_varianti.py`, `tests/test_avvio_unico.py`

**Interfaces:**
- Produces:
  - `Configurazione.variante_scadenze: str = "mcp"`, `Configurazione.porta_api: int | None = None`;
  - `VARIANTI_SCADENZE = ("mcp", "fastapi")`;
  - `crea_sostituti(config, *, url_api: str | None = None)`;
  - `prepara_strumenti(config, log_server=LOG_SERVER, log_api=LOG_API)`.

- [ ] **Step 1: test**
  - **Configurazione:**
    - `VARIANTE_SCADENZE` mancante compare tra le mancanti;
    - un valore non ammesso dà un messaggio con `Valori ammessi: mcp, fastapi`;
    - con `fastapi` e senza `API_PORTA`, il messaggio nomina `API_PORTA`;
    - `API_PORTA` uguale a `MCP_PORTA` dà `API_PORTA deve essere diversa da MCP_PORTA.`;
    - con `mcp`, `API_PORTA` è ignorata anche se non è valida.
  - **Avvio unico:**
    - `test_variante_fastapi`: con `VARIANTE_SCADENZE=fastapi` e una porta libera, il modello finto fa una chiamata `calcola_scadenza` con l'esempio della specifica. Si verifica che:
      - compaiano `calcola_scadenza (fastapi)` e `[calcola_scadenza · fastapi: 2026-12-23, 3, True]`;
      - `LOG_API` contenga `endpoint=/scadenza`;
      - `LOG_ASSISTENTE` contenga `origine=fastapi tool=calcola_scadenza`;
      - `LOG_SERVER` non contenga `tool=calcola_scadenza`;
      - i due processi siano terminati;
    - `test_servizio_che_non_parte_spegne_tutto`: con `API_PORTA` occupata, `main() == 1`, lo stderr contiene `API_PORTA` e il server MCP registrato è terminato.
- [ ] **Step 2:** i test indicati. Atteso: FAIL sui nuovi test.
- [ ] **Step 3: implementare.**
  - `prepara_strumenti` usa un `ExitStack`: prima il server MCP; poi, se la variante è `fastapi`, `avvia_servizio_api(config.porta_api, log_api)`; infine `seleziona_strumenti(remoti, crea_sostituti(config, url_api=...))`.
  - Nel log: `varianti calcolatrice=<v> scadenze=<v>`.
  - In `.env.example`: `VARIANTE_SCADENZE=mcp` e `API_PORTA=8766`, commentati.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(varianti): scegli la variante delle scadenze e avvia il servizio FastAPI`.

---

### Task 7: prove reali, documentazione e checkpoint

**Files:**
- Create: `tests/test_reale_scadenze.py`, `docs/superpowers/checkpoint/AAAA-MM-GG-scadenze.md`
- Modify: `README.md`, `../CLAUDE.md` (struttura: `servizio_api/`, `risorse/`, `wrapper_scadenze.py`), `Dockerfile` (`COPY servizio_api/ servizio_api/` e `COPY risorse/ risorse/`). Senza queste due righe l'immagine si rompe dal passo 4, quando il server legge `risorse/` all'avvio. La prova Docker completa resta al passo 7.

- [ ] **Step 1: controllare il `.env` reale.** Se mancano `VARIANTE_SCADENZE` o `API_PORTA`, chiedere all'utente di aggiungerle.
- [ ] **Step 2: scrivere `tests/test_reale_scadenze.py`**, parametrizzato su `("mcp", "fastapi")`, con `ambiente_reale({"VARIANTE_SCADENZE": v})`.
  - **Domanda «Se parto il 23 dicembre 2026, quando scadono 3 giorni lavorativi?»**:
    - l'ultima chiamata a `calcola_scadenza` ha argomenti `("2026-12-23", 3, True)` e un ToolMessage `success` con `scadenza == "2026-12-29"`;
    - la risposta contiene `29`;
    - nel log compare `origine=<v> tool=calcola_scadenza`;
    - con `fastapi`, `logs/servizio_api.log` guadagna una riga `endpoint=/scadenza`.
  - **Errore controllato**: invocazione diretta con `data_inizio="2026-02-30"`. Il risultato ha `tipo == "strumento"` e non ha `scadenza`.
- [ ] **Step 3:** `python -m pytest -q`, poi `python -m pytest --lmstudio -m lmstudio -v -s`. Stessa regola di fallimento dei passi precedenti.
- [ ] **Step 4: README**, con:
  - le variabili `VARIANTE_SCADENZE` e `API_PORTA`;
  - l'avvio del solo servizio, `python -m servizio_api --porta 8766`, con `http://127.0.0.1:8766/docs` (comando verificato);
  - il file delle festività e gli anni coperti;
  - la diagnosi del servizio FastAPI: processo, porta, `/openapi.json`, timeout del wrapper.
- [ ] **Step 5: checkpoint** con **Fatto**, **Da fare** (passo 4) e **Stato attuale**.
- [ ] **Step 6:** commit `test(reale): prove reali delle scadenze nelle varianti MCP e FastAPI e documentazione`.
- [ ] **Step 7:** **chiedere all'utente l'approvazione esplicita** per unire `dev-scadenze` in `main`.
