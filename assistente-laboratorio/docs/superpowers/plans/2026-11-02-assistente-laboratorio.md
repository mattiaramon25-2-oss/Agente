# Assistente del laboratorio — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** assistente da terminale in Python che chatta con un modello di LM Studio tramite un grafo LangGraph esplicito, con uno strumento orologio a fuso esplicito e avvio anche con Docker Compose.

**Architecture:** pacchetto `assistente/` con moduli piccoli: configurazione, fuso, strumenti, modello (collegamento a LM Studio), grafo (stato, nodi `modello`/`strumenti`/`limite`, instradamento), terminale (ciclo di chat), `__main__` (composizione). Il grafo riceve un modello già collegato agli strumenti, così i test usano un modello finto. La cronologia vive in una lista tenuta dal terminale e passata al grafo a ogni turno; nessun checkpointer.

**Tech Stack:** Python 3.14 · langgraph 1.2.19 · langchain-openai 1.7.3 · langchain-core 1.7.3 · tzlocal 5.4.5 · tzdata 2026.6 · python-dotenv 1.2.4 · pytest 9.2.0 · Docker Compose.

**Spec:** `assistente-laboratorio/docs/superpowers/specs/2026-11-02-assistente-laboratorio-design.md` (leggerla insieme a questo piano) e `CLAUDE.md` alla radice della repository.

## Global Constraints

- Tutti i file del progetto dentro `assistente-laboratorio/`; non toccare altre cartelle (unica eccezione: `CLAUDE.md` alla radice, nel Task 8).
- Tutti i comandi di questo piano si eseguono da `assistente-laboratorio/`, con l'ambiente virtuale `.venv` attivo (PowerShell: `.\.venv\Scripts\Activate.ps1`).
- Codice sincrono, nessun `async`.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente: `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`, `LMSTUDIO_BASE_URL_DOCKER`; fuso: `FUSO_ORARIO`, `FUSO_HOST_WINDOWS`, `ASSISTENTE_IN_DOCKER`. Nessun indirizzo né id di modello nel codice o in `compose.yaml`.
- Dipendenze solo quelle elencate sopra, con `==`. Nessun'altra senza accordo con l'utente.
- Niente agenti prefabbricati di LangGraph (`create_react_agent` e simili) né `ToolNode`: nodi e instradamento scritti nel nostro codice.
- Testi rivolti all'utente e messaggio di sistema in italiano.
- Commit: Conventional Commits in italiano; prima di ogni commit `git status`, `git diff --cached`, staging solo dei file del task. Mai `.env`, `.venv`, cache. Ogni messaggio di commit termina con la riga `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Nessun push.
- Test automatici: `python -m pytest` deve passare senza LM Studio né Docker. Le prove reali partono solo con `--lmstudio` o `--docker`.
- README: solo comandi effettivamente eseguiti e verificati.

## Review Focus

1. Il modello chiede uno strumento inesistente o con argomenti sbagliati (manca `fuso`, tipo errato): il nodo strumenti risponde con un messaggio di errore, nessun crash. → Task 3, `test_strumento_sconosciuto_e_argomenti_errati`.
2. Nomi di fuso strani dal modello (`"Roma"`, `""`, `"../../etc/passwd"`, `"europe/rome"`): errore leggibile, mai eccezione. → Task 1, `test_fusi_non_validi`.
3. `Ctrl+C` mentre si aspetta la risposta (lenta) del modello: uscita pulita, senza traceback. → Task 5, `test_ctrl_c_durante_la_risposta`.
4. Il modello risponde con testo vuoto (capita con i modelli piccoli): il terminale mostra un segnaposto, non una riga vuota. → Task 5, `test_risposta_vuota`.
5. `LMSTUDIO_BASE_URL` scritto con la barra finale (`http://localhost:1234/v1/`): la verifica all'avvio funziona lo stesso. → Task 4, `test_barra_finale_nell_indirizzo`.

---

### Task 1: Struttura del progetto e strumento orologio

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `pytest.ini`, `tests/conftest.py`, `assistente/__init__.py`, `assistente/strumenti.py`
- Test: `tests/test_strumenti.py`

