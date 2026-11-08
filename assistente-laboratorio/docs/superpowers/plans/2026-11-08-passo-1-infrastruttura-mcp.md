# Passo 1 — Infrastruttura MCP, convertitore e orologio spostato — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un server MCP («Strumenti laboratorio») con `converti_unita` e `ora_corrente`, avviato, scoperto, usato e spento dall'agente con un solo comando. Ogni chiamata è registrata con la sua `origine`, e nell'agente non resta nessuno strumento locale.

**Architecture:**
- **`logica/`:** un pacchetto di logica pura, che contiene orologio e conversioni.
- **`server_mcp/`:** registra la logica con FastMCP e la espone su Streamable HTTP, all'indirizzo `127.0.0.1`.
- **`assistente/`:**
  - avvia il server come processo separato;
  - scopre il catalogo e avvolge ogni tool in un ponte sincrono;
  - seleziona gli strumenti da passare al modello. È il punto in cui i passi 2 e 3 inseriranno le varianti;
  - registra ogni chiamata in `logs/assistente.log`.

**Tech Stack:** Python 3.14, LangGraph 1.2.19, langchain-core 1.7.3, `fastmcp` 3.4.11, `langchain-mcp-adapters` 0.3.2, `mcp` 1.30.0, pytest 9.2.0, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-08-strumenti-lezione-5-design.md` (sezioni 5.1, 5.2, 6, 7, 8 e 12, passo 1). È da leggere insieme a `docs/superpowers/specs/2026-11-03-convertitore-unita-mcp-design.md`, che resta valida per l'infrastruttura.

**Piano di riferimento:** `docs/superpowers/plans/2026-11-03-convertitore-unita-mcp.md`. I suoi Task 2–8 sono **sostituiti** da questo piano, ma il loro codice di test e i dettagli di implementazione restano validi dove questo piano dice «come nel Task N del piano 2026-11-03». Le differenze sono elencate in ogni task.

**Branch:** `dev-infrastruttura-mcp`, creato da `dev`.

## Global Constraints

Valgono anche per i passi 2–7: ogni piano successivo li richiama.

- Tutti i percorsi sono relativi a `assistente-laboratorio/`. I comandi si eseguono da lì con `.venv/Scripts/python.exe`, abbreviato sotto in `python`.
- **Git:**
  - un branch per passo, `dev-<passo>`, creato da `dev`. Se il passo precedente non è ancora unito in `main`, il branch parte dal branch del passo precedente;
  - Conventional Commits in italiano, staging selettivo dei soli file del task, **nessuna riga `Co-Authored-By`**;
  - nessun push e **nessun merge in `main` senza l'approvazione esplicita dell'utente**.
- **Checkpoint:** a fine passo, e a ogni interruzione, scrivere `docs/superpowers/checkpoint/AAAA-MM-GG-<passo>.md` con tre sezioni (**Fatto**, **Da fare**, **Stato attuale**), da committare con il lavoro.
- **Versioni fissate** in `requirements.txt`, risolte il 2026-11-08 con `pip --dry-run` su Python 3.14.7 senza conflitti. Nessun'altra dipendenza.

  | Pacchetto | Versione | Passo |
  |---|---|---|
  | `fastmcp` | 3.4.11 | 1 |
  | `langchain-mcp-adapters` | 0.3.2 | 1 |
  | `mcp` | 1.30.0 | 1 |
  | `httpx` | 0.28.1 | 3 |
  | `fastapi` | 0.162.2 | 3 |
  | `uvicorn` | 0.54.0 | 3 |
- **Codice sincrono** ovunque, tranne dentro `assistente/client_mcp.py`, che usa `asyncio.run`.
- **Server MCP:**
  - solo su `127.0.0.1`, percorso `/mcp`, URL `http://127.0.0.1:<porta>/mcp`;
  - nome `Strumenti laboratorio`;
  - espone sempre tutti i suoi strumenti, qualunque sia la configurazione dell'agente.