**Interfaces:**
- Produces:
  - `NOME_OROLOGIO = "ora_corrente"`
  - `crea_strumento_orologio(adesso: Callable[[], datetime] = <ora UTC attuale>) -> BaseTool` — strumento LangChain con un solo argomento `fuso: str`; `.invoke({"fuso": ...})` restituisce una **stringa JSON**.
  - `è_fuso_valido(nome: str) -> bool` (usato anche dal Task 2).
  - Marcatori pytest `lmstudio` e `docker`, opzioni `--lmstudio` e `--docker`.

- [ ] **Step 1: Ambiente e file di base**

`requirements.txt`:
```
langgraph==1.2.19
langchain-openai==1.7.3
langchain-core==1.7.3
tzlocal==5.4.5
tzdata==2026.6
python-dotenv==1.2.4
```
`requirements-dev.txt`: `-r requirements.txt` e `pytest==9.2.0`.
`.gitignore`: `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`.
`pytest.ini`: `testpaths = tests`, `pythonpath = .`, marcatori `lmstudio: prova reale con LM Studio` e `docker: prova reale con Docker`.
`tests/conftest.py`: aggiunge le opzioni `--lmstudio` e `--docker` (`action="store_true"`); in `pytest_collection_modifyitems` salta i test marcati se l'opzione corrispondente manca, con motivo `"prova reale: usare --lmstudio"` / `"--docker"`.

Run (PowerShell):
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```
Expected: installazione senza errori.

- [ ] **Step 2: Test che falliscono** — `tests/test_strumenti.py`, istante fisso `ISTANTE = datetime(2026, 11, 2, 14, 4, 5, tzinfo=timezone.utc)` (lunedì)

```python
def test_ora_a_roma():          # json.loads(orologio.invoke({"fuso": "Europe/Rome"}))
    assert r == {"fuso": "Europe/Rome", "data_ora": "2026-11-02T15:04:05+01:00",
                 "scarto_utc": "+01:00", "giorno_settimana": "lunedì"}
def test_ora_a_tokyo():         # data_ora == "2026-11-02T23:04:05+09:00", scarto_utc == "+09:00"
def test_ora_a_new_york():      # data_ora == "2026-11-02T09:04:05-05:00" (ora solare già in vigore)
def test_ora_legale():          # adesso = 2026-07-01T12:00Z, Europe/Rome → "2026-07-01T14:00:00+02:00"
def test_fusi_non_validi():     # per "Roma", "", "../../etc/passwd", "europe/rome":
    assert set(r) == {"errore"} and "Europe/Rome" in r["errore"]   # il messaggio suggerisce il formato IANA
def test_nome_e_argomenti():
    assert orologio.name == "ora_corrente"
    assert list(orologio.args) == ["fuso"]
def test_è_fuso_valido():       # True: "Europe/Rome", "UTC"; False: "Roma", "", "../x"
```
Nota su `"europe/rome"`: su Windows `zoneinfo` può accettarlo (file system senza maiuscole); `è_fuso_valido` deve rifiutarlo comunque, controllando che il nome sia in `zoneinfo.available_timezones()`.

- [ ] **Step 3: Verifica che falliscano**

Run: `python -m pytest tests/test_strumenti.py -v`
Expected: FAIL (`ModuleNotFoundError: assistente.strumenti`).

- [ ] **Step 4: Implementare `assistente/strumenti.py`**

`crea_strumento_orologio` costruisce lo strumento con `langchain_core.tools.tool` (o `StructuredTool.from_function`) attorno a una funzione interna `ora_corrente(fuso: str) -> str`. Descrizione dello strumento in italiano: «Restituisce data e ora attuali nel fuso orario indicato. `fuso`: nome IANA, per esempio "Europe/Rome" o "Asia/Tokyo".» Giorni della settimana da una tupla italiana fissa (non dipendere dalla lingua del sistema). Errore: `{"errore": "Fuso orario sconosciuto: '<nome>'. Usa un nome IANA, per esempio 'Europe/Rome'."}`. JSON con `ensure_ascii=False`.

- [ ] **Step 5: Verifica che passino**

Run: `python -m pytest -v`
Expected: tutti PASS.

- [ ] **Step 6: Commit** — `feat(strumenti): aggiungi struttura del progetto e strumento orologio`

---

### Task 2: Configurazione e rilevamento del fuso

**Files:**
- Create: `assistente/configurazione.py`, `assistente/fuso.py`, `.env.example`
- Test: `tests/test_configurazione.py`, `tests/test_fuso.py`

**Interfaces:**
- Consumes: `è_fuso_valido` (Task 1).
- Produces:
  - `@dataclass(frozen=True) class Configurazione: base_url: str; modello: str`
  - `class ErroreConfigurazione(Exception)`
  - `carica_configurazione(env: Mapping[str, str]) -> Configurazione`
  - `@dataclass(frozen=True) class RisultatoFuso: fuso: str; origine: str; avviso: str | None` con `origine` in `"host Windows"`, `"computer locale"`, `"FUSO_ORARIO"`, `"ripiego"`.
  - `rileva_fuso(env: Mapping[str, str], fuso_locale: Callable[[], str | None] = <tzlocal.get_localzone_name>) -> RisultatoFuso`

- [ ] **Step 1: Test che falliscono**

`tests/test_configurazione.py`:
```python
def test_configurazione_completa():   # {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}
def test_variabili_mancanti():        # env {} → ErroreConfigurazione; il messaggio contiene
                                      # "LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL" e ".env.example"
def test_variabile_vuota():           # LMSTUDIO_MODEL="  " conta come mancante
```
`tests/test_fuso.py` (`fuso_locale` sempre iniettato; quello che non deve essere chiamato solleva `AssertionError`):
```python
def test_host_windows():              # FUSO_HOST_WINDOWS="W. Europe Standard Time"
    assert r == RisultatoFuso("Europe/Berlin", "host Windows", None)
def test_host_windows_tokyo():        # "Tokyo Standard Time" → "Asia/Tokyo"
def test_locale_fuori_da_docker():    # env {}, fuso_locale → "Europe/Rome" → origine "computer locale"
def test_docker_salta_il_locale():    # ASSISTENTE_IN_DOCKER="1", FUSO_ORARIO="Europe/Rome", fuso_locale non chiamato
    assert r.fuso == "Europe/Rome" and r.origine == "FUSO_ORARIO"
def test_host_windows_sconosciuto():  # FUSO_HOST_WINDOWS="Fuso Inventato", ASSISTENTE_IN_DOCKER="1", FUSO_ORARIO="Asia/Tokyo" → FUSO_ORARIO
def test_locale_fallisce():           # fuso_locale solleva Exception oppure restituisce None/"Roma" → si passa a FUSO_ORARIO
def test_ripiego_utc():               # ASSISTENTE_IN_DOCKER="1", FUSO_ORARIO="Roma" →
    assert r.fuso == "UTC" and r.origine == "ripiego"
    assert "avvia.ps1" in r.avviso and "FUSO_ORARIO" in r.avviso