- **Tempi:**
  - attesa di avvio di un processo: 10 s;
  - timeout di ogni chiamata MCP: 10 s;
  - attesa di arresto: 5 s, poi arresto forzato.
- **`origine`** nei metadati di ogni tool e nei log: `mcp`, `locale` o `fastapi`.
- **Esiti nel log:** `ok`, `errore_tool`, `errore_collegamento`, `strumento_sconosciuto`, `limite`.
- **Errori di uno strumento:**
  - nella logica pura sono un `logica.errori.ErroreStrumento`, con messaggio in italiano;
  - nel server MCP diventano un `ToolError`;
  - nell'agente arrivano come `{"errore": "...", "tipo": "strumento"|"collegamento"}`, sempre senza risultato.
- **Messaggi all'utente** in italiano. Gli errori di avvio sono senza traceback e con codice di uscita 1.
- **Log** in `logs/`, in UTF-8 e in coda, con la cartella esclusa da Git e dall'immagine Docker.
- **Fatti verificati** nel prototipo del 2026-11-03, da non riscoprire: sono elencati nei Global Constraints del piano 2026-11-03 (tool dell'adattatore solo asincroni, `ToolException` con `handle_tool_errors=False`, `ExceptionGroup` con server spento, `CTRL_BREAK_EVENT` su Windows, argomenti `run` silenziosi, `Annotated[Any, WithJsonSchema(...)]`).

## Review Focus

1. **Ctrl+C durante l'attesa dell'avvio:** il server viene spento lo stesso. Lo verifica il Task 4 (`test_ctrl_c_durante_l_avvio_spegne_il_server`).
2. **`°C` e `à` nei log su Windows:** il processo figlio parte con `PYTHONUTF8=1` e i log si rileggono in UTF-8. Lo verifica il Task 4 (`test_log_del_server_in_utf8`).
3. **Nessun output del server nel terminale della chat.** Lo verifica il Task 4 (`test_nessun_output_nel_terminale`).
4. **Fuso inesistente dopo lo spostamento dell'orologio:** `Mars/Olympus` dà un errore MCP con il messaggio di oggi, non un risultato con dentro `"errore"`, e nel terminale non compare una riga di successo. Lo verificano il Task 2 (`test_orologio_fuso_sconosciuto`) e il Task 6 (`test_strumento_fallito_non_stampa`).
5. **`.env` vecchio senza `MCP_PORTA`:** l'avvio fallisce con un messaggio che nomina la variabile, non con un traceback. Lo verifica il Task 6 (`test_porta_mancante`).

---

### Task 0: branch

- [ ] **Step 1:** `git switch dev`, poi `git switch -c dev-infrastruttura-mcp`. Atteso: `git status` pulito, tranne `../.gitattributes`, che non si tocca.

---

### Task 1: pacchetto di logica pura (orologio e conversioni)

**Files:**
- Create: `logica/__init__.py` (solo docstring), `logica/errori.py`, `logica/orologio.py`
- Move: `server_mcp/conversioni.py` → `logica/conversioni.py`, con `git mv`; `server_mcp/__init__.py` resta
- Modify: `logica/conversioni.py` (`ErroreConversione` deriva da `ErroreStrumento`), `assistente/fuso.py` (import), `assistente/strumenti.py` (delega a `logica.orologio`)
- Test: `tests/test_conversioni.py` (import), `tests/test_orologio.py` (nuovo)

**Interfaces:**
- Produces:
  - `logica.errori.ErroreStrumento(ValueError)`;
  - `logica.orologio`:
    - `GIORNI: tuple[str, ...]`;
    - `è_fuso_valido(nome: object) -> bool`;
    - `ora_utc() -> datetime`;
    - `ora_corrente(fuso: object, adesso: datetime) -> dict`, con le chiavi `fuso`, `data_ora`, `scarto_utc`, `giorno_settimana`;
  - `logica.conversioni`: invariato (`UNITA_AMMESSE`, `ErroreConversione`, `converti`).

- [ ] **Step 1: scrivere `tests/test_orologio.py`**
  - Portare da `tests/test_strumenti.py` i casi della logica (risultato, scarto, giorno della settimana, fusi non validi), riscritti su `ora_corrente(fuso, ISTANTE)`.
  - Un fuso non valido ora solleva un errore:

```python
@pytest.mark.parametrize("fuso", ["Mars/Olympus", "europe/rome", "", None, 3])
def test_fuso_non_valido(fuso):
    with pytest.raises(ErroreStrumento, match="Fuso orario sconosciuto"):
        ora_corrente(fuso, ISTANTE)

def test_errore_conversione_e_errore_strumento():
    assert issubclass(ErroreConversione, ErroreStrumento)
```

  - In `tests/test_conversioni.py` l'import diventa `from logica.conversioni import ...`.
- [ ] **Step 2:** `python -m pytest tests/test_orologio.py tests/test_conversioni.py -v`. Atteso: FAIL (`logica` assente).
- [ ] **Step 3: implementare**
  - `git mv server_mcp/conversioni.py logica/conversioni.py`.
  - In `logica/orologio.py`, la logica viene da `assistente/strumenti.py`. Il messaggio d'errore resta quello attuale: `Fuso orario sconosciuto: '{fuso}'. Usa un nome IANA, per esempio 'Europe/Rome'.`
  - `assistente/strumenti.py` resta per ora (lo rimuove il Task 6). `crea_strumento_orologio` chiama `ora_corrente` e trasforma `ErroreStrumento` in `{"errore": ...}` come oggi, così i test esistenti restano verdi.
  - `assistente/fuso.py` importa `è_fuso_valido` da `logica.orologio`.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `refactor(logica): separa la logica di orologio e conversioni in un pacchetto puro`.

---

### Task 2: server MCP con convertitore e orologio

Come il Task 2 del piano 2026-11-03, con queste differenze.

**Files:**
- Modify: `requirements.txt` (`fastmcp==3.4.11`, `langchain-mcp-adapters==0.3.2`, `mcp==1.30.0`)
- Create: `server_mcp/server.py`, `server_mcp/__main__.py`
- Test: `tests/test_server_mcp.py`

**Interfaces:**
- Consumes: `logica.conversioni`, `logica.orologio`, `ErroreStrumento` (Task 1).
- Produces:
  - `NOME_SERVER = "Strumenti laboratorio"`, `NOME_CONVERTITORE = "converti_unita"`, `NOME_OROLOGIO = "ora_corrente"`;
  - `esegui_registrato(nome: str, argomenti: dict, calcolo: Callable[[], dict]) -> dict`: esegue, scrive la riga di log e trasforma `ErroreStrumento` in `ToolError`. I passi 2–6 lo riusano per ogni nuovo strumento;
  - `crea_server(*, adesso: Callable[[], datetime] = ora_utc) -> FastMCP`. I passi 5 e 6 aggiungeranno altri argomenti solo per parola chiave;
  - il comando `python -m server_mcp --porta <int>`.

- [ ] **Step 1: scrivere i test.** Prendere i tre test del Task 2 del piano 2026-11-03, con `con_client(funzione, **opzioni)` che passa le opzioni a `crea_server`. Poi:
  - `test_catalogo` controlla `{s.name for s in strumenti} == {"converti_unita", "ora_corrente"}` e lo schema del convertitore come prima;
  - nuovi casi:

```python
def test_orologio_nel_catalogo():
    (orologio,) = [s for s in con_client(lambda c: c.list_tools()) if s.name == "ora_corrente"]
    assert orologio.inputSchema["required"] == ["fuso"] and "IANA" in orologio.description

def test_orologio_risultato():
    istante = datetime(2026, 11, 2, 14, 4, 5, tzinfo=timezone.utc)
    r = con_client(lambda c: c.call_tool("ora_corrente", {"fuso": "Asia/Tokyo"}), adesso=lambda: istante)
    assert r.structured_content == {"fuso": "Asia/Tokyo", "data_ora": "2026-11-02T23:04:05+09:00",
                                    "scarto_utc": "+09:00", "giorno_settimana": "lunedì"}

def test_orologio_fuso_sconosciuto():
    r = con_client(lambda c: c.call_tool("ora_corrente", {"fuso": "Mars/Olympus"}, raise_on_error=False))
    assert r.is_error and "Fuso orario sconosciuto: 'Mars/Olympus'" in r.content[0].text
```

- [ ] **Step 2:** `python -m pytest tests/test_server_mcp.py -v`. Atteso: FAIL.
- [ ] **Step 3: implementare `server_mcp/server.py`.**
  - Il convertitore è come nel piano 2026-11-03.
  - L'orologio ha il parametro `fuso: Annotated[Any, WithJsonSchema({"type": "string", "description": "Nome IANA del fuso, per esempio Europe/Rome o Asia/Tokyo"})]`.
  - La descrizione dell'orologio è esattamente il testo attuale di `DESCRIZIONE_OROLOGIO` in `assistente/strumenti.py`.
  - Le righe di log le scrive `esegui_registrato`, con il formato del piano 2026-11-03.
- [ ] **Step 4: implementare `server_mcp/__main__.py`** come nel piano 2026-11-03.
- [ ] **Step 5:** `python -m pip install -r requirements-dev.txt`, poi `python -m pip check` (atteso: `No broken requirements found.`), poi `python -m pytest -q` (atteso: tutti PASS).
- [ ] **Step 6:** commit `feat(server): esponi convertitore e orologio con un server FastMCP`.

---

### Task 3: ponte sincrono e selezione degli strumenti

Come il Task 3 del piano 2026-11-03, con una differenza: `unisci_strumenti` è sostituita da `seleziona_strumenti`, che vive in un modulo proprio, e gli errori di avvio hanno un'unica classe.

**Files:**
- Create: `assistente/errori.py`, `assistente/client_mcp.py`, `assistente/varianti.py`
- Test: `tests/test_client_mcp.py`, `tests/test_varianti.py`

**Interfaces:**
- Produces:
  - `assistente.errori.ErroreAvvio(Exception)`: tutti gli errori di avvio (porte, processi, catalogo, nomi duplicati, variabili);
  - `assistente.client_mcp`: `NOME_CONNESSIONE = "laboratorio"`, `TIMEOUT_CHIAMATA = 10.0`, `TIPO_STRUMENTO = "strumento"`, `TIPO_COLLEGAMENTO = "collegamento"`, `ORIGINE_MCP = "mcp"`, `avvolgi(strumento, timeout=TIMEOUT_CHIAMATA) -> BaseTool`, `scopri_strumenti(url, timeout_scoperta=TIMEOUT_CHIAMATA) -> list[BaseTool]`;
  - `assistente.varianti`:
    - `seleziona_strumenti(remoti: list[BaseTool], sostituti: Sequence[BaseTool] = ()) -> list[BaseTool]`: toglie dai remoti ogni tool con lo stesso nome di un sostituto, poi aggiunge i sostituti in coda; con nomi ancora duplicati solleva `ErroreAvvio`;
    - `origini(strumenti: Sequence[BaseTool]) -> dict[str, str]`: da nome a `metadata["origine"]`, con `"locale"` se manca.

- [ ] **Step 1: scrivere i test**
  - `tests/test_client_mcp.py`: i primi tre test del Task 3 del piano 2026-11-03, cioè contratto, errori e timeout, senza `test_unisci_e_conflitto`.
  - `tests/test_varianti.py`:

```python
def tool(nome, origine):
    return StructuredTool.from_function(lambda: "", name=nome, description="d", metadata={"origine": origine})

def test_senza_sostituti():
    remoti = [tool("ora_corrente", "mcp"), tool("converti_unita", "mcp")]
    assert seleziona_strumenti(remoti) == remoti

def test_sostituto_prende_il_posto_della_versione_mcp():
    scelti = seleziona_strumenti([tool("calcola", "mcp"), tool("ora_corrente", "mcp")], [tool("calcola", "locale")])
    assert origini(scelti) == {"ora_corrente": "mcp", "calcola": "locale"} and len(scelti) == 2

def test_nomi_duplicati():
    with pytest.raises(ErroreAvvio, match="ora_corrente"):
        seleziona_strumenti([tool("ora_corrente", "mcp"), tool("ora_corrente", "mcp")])
```

- [ ] **Step 2:** `python -m pytest tests/test_client_mcp.py tests/test_varianti.py -v`. Atteso: FAIL.
- [ ] **Step 3: implementare** `client_mcp.py` come nel piano 2026-11-03, poi `errori.py` e `varianti.py`. Il messaggio dei duplicati è: `Strumento '{nome}' presente due volte: ogni strumento deve arrivare al modello da una sola variante.`
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(mcp): aggiungi il ponte sincrono e la selezione degli strumenti`.

---

### Task 4: avvio, attesa e arresto di un processo

Come il Task 4 del piano 2026-11-03, con una differenza: il ciclo «porta libera → avvio → attesa → arresto» diventa generico, così il passo 3 lo riusa per il servizio FastAPI.

**Files:**
- Create: `assistente/avvio_server.py`, `tests/server_vuoto.py`
- Modify: `tests/conftest.py` (fixture `porta` e `popen_registrati`)
- Test: `tests/test_avvio_server.py`

**Interfaces:**
- Consumes: `scopri_strumenti` (Task 3), `ErroreAvvio` (Task 3).
- Produces:
  - `ATTESA_AVVIO = 10.0`, `ATTESA_ARRESTO = 5.0`, `CARTELLA_PROGETTO: Path`;
  - `porta_libera(porta: int) -> bool`;
  - `ultime_righe(percorso: Path, quante: int = 10) -> str`;
  - `ferma(processo, attesa=ATTESA_ARRESTO) -> None`;
  - `@contextmanager processo_in_attesa(comando: list[str], porta: int, percorso_log: Path, prova: Callable[[float], T], *, descrizione: str, variabile_porta: str, attesa: float = ATTESA_AVVIO) -> Iterator[tuple[subprocess.Popen, T]]`. `prova(tempo_massimo)` restituisce un valore quando il processo è pronto, altrimenti solleva un'eccezione;
  - `url_server(porta: int) -> str`;
  - `@dataclass(frozen=True) ServerAvviato(processo, url: str, strumenti: list[BaseTool])`;
  - `@contextmanager avvia_server_mcp(porta, percorso_log, attesa=ATTESA_AVVIO, comando=None) -> Iterator[ServerAvviato]`;
  - logger `assistente.avvio`.

- [ ] **Step 1: scrivere i test** del Task 4 del piano 2026-11-03, con queste differenze:
  - `ErroreServerMCP` diventa `ErroreAvvio`;
  - in `test_ciclo_completo` gli strumenti sono due: si cerca `converti_unita` per nome, e `ora_corrente` con `{"fuso": "Asia/Tokyo"}` restituisce un JSON con `"fuso": "Asia/Tokyo"`;
  - nuovo test generico:

```python
def test_processo_in_attesa_messaggi_parametrizzati(porta, tmp_path):
    comando = [sys.executable, "-c", "import sys; sys.exit(3)"]
    with pytest.raises(ErroreAvvio, match="Il servizio prova non è partito"):
        with processo_in_attesa(comando, porta, tmp_path / "p.log", lambda t: None,
                                descrizione="servizio prova", variabile_porta="PROVA_PORTA"): pass
```

- [ ] **Step 2:** `python -m pytest tests/test_avvio_server.py -v`. Atteso: FAIL.
- [ ] **Step 3: implementare** come nel piano 2026-11-03, con i messaggi parametrizzati:
  - `Porta {porta} già in uso: chiudi il programma che la usa o cambia {variabile_porta} nel .env.`;
  - `Il {descrizione} non è partito (porta {porta}). Ultime righe di {percorso_log}:\n…`.

  `avvia_server_mcp` usa `descrizione="server MCP"`, `variabile_porta="MCP_PORTA"` e una `prova` che chiama `scopri_strumenti`. Un catalogo vuoto dà `Il server MCP non espone nessuno strumento.`
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(mcp): avvia, attendi e spegni il server MCP`.

---

### Task 5: registro delle chiamate e grafo

Come il Task 5 del piano 2026-11-03, con queste differenze:
- **`finti.py`** guadagna `chiamata(nome: str, argomenti: dict, id: str = "c1") -> AIMessage`, generica, e `strumento_finto(risposta: str, nome: str = "converti_unita", origine: str = "mcp") -> BaseTool`.
- **Messaggio di sistema.** Mantiene la regola su `ora_corrente`, che resta nominato, e guadagna la riga del piano 2026-11-03 sui calcoli. Il test `test_testi_generici` resta valido.
- **Nessun test dell'orologio locale**: `test_errore_orologio_marcato` diventa `test_errore_strumento_marcato`, con `strumento_finto('{"errore": "Fuso orario sconosciuto", "tipo": "strumento"}', nome="ora_corrente")`, e si aspetta `status == "error"`, `origine=mcp` ed `esito=errore_tool`.

**Interfaces:**
- Produces:
  - `registro.CARTELLA_LOG`, `LOG_ASSISTENTE`, `LOG_SERVER`;
  - `configura_registro(percorso=LOG_ASSISTENTE)`;
  - `formatta(campi)`;
  - logger `assistente.strumenti`.

- [ ] **Step 1:** test di `registro.py` e del grafo, come nel piano 2026-11-03 con le differenze sopra.
- [ ] **Step 2:** `python -m pytest tests/test_registro.py tests/test_grafo.py -v`. Atteso: FAIL sui nuovi test.
- [ ] **Step 3:** implementare `registro.py` e le modifiche a `grafo.py`. `grafo.py` non importa più nulla da `assistente.strumenti`: il nome `ora_corrente` è una costante locale `NOME_OROLOGIO`.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(grafo): registra ogni chiamata con la sua origine`.

---

### Task 6: configurazione, terminale, avvio unico e rimozione dell'orologio locale

Come il Task 6 del piano 2026-11-03, con queste differenze:
- **Riga del terminale uniforme** per ogni strumento, invece di `[convertitore: …]`.
- **Strumenti preparati in un modulo proprio**, riusato dalle prove reali.
- **Orologio locale rimosso.**

**Files:**
- Create: `assistente/avvio.py`, `tests/reale.py`, `tests/test_avvio_unico.py`
- Modify: `assistente/configurazione.py`, `assistente/terminale.py`, `assistente/__main__.py`, `.env.example`, `.gitignore` (`logs/`), `tests/test_configurazione.py`, `tests/test_modello.py:67`, `tests/test_terminale.py`, `tests/test_reale_lmstudio.py`
- Delete: `assistente/strumenti.py`, `tests/test_strumenti.py` (i casi sono già in `tests/test_orologio.py`)

**Interfaces:**
- Consumes: `avvia_server_mcp` (Task 4), `seleziona_strumenti` e `origini` (Task 3), `configura_registro`, `LOG_SERVER` e `strumento_finto` (Task 5).
- Produces:
  - `Configurazione(base_url: str, modello: str, porta_mcp: int)`. I passi 2 e 3 aggiungono campi con un valore predefinito nel dataclass, ma restano obbligatori nell'ambiente;
  - `@contextmanager assistente.avvio.prepara_strumenti(config: Configurazione, log_server: Path = LOG_SERVER) -> Iterator[list[BaseTool]]`, che avvia i processi necessari, seleziona gli strumenti e spegne tutto all'uscita. È costruito su `contextlib.ExitStack`, perché il passo 3 ci aggiungerà il servizio FastAPI;
  - `esegui_sessione(grafo, fuso, leggi=input, scrivi=print, origini: Mapping[str, str] | None = None)`;
  - `tests.reale.ambiente_reale(variabili: Mapping[str, str] | None = None)`: un context manager che restituisce `(grafo, fuso_utente, strumenti)`, dopo aver applicato `variabili` all'ambiente, letto `.env` e la configurazione, verificato LM Studio, aperto `prepara_strumenti`, configurato il registro e creato modello e grafo.

- [ ] **Step 1: scrivere i test**
  - **Configurazione e avvio unico:** come nel piano 2026-11-03. `test_avvio_completo` controlla che la riga `Strumenti: ` contenga `ora_corrente (mcp)` e `converti_unita (mcp)`. `crea_modello` nel monkeypatch riceve gli strumenti selezionati.
  - **Terminale:** `sessione()` costruisce il grafo con `strumento_finto` al posto dell'orologio locale. I test che usavano `chiamata_orologio` restano, con `strumento_finto('{"fuso": "Asia/Tokyo", ...}', nome="ora_corrente")`. Poi:

```python
def test_riga_con_variante():      # chiamata("converti_unita", {"valore": 2.5, "da": "km", "a": "m"}), AIMessage("2500 m")
    # origini={"converti_unita": "mcp"} → "[converti_unita · mcp: 2.5, km, m]" stampata prima di "Assistente: 2500 m"
def test_strumento_fallito_non_stampa():   # strumento_finto('{"errore": "x", "tipo": "strumento"}') → nessuna riga che inizia con "["
def test_benvenuto_con_strumenti():        # origini={"ora_corrente": "mcp", "calcola": "locale"} → "Strumenti: ora_corrente (mcp), calcola (locale)"
```

  - `tests/test_reale_lmstudio.py` usa `ambiente_reale()` e cerca lo strumento per nome `"ora_corrente"`, non più `NOME_OROLOGIO` da `assistente.strumenti`.
- [ ] **Step 2:** `python -m pytest tests/test_configurazione.py tests/test_terminale.py tests/test_avvio_unico.py -v`. Atteso: FAIL sui nuovi test.
- [ ] **Step 3: implementare**
  - **Configurazione:** come nel piano 2026-11-03. `ErroreConfigurazione` resta.
  - **Riga del terminale:** `f"[{nome} · {origine}: {valori}]"`, dove `valori` è `", ".join(str(v) for v in argomenti.values())`. Si stampa solo per i ToolMessage con `status != "error"`, e `origine` viene da `origini`, con `?` se manca.
  - **Benvenuto:** subito dopo la riga del fuso, `Strumenti: ` seguito da `nome (origine)` separati da `, `.
  - **`__main__.py`:**
    1. `load_dotenv`;
    2. `carica_configurazione`;
    3. `configura_registro`;
    4. `verifica_server`;
    5. `rileva_fuso`;
    6. `with prepara_strumenti(config) as strumenti:`, poi `crea_modello`, `crea_grafo` ed `esegui_sessione(..., origini=origini(strumenti))`.

    `ErroreAvvio` si aggiunge alle eccezioni che stampano `Errore: …` e restituiscono 1.
  - Rimuovere `assistente/strumenti.py` e `tests/test_strumenti.py`, poi controllare che nessun file importi `assistente.strumenti`: `git grep -n "assistente.strumenti"` deve dare zero risultati.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS, prove reali `skipped`.
- [ ] **Step 5:** commit `feat(avvio): avvia agente e server MCP con un solo comando e sposta l'orologio nel server`.

---

### Task 7: prove reali e Docker minimo

Come il Task 7 del piano 2026-11-03, con queste differenze.

**Files:**
- Modify: `Dockerfile` (`COPY logica/ logica/` e `COPY server_mcp/ server_mcp/` dopo `assistente/`), `compose.yaml` (`volumes: ["./logs:/app/logs"]`), `.dockerignore` (`logs`), `tests/test_reale_docker.py`
- Create: `tests/test_reale_convertitore.py`

- [ ] **Step 1: controllare il `.env` reale.** Se manca `MCP_PORTA`, chiedere all'utente di aggiungere `MCP_PORTA=8765`: il `.env` è suo. Verificare anche che LM Studio e Docker Desktop siano accesi.
- [ ] **Step 2:** `tests/test_reale_convertitore.py` con i 5 `CASI`, il criterio e `forme_del_numero` del piano 2026-11-03, ma con la fixture costruita su `ambiente_reale()`. Si aggiunge il controllo che la riga in `logs/assistente.log` contenga `origine=mcp tool=converti_unita`.
- [ ] **Step 3:** in `tests/test_reale_lmstudio.py`, un controllo in più per ogni caso dell'orologio: nel log compare `origine=mcp tool=ora_corrente`. Poi l'**errore controllato** (slide 23), cioè un'invocazione diretta senza modello:

```python
def test_errore_controllato_orologio(ambiente):
    _, _, strumenti = ambiente
    errore = json.loads(next(s for s in strumenti if s.name == "ora_corrente").invoke({"fuso": "Mars/Olympus"}))
    assert errore["tipo"] == "strumento" and "Fuso orario sconosciuto" in errore["errore"] and "data_ora" not in errore
```

- [ ] **Step 4:** in `tests/test_reale_docker.py`, `test_convertitore_in_docker` con la domanda `"Quanti metri sono 2,5 km?\nesci\n"`:
  - in stdout compaiono `converti_unita (mcp)` e `[converti_unita · mcp:`;
  - i log sull'host contengono `tool=converti_unita`.
- [ ] **Step 5:** `python -m pytest -q`. Atteso: tutti PASS, prove reali `skipped`.
- [ ] **Step 6:** `python -m pytest --lmstudio -m lmstudio -v -s`. Atteso: PASS per i casi del convertitore e dell'orologio. Se un caso fallisce: al massimo due ritocchi alla descrizione o al messaggio di sistema, poi ci si ferma e si riporta l'esito con le chiamate stampate. **Il modello lo cambia l'utente.**
- [ ] **Step 7:** `python -m pytest --docker -m docker -v -s`. Atteso: tutti PASS.
- [ ] **Step 8:** commit `test(reale): prove reali di convertitore e orologio via MCP, anche in Docker`.

---

### Task 8: documentazione, checkpoint e richiesta di merge

**Files:**
- Modify: `README.md`, `../CLAUDE.md`
- Create: `docs/superpowers/checkpoint/AAAA-MM-GG-infrastruttura-mcp.md`

- [ ] **Step 1: README**, come nel Task 8 del piano 2026-11-03, con la riga `Strumenti: …` e la nuova riga del terminale. Solo i comandi eseguiti con successo nei Task 6 e 7.
- [ ] **Step 2: `../CLAUDE.md`, sezione «Struttura e comandi»:**
  - `logica/`, `server_mcp/`, `assistente/` con `client_mcp.py`, `varianti.py`, `avvio_server.py`, `avvio.py`, `registro.py` ed `errori.py`;
  - `logs/`;
  - senza `strumenti.py`.

  Nelle «Scelte tecniche»: il codice è sincrono, tranne il ponte MCP.
- [ ] **Step 3: checkpoint** con tre sezioni:
  - **Fatto:** i task, con commit ed esiti;
  - **Da fare:** il passo 2 e quello che non è verificato;
  - **Stato attuale:** branch `dev-infrastruttura-mcp`, ultimo commit, esito di `pytest -q` e delle prove reali, con l'elenco dei casi.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `docs: documenta l'infrastruttura MCP e aggiungi il checkpoint del passo 1`.
- [ ] **Step 6:** **chiedere all'utente l'approvazione esplicita** per unire `dev-infrastruttura-mcp` in `main`. Senza un «sì» per questo passo non si unisce nulla.