```

- [ ] **Step 2: Verifica che falliscano** — `python -m pytest tests/test_configurazione.py tests/test_fuso.py -v` → FAIL (moduli assenti).

- [ ] **Step 3: Implementare** `configurazione.py` (valori con `.strip()`) e `fuso.py`: ordine esatto della spec 5.3; conversione Windows→IANA con `tzlocal.windows_tz.win_tz`; ogni candidato passa per `è_fuso_valido`; qualunque eccezione di `fuso_locale` vale come rilevamento fallito. `avviso` solo nel ripiego.

`.env.example`:
```
# Copia questo file in .env e adatta i valori. Nessuna credenziale necessaria.
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_BASE_URL_DOCKER=http://host.docker.internal:1234/v1
# Identificativo restituito da GET /v1/models
LMSTUDIO_MODEL=google/gemma-4-e2b
# Riserva manuale se il fuso non viene rilevato
FUSO_ORARIO=Europe/Rome
```

- [ ] **Step 4: Verifica che passino** — `python -m pytest -v` → tutti PASS.

- [ ] **Step 5: Commit** — `feat(configurazione): aggiungi configurazione e rilevamento del fuso`

---

### Task 3: Grafo

**Files:**
- Create: `assistente/grafo.py`, `tests/finti.py`
- Test: `tests/test_grafo.py`

**Interfaces:**
- Consumes: `crea_strumento_orologio`, `NOME_OROLOGIO` (Task 1).
- Produces:
  - `MAX_GIRI_STRUMENTO = 3`
  - `TESTO_LIMITE = "Non sono riuscito a completare la richiesta: troppe chiamate all'orologio. Prova a riformularla."`
  - `class StatoConversazione(TypedDict): messages: Annotated[list[AnyMessage], add_messages]; fuso_utente: str; giri_strumento: int`
  - `messaggio_sistema(fuso_utente: str) -> SystemMessage`
  - `instrada_dopo_modello(stato: StatoConversazione) -> Literal["strumenti", "limite", "__end__"]`
  - `crea_grafo(modello, strumenti: list[BaseTool]) -> CompiledStateGraph` — `modello` è qualunque oggetto con `.invoke(list[BaseMessage]) -> AIMessage`, già collegato agli strumenti. Nodi: `"modello"`, `"strumenti"`, `"limite"`. Archi: `START→modello`; `modello→instrada_dopo_modello`; `strumenti→modello`; `limite→END`.
  - `esegui_turno(grafo, cronologia: list[BaseMessage], fuso_utente: str, testo: str) -> list[BaseMessage]` — invoca il grafo con `cronologia + [HumanMessage(testo)]`, `giri_strumento=0`; restituisce la cronologia completa nuova. Non modifica la lista ricevuta.
  - `tests/finti.py`: `class ModelloFinto: __init__(self, risposte: list[AIMessage | Exception]); chiamate: list[list[BaseMessage]]; invoke(self, messaggi, config=None) -> AIMessage` (registra una copia dei messaggi, restituisce la risposta successiva o la solleva se è un'eccezione; `AssertionError` se finite). `chiamata_orologio(fuso: str, id: str = "c1") -> AIMessage` con contenuto vuoto e una `tool_call` a `ora_corrente`.

- [ ] **Step 1: Test che falliscono** — `tests/test_grafo.py` (orologio con istante fisso del Task 1)

```python
def test_messaggio_sistema():           # contiene "Europe/Rome" e "ora_corrente"
def test_instradamento():               # AIMessage senza tool_calls → "__end__";
                                        # con tool_calls e giri 0..2 → "strumenti"; giri 3 → "limite"
def test_risposta_diretta():            # ModelloFinto([AIMessage("Ciao!")]); cronologia finale == [Human, AI("Ciao!")];
                                        # la prima chiamata inizia con SystemMessage contenente il fuso;
                                        # nessun SystemMessage nella cronologia restituita
def test_ciclo_con_orologio():          # risposte: chiamata_orologio("Asia/Tokyo","c1"), AIMessage("Sono le 23:04.")
                                        # tipi cronologia: Human, AI(tool_calls), Tool, AI;
                                        # ToolMessage.tool_call_id == "c1", json del contenuto ha data_ora "2026-11-02T23:04:05+09:00";
                                        # la seconda chiamata al modello include il ToolMessage
def test_cronologia_tra_turni():        # due esegui_turno di fila: la seconda chiamata al modello vede
                                        # Human1, AI1, Human2; la lista del primo turno non è stata modificata
def test_limite_raggiunto():            # il modello chiede l'orologio 4 volte (c1..c4)
    # ultimo messaggio: AIMessage(TESTO_LIMITE); modello chiamato 4 volte;
    # ogni tool_call nella cronologia ha un ToolMessage con lo stesso id (anche c4)
def test_strumento_sconosciuto_e_argomenti_errati():
    # tool_calls: {"name": "meteo", "args": {}, "id": "x1"} e {"name": "ora_corrente", "args": {}, "id": "x2"}
    # poi AIMessage("ok") → nessuna eccezione; due ToolMessage con "errore" nel JSON
def test_giri_ripartono_a_ogni_turno(): # turno 1 usa 3 giri e risponde; turno 2 con 1 giro non va in "limite"
```

- [ ] **Step 2: Verifica che falliscano** — `python -m pytest tests/test_grafo.py -v` → FAIL.

- [ ] **Step 3: Implementare `assistente/grafo.py`**

- Nodo `modello`: `modello.invoke([messaggio_sistema(fuso), *stato["messages"]])` → `{"messages": [risposta]}`.
- Nodo `strumenti`: per ogni `tool_call` dell'ultimo `AIMessage` esegue lo strumento con quel nome; strumento sconosciuto o eccezione (anche di validazione degli argomenti) → `ToolMessage` con `{"errore": ...}`; restituisce i `ToolMessage` (con `tool_call_id` e `name`) e `giri_strumento + 1`.
- Nodo `limite`: un `ToolMessage` `{"errore": "limite di chiamate raggiunto"}` per ogni `tool_call` in sospeso, poi `AIMessage(TESTO_LIMITE)`.
- Messaggio di sistema (testo esatto lasciato a te, nel rispetto della spec 5.2): assistente utile; rispondi nella lingua dell'utente; per data e ora usa sempre lo strumento `ora_corrente` e non inventarle; il fuso dell'utente è `{fuso_utente}`, da usare quando non è indicato un altro luogo; per un luogo scegli il fuso IANA corrispondente.

- [ ] **Step 4: Verifica che passino** — `python -m pytest -v` → tutti PASS.

- [ ] **Step 5: Commit** — `feat(grafo): aggiungi grafo con nodi modello, strumenti e limite`

---

### Task 4: Collegamento a LM Studio

**Files:**
- Create: `assistente/modello.py`
- Test: `tests/test_modello.py`

**Interfaces:**
- Consumes: `Configurazione` (Task 2).
- Produces:
  - `class ErroreServer(Exception)`
  - `verifica_server(base_url: str, modello: str, leggi_json: Callable[[str, float], dict] = <GET HTTP con urllib>, timeout: float = 5.0) -> None`
  - `crea_modello(config: Configurazione, strumenti: list[BaseTool])` → `ChatOpenAI(model=config.modello, base_url=config.base_url, api_key="lm-studio", timeout=120, max_retries=1).bind_tools(strumenti)`. La chiave è un segnaposto: LM Studio non la controlla.

- [ ] **Step 1: Test che falliscono** (`leggi_json` finto che registra l'URL)

```python
def test_modello_presente():            # {"data": [{"id": "google/gemma-4-e2b"}]} → nessuna eccezione;
                                        # URL letto == "http://localhost:1234/v1/models"
def test_barra_finale_nell_indirizzo(): # base_url "http://localhost:1234/v1/" → stesso URL
def test_modello_assente():             # ErroreServer; messaggio contiene l'id cercato e "qwen/qwen3.5-9b" (gli id disponibili)
def test_server_irraggiungibile():      # leggi_json solleva urllib.error.URLError / TimeoutError / OSError
                                        # → ErroreServer che contiene l'URL e "LM Studio"
def test_risposta_malformata():         # {} oppure {"data": "x"} → ErroreServer
def test_crea_modello():                # nessuna rete: il risultato ha .invoke; il ChatOpenAI interno ha
                                        # model_name == "google/gemma-4-e2b" e openai_api_base == base_url;
                                        # tra i kwargs collegati c'è lo strumento "ora_corrente"
```

- [ ] **Step 2: Verifica che falliscano** — `python -m pytest tests/test_modello.py -v` → FAIL.
- [ ] **Step 3: Implementare `assistente/modello.py`** — l'HTTP predefinito usa `urllib.request.urlopen` + `json.load` (nessuna dipendenza nuova).
- [ ] **Step 4: Verifica che passino** — `python -m pytest -v` → tutti PASS.
- [ ] **Step 5: Verifica manuale con il server vero** (LM Studio acceso):
  `python -c "from assistente.modello import verifica_server; verifica_server('http://localhost:1234/v1', 'google/gemma-4-e2b'); print('ok')"` → `ok`; con id `'inventato'` → `ErroreServer` con l'elenco dei modelli.
- [ ] **Step 6: Commit** — `feat(modello): aggiungi verifica del server e client LM Studio`

---

### Task 5: Interfaccia da terminale e avvio

**Files:**
- Create: `assistente/terminale.py`, `assistente/__main__.py`
- Test: `tests/test_terminale.py`

**Interfaces:**
- Consumes: `esegui_turno`, `crea_grafo` (Task 3); `RisultatoFuso`, `rileva_fuso`, `carica_configurazione`, `ErroreConfigurazione` (Task 2); `verifica_server`, `crea_modello`, `ErroreServer` (Task 4); `crea_strumento_orologio`, `NOME_OROLOGIO` (Task 1).
- Produces:
  - `PAROLA_USCITA = "esci"`
  - `esegui_sessione(grafo, fuso: RisultatoFuso, leggi: Callable[[str], str] = input, scrivi: Callable[[str], None] = print) -> None`
  - `main() -> int` in `__main__.py`; avvio con `python -m assistente`.

Comportamento di `esegui_sessione` (spec 5.1): benvenuto con fuso e origine (es. `Fuso orario: Europe/Berlin (host Windows)`), più l'avviso se c'è, e come uscire; prompt `"Tu: "`; risposta `"Assistente: <testo>"`; per ogni `tool_call` di `ora_corrente` nei messaggi nuovi del turno una riga `[orologio: <fuso>]` prima della risposta; contenuto vuoto → `"Assistente: (nessuna risposta dal modello)"`; `except Exception` attorno a `esegui_turno` → `"Errore: <messaggio>"` e la cronologia resta quella di prima; `esci` (con `.strip().lower()`), `EOFError`, `KeyboardInterrupt` (sia in `leggi` sia durante `esegui_turno`) → `"Arrivederci."` e ritorno.

`main()`: `load_dotenv()` (senza sovrascrivere variabili già impostate) → `carica_configurazione(os.environ)` → `verifica_server` → `rileva_fuso(os.environ)` → `crea_strumento_orologio()` → `crea_modello` → `crea_grafo` → `esegui_sessione`. `ErroreConfigurazione`/`ErroreServer` → messaggio su stderr, ritorno `1`. `KeyboardInterrupt` durante l'avvio → ritorno `0` senza traceback.

- [ ] **Step 1: Test che falliscono** — `leggi` finto da una lista di righe (un elemento eccezione viene sollevato), `scrivi` che accumula in una lista, grafo vero con `ModelloFinto`

```python
def test_esci():                        # righe ["  ESCI "] → modello mai chiamato; output contiene "Arrivederci."
def test_riga_vuota_ignorata():         # ["", "   ", "esci"] → modello mai chiamato
def test_eof():                         # [EOFError()] → "Arrivederci.", nessuna eccezione
def test_ctrl_c_in_lettura():           # [KeyboardInterrupt()] → "Arrivederci."
def test_ctrl_c_durante_la_risposta():  # ModelloFinto([KeyboardInterrupt()]), ["ciao"] → "Arrivederci.", nessuna eccezione
def test_benvenuto():                   # RisultatoFuso("UTC", "ripiego", "AVVISO X") → output contiene "UTC" e "AVVISO X"
def test_conversazione_con_orologio():  # chiamata_orologio("Asia/Tokyo"), AIMessage("Sono le 23:04.") →
                                        # "[orologio: Asia/Tokyo]" prima di "Assistente: Sono le 23:04."
def test_risposta_vuota():              # AIMessage("") → "Assistente: (nessuna risposta dal modello)"
def test_errore_del_modello():          # risposte: RuntimeError("server giù"), AIMessage("ok"); righe ["a", "b", "esci"]
    # output contiene "Errore: server giù" e poi "Assistente: ok";
    # la seconda chiamata al modello NON contiene il messaggio "a"
```

- [ ] **Step 2: Verifica che falliscano** — `python -m pytest tests/test_terminale.py -v` → FAIL.
- [ ] **Step 3: Implementare** `terminale.py` e `__main__.py`.
- [ ] **Step 4: Verifica che passino** — `python -m pytest -v` → tutti PASS.
- [ ] **Step 5: Verifica manuale degli errori di avvio** (non interattiva):
  - `Remove-Item Env:LMSTUDIO_*` in una shell senza `.env` → `python -m assistente` stampa le variabili mancanti, codice di uscita 1 (`$LASTEXITCODE`).
  - Con `.env` copiato da `.env.example` e LM Studio acceso: `"esci" | python -m assistente` → benvenuto con il fuso, `Arrivederci.`, codice 0.
- [ ] **Step 6: Commit** — `feat(terminale): aggiungi interfaccia da terminale e punto di avvio`

---

### Task 6: Prova reale con LM Studio

**Files:**
- Create: `tests/test_reale_lmstudio.py`
- Create: `README.md` (prime sezioni: requisiti, configurazione, avvio diretto, test, diagnosi)
- Modify (solo se serve, Step 4): testo di `messaggio_sistema` in `assistente/grafo.py`, descrizione dello strumento in `assistente/strumenti.py`

**Interfaces:**
- Consumes: `carica_configurazione`, `crea_modello`, `crea_grafo`, `esegui_turno`, `crea_strumento_orologio`, `rileva_fuso`.

- [ ] **Step 1: Scrivere la prova** — marcata `@pytest.mark.lmstudio`, configurazione da `.env` (`load_dotenv`) e `os.environ`. Cinque casi parametrizzati, **ognuno in una sessione nuova** (cronologia vuota), fuso utente da `rileva_fuso`:

| Domanda | Fuso atteso nella `tool_call` |
|---|---|
| `Che ore sono?` | fuso utente |
| `Che giorno è oggi?` | fuso utente |
| `Che ore sono a Tokyo?` | `Asia/Tokyo` |
| `Che ora è adesso a New York?` | `America/New_York` |
| `Dimmi l'ora attuale a Londra.` | `Europe/London` |

Asserzioni per ogni caso: c'è almeno un `ToolMessage` di `ora_corrente` senza `"errore"`; l'argomento `fuso` della prima chiamata è quello atteso; l'ultimo messaggio è un `AIMessage` non vuoto. Per le domande sull'ora, la risposta contiene l'`HH:MM` restituito dallo strumento (o il minuto successivo). Stampa domanda, argomenti e risposta (`-s`) per il resoconto.

- [ ] **Step 2: Eseguire** — LM Studio acceso con `google/gemma-4-e2b`:
  `python -m pytest --lmstudio -m lmstudio -v -s`
  Expected (criterio della spec): 5 su 5 PASS. Verificare anche che `python -m pytest` senza opzioni salti questa prova (`skipped`).

- [ ] **Step 3: Chat reale breve** — `python -m assistente`, provare a mano "ciao", "che ore sono a Tokyo?", "e a Roma?" (verifica la cronologia), poi `esci`. Annotare l'esito.

- [ ] **Step 4: Solo se lo Step 2 fallisce** — al massimo due tentativi di miglioramento del messaggio di sistema e della descrizione dello strumento, rieseguendo lo Step 2 e `python -m pytest` dopo ognuno. Se ancora non 5/5: **fermarsi, riportare all'utente** gli esiti di Gemma, poi rieseguire con `LMSTUDIO_MODEL=qwen/qwen3.5-9b` (solo variabile, nel `.env`) e riportare anche quell'esito.

- [ ] **Step 5: README** — requisiti (Python 3.14, LM Studio con server attivo), creazione `.venv`, copia `.env.example` → `.env` (`Copy-Item .env.example .env`), avvio `python -m assistente`, test automatici `python -m pytest`, prova reale `python -m pytest --lmstudio -m lmstudio -v -s`, diagnosi (server spento, id sbagliato con `Invoke-RestMethod http://localhost:1234/v1/models`, prima risposta lenta per il caricamento al volo, nota `W. Europe Standard Time` → `Europe/Berlin` = stessa ora di Roma). Solo comandi eseguiti in questo task.

- [ ] **Step 6: Commit** — `test(reale): aggiungi prova reale con LM Studio` (+ eventuali modifiche al prompt nello stesso commit) e `docs: aggiungi README con avvio diretto e test`.

---

### Task 7: Docker

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `compose.yaml`, `avvia.ps1`, `tests/test_reale_docker.py`
- Modify: `README.md` (sezione Docker)

**Interfaces:**
- Consumes: `python -m assistente` (Task 5), variabili della spec 6.

- [ ] **Step 1: File Docker**
  - `Dockerfile`: `FROM python:3.14-slim`; `ENV ASSISTENTE_IN_DOCKER=1 PYTHONUNBUFFERED=1`; `WORKDIR /app`; copia e installa `requirements.txt` (`--no-cache-dir`), poi copia `assistente/`; `CMD ["python", "-m", "assistente"]`.
  - `.dockerignore`: `.env`, `.venv`, `tests`, `docs`, `__pycache__`, `.pytest_cache`, `.git`.
  - `compose.yaml`: servizio `assistente`; `build: .`; `env_file: .env`; `environment: LMSTUDIO_BASE_URL: ${LMSTUDIO_BASE_URL_DOCKER:?Imposta LMSTUDIO_BASE_URL_DOCKER nel file .env}`; `extra_hosts: ["host.docker.internal:host-gateway"]`; `stdin_open: true`; `tty: true`.
  - `avvia.ps1`: `param([switch]$SenzaTty)`; si sposta nella cartella dello script; `$fuso = (Get-TimeZone).Id`; esegue `docker compose run --rm` (+ `-T` se `-SenzaTty`) `-e "FUSO_HOST_WINDOWS=$fuso" assistente`; esce con il codice di Docker. Lo switch `-SenzaTty` serve solo alla prova automatica (ingresso da pipe) — *scelta del piano*.

- [ ] **Step 2: Prova reale** — `tests/test_reale_docker.py`, marcata `@pytest.mark.docker`: `docker compose build`, poi esegue `powershell -NoProfile -ExecutionPolicy Bypass -File avvia.ps1 -SenzaTty` con ingresso `"Che ore sono?\nesci\n"` (timeout 300 s). Asserzioni: codice 0; output contiene `(host Windows)`, il nome IANA atteso (calcolato nel test con `tzlocal.windows_tz.win_tz[(Get-TimeZone).Id]`), `[orologio:` e `Arrivederci.`; output **non** contiene `ripiego`.
  Più un caso senza script: `docker compose run --rm -T assistente` con lo stesso ingresso → output contiene `(FUSO_ORARIO)` (dal `.env`), non UTC in silenzio.

- [ ] **Step 3: Eseguire** — LM Studio acceso: `python -m pytest --docker -m docker -v -s` → PASS. Se il container non raggiunge LM Studio: abilitare in LM Studio il servizio sulla rete locale, rieseguire, e annotarlo per il README.

- [ ] **Step 4: Prova interattiva** — `.\avvia.ps1` da PowerShell: benvenuto, una domanda, `esci`. Se l'ambiente non permette un terminale interattivo, segnarlo nel resoconto come "da provare dall'utente".

- [ ] **Step 5: README** — sezione Docker: prerequisiti (Docker Desktop, eventuale opzione di rete di LM Studio), `.\avvia.ps1`, perché serve lo script (fuso), cosa succede con `docker compose run` a mano, prova `python -m pytest --docker -m docker -v -s`, diagnosi (`host.docker.internal` irraggiungibile, `LMSTUDIO_BASE_URL_DOCKER` mancante, criterio di esecuzione di PowerShell). Solo comandi verificati.

- [ ] **Step 6: Commit** — `feat(docker): aggiungi Dockerfile, Compose e script di avvio` e `docs: aggiungi avvio con Docker al README`.

---

### Task 8: Chiusura e documentazione stabile

**Files:**
- Modify: `../CLAUDE.md` (radice della repository), `README.md`

- [ ] **Step 1: Verifica completa** — `python -m pytest -v` (tutti PASS, prove reali `skipped`); rieseguire `python -m pytest --lmstudio -m lmstudio -v` e `python -m pytest --docker -m docker -v` se LM Studio e Docker sono disponibili.
- [ ] **Step 2: `CLAUDE.md`** — correggere la frase sulla posizione (il file è alla radice della repository, il progetto in `assistente-laboratorio/`); aggiungere struttura (`assistente/`, `tests/`), comandi di test (`python -m pytest`, `--lmstudio`, `--docker`) e avvio (`python -m assistente`, `.\avvia.ps1`). Nessuna nota sull'avanzamento.
- [ ] **Step 3: README** — rilettura: ogni comando è stato eseguito in questo progetto; nessun riferimento a funzioni non realizzate.
- [ ] **Step 4: Commit** — `docs: aggiorna CLAUDE.md con struttura e comandi di test`.
- [ ] **Step 5: Resoconto all'utente** — cosa è stato eseguito e con quale esito (test automatici, prova LM Studio con il conteggio x/5 per modello, prova Docker, prova interattiva), cosa resta da provare.
