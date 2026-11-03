# Convertitore di unità tramite MCP — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere all'assistente lo strumento `converti_unita`, esposto da un server MCP (`fastmcp`, Streamable HTTP) che l'agente avvia, scopre con `langchain-mcp-adapters`, usa tramite un ponte sincrono e spegne all'uscita, con log che dimostrano ogni chiamata.

**Architecture:** un nuovo pacchetto `server_mcp/` (logica di conversione pura + registrazione FastMCP + avvio HTTP su `127.0.0.1`) gira come processo separato. In `assistente/`: `avvio_server.py` avvia il processo, attende la discovery e lo spegne; `client_mcp.py` scopre il catalogo e avvolge ogni tool asincrono in un tool LangChain sincrono che non solleva mai eccezioni; `registro.py` scrive `logs/assistente.log`. Grafo, terminale e `__main__` cambiano il minimo indispensabile.

**Tech Stack:** Python 3.14, LangGraph 1.2.19, langchain-core 1.7.3, `fastmcp` 3.4.11, `langchain-mcp-adapters` 0.3.2, `mcp` 1.30.0, pytest 9.2.0, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-03-convertitore-unita-mcp-design.md` (da leggere insieme a questo piano).

## Global Constraints

- Tutti i percorsi sono relativi a `assistente-laboratorio/`. Comandi da lì con l'interprete dell'ambiente virtuale: `.venv/Scripts/python.exe` (sotto abbreviato in `python`).
- Branch `dev`. Commit in Conventional Commits in italiano, staging selettivo dei soli file del task, **nessuna riga `Co-Authored-By`**. Nessun push.
- Versioni fissate in `requirements.txt`: `fastmcp==3.4.11`, `langchain-mcp-adapters==0.3.2`, `mcp==1.30.0` (verificate il 2026-11-03 in un ambiente pulito con Python 3.14 e le versioni già fissate: `pip` risolve senza conflitti; `fastmcp` 4.x richiede `mcp>=2.3` ed è incompatibile con l'adattatore). Nessun'altra dipendenza.
- Codice sincrono ovunque tranne dentro `assistente/client_mcp.py`, che usa `asyncio.run`.
- Il server ascolta solo su `127.0.0.1`, percorso `/mcp`. URL: `http://127.0.0.1:<porta>/mcp`.
- Nome dello strumento: `converti_unita`. Nome del server: `Strumenti laboratorio`.
- Unità, nell'ordine dell'enumerazione: `km hm dam m dm cm mm kg hg dag g dg cg mg hl dal l dl cl ml °C °F`.
- Tempi: attesa di avvio 10 s; timeout di ogni chiamata MCP 10 s; attesa di arresto 5 s prima dell'arresto forzato.
- `MCP_PORTA` obbligatoria, intero tra 1024 e 65535.
- Log in `logs/assistente.log` e `logs/server_mcp.log`, in UTF-8, in coda, cartella esclusa da Git e dall'immagine Docker.
- Messaggi all'utente in italiano, errori di avvio senza traceback e con codice di uscita 1.
- Fatti verificati nel prototipo (da non riscoprire):
  - i tool dell'adattatore sono solo asincroni (`invoke` → `NotImplementedError`);
  - con `handle_tool_errors=False` un risultato MCP con `isError` solleva `ToolException`;
  - un server spento produce un `ExceptionGroup` che contiene `ConnectTimeout`/`ConnectError`;
  - su Windows `CTRL_BREAK_EVENT` a un processo avviato con `CREATE_NEW_PROCESS_GROUP` lo chiude in circa 0,2 s;
  - `stateless_http=True, json_response=True, log_level="warning"` evitano traceback e rumore nel log del server;
  - un parametro `Annotated[Any, WithJsonSchema({...})]` pubblica lo schema voluto e passa alla funzione il valore grezzo.

## Review Focus

1. **Ctrl+C durante i 10 s di attesa dell'avvio:** il server deve essere spento lo stesso. Test in Task 4 (`test_ctrl_c_durante_l_avvio_spegne_il_server`).
2. **Caratteri non ASCII nei log su Windows** (`°C`, `à`): il processo figlio scriverebbe con la codifica locale. Il server va avviato con `PYTHONUTF8=1` e il log va riletto in UTF-8. Test in Task 4 (`test_log_del_server_in_utf8`).
3. **L'output del server non deve comparire nel terminale della chat.** Test in Task 4 (`test_nessun_output_nel_terminale`).
4. **Valori enormi** (`1e308 km → mm`) devono dare un errore, non `Infinity` nel JSON. Test in Task 1.
5. **Cartella `logs/` assente al primo avvio:** va creata. Test in Task 5 (`test_crea_la_cartella`).

---

### Task 1: logica di conversione

**Files:**
- Create: `server_mcp/__init__.py` (solo docstring), `server_mcp/conversioni.py`
- Test: `tests/test_conversioni.py`

**Interfaces:**
- Produces:
  - `UNITA_AMMESSE: tuple[str, ...]` (ordine dei Global Constraints);
  - `class ErroreConversione(ValueError)`;
  - `converti(valore: object, da: object, a: object) -> dict`, che restituisce `{"valore", "da", "a", "risultato", "grandezza"}`;
  - `grandezza` vale `"lunghezza"`, `"massa"`, `"volume"` o `"temperatura"`.

- [ ] **Step 1: scrivere i test**

```python
import math
import pytest
from server_mcp.conversioni import UNITA_AMMESSE, ErroreConversione, converti

def test_risultato_completo():
    assert converti(2.5, "km", "m") == {"valore": 2.5, "da": "km", "a": "m", "risultato": 2500, "grandezza": "lunghezza"}

@pytest.mark.parametrize("valore, da, a, atteso", [
    (0.1, "km", "m", 100), (750, "ml", "l", 0.75), (3, "kg", "g", 3000), (1, "mg", "kg", 1e-06),
    (5, "hl", "cl", 50000), (1, "dag", "dg", 100), (12, "dam", "dm", 1200), (0, "cm", "m", 0),
    (100, "°F", "°C", 37.78), (37, "°C", "°F", 98.6), (-40, "°C", "°F", -40), (0, "°C", "°F", 32),
    (2.5, "km", "km", 2.5), ("2.5", "km", "m", 2500),
])
def test_conversioni(valore, da, a, atteso):
    risultato = converti(valore, da, a)["risultato"]
    assert risultato == atteso and type(risultato) is type(atteso)

def test_grandezze():
    assert [converti(1, u, u)["grandezza"] for u in ("m", "g", "l", "°C")] == ["lunghezza", "massa", "volume", "temperatura"]

def test_elenco_unita():
    assert UNITA_AMMESSE == ("km", "hm", "dam", "m", "dm", "cm", "mm", "kg", "hg", "dag", "g", "dg", "cg", "mg",
                             "hl", "dal", "l", "dl", "cl", "ml", "°C", "°F")

@pytest.mark.parametrize("valore, da, a, frammento", [
    ("2,5", "km", "m", "punto"), ("abc", "km", "m", "non numerico"), (True, "km", "m", "non numerico"),
    (None, "km", "m", "non numerico"), (math.nan, "km", "m", "finito"), (math.inf, "km", "m", "finito"),
    (-1, "km", "m", "negativo"), (-300, "°C", "°F", "zero assoluto"), (-460, "°F", "°C", "zero assoluto"),
    (1, "Km", "m", "Unità sconosciuta"), (1, " km", "m", "Unità sconosciuta"), (1, "m", "C", "Unità sconosciuta"),
    (1, "kg", "m", "grandezze"), (1, "°C", "l", "grandezze"), (1e308, "km", "mm", "troppo grande"),
])
def test_errori(valore, da, a, frammento):
    with pytest.raises(ErroreConversione) as errore:
        converti(valore, da, a)
    assert frammento in str(errore.value)

def test_unita_sconosciuta_elenca_le_ammesse():
    with pytest.raises(ErroreConversione) as errore:
        converti(1, "miglia", "m")
    assert "km, hm, dam, m" in str(errore.value) and "°C, °F" in str(errore.value)
```

- [ ] **Step 2:** `python -m pytest tests/test_conversioni.py -v`. Atteso: FAIL con `ModuleNotFoundError: server_mcp`.

- [ ] **Step 3: implementare `converti` in `server_mcp/conversioni.py`**

Il modulo non importa `fastmcp`.

Tabella:
- lunghezza, massa e volume hanno un esponente di 10 rispetto all'unità base (`km`→3 … `mm`→−3; `kg`→3 … `mg`→−3; `hl`→2 … `ml`→−3);
- la temperatura ha `°C`/`°F`.

Validazione, in quest'ordine:
1. **valore**:
   - `bool` è rifiutato;
   - una stringa con `,` è rifiutata («usa il punto come separatore decimale, per esempio 2.5»);
   - un'altra stringa passa da `float()`;
   - poi deve essere finito;
   - poi diventa `Decimal(repr(float(x)))`, o `Decimal(int)` per un intero.
2. **unità**: un'unità fuori elenco dà `Unità sconosciuta: '<u>'. Unità ammesse: <elenco separato da ", ">.`
3. **grandezza**: devono essere della stessa grandezza.
4. **limiti**:
   - un negativo è rifiutato per lunghezza, massa e volume;
   - per le temperature valgono i minimi `-273.15` °C e `-459.67` °F.
5. **calcolo**:
   - le metriche si moltiplicano per `Decimal(10) ** (esp_da - esp_a)`;
   - le temperature usano le formule della spec, con `quantize(Decimal("0.01"), ROUND_HALF_UP)`;
   - se `da == a` il valore resta invariato.
6. **uscita**:
   - un `Decimal` intero diventa `int`, altrimenti `float`;
   - un `float` non finito dà «Risultato troppo grande per essere rappresentato.»

Il campo `"valore"` del risultato è il numero già interpretato (2.5, non "2.5").

- [ ] **Step 4:** `python -m pytest tests/test_conversioni.py -v`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(server): aggiungi la logica del convertitore di unità` con `server_mcp/__init__.py`, `server_mcp/conversioni.py` e `tests/test_conversioni.py`.

---

### Task 2: server MCP con FastMCP

**Files:**
- Modify: `requirements.txt` (aggiungere le tre righe dei Global Constraints)
- Create: `server_mcp/server.py`, `server_mcp/__main__.py`
- Test: `tests/test_server_mcp.py`

**Interfaces:**
- Consumes: `converti`, `ErroreConversione`, `UNITA_AMMESSE` (Task 1).
- Produces:
  - `NOME_SERVER = "Strumenti laboratorio"`, `NOME_CONVERTITORE = "converti_unita"`;
  - `crea_server() -> FastMCP`;
  - comando `python -m server_mcp --porta <int>`, che avvia lo Streamable HTTP su `127.0.0.1:<porta>/mcp`;
  - log del logger `server_mcp` su stderr.

- [ ] **Step 1: installare le dipendenze**
  - Aggiungere `fastmcp==3.4.11`, `langchain-mcp-adapters==0.3.2` e `mcp==1.30.0` a `requirements.txt`.
  - Eseguire `python -m pip install -r requirements-dev.txt`, poi `python -m pip check`. Atteso: `No broken requirements found.`

- [ ] **Step 2: scrivere i test.** I test usano il client in memoria di `fastmcp`, senza rete, con `asyncio.run` dentro test sincroni:

```python
import asyncio, json, logging
from fastmcp import Client
from server_mcp.conversioni import UNITA_AMMESSE
from server_mcp.server import NOME_CONVERTITORE, crea_server

def con_client(funzione):
    async def corpo():
        async with Client(crea_server()) as client:
            return await funzione(client)
    return asyncio.run(corpo())

def test_catalogo():
    strumenti = con_client(lambda c: c.list_tools())
    assert [s.name for s in strumenti] == [NOME_CONVERTITORE]
    schema = strumenti[0].inputSchema
    assert schema["required"] == ["valore", "da", "a"]
    assert schema["properties"]["valore"]["type"] == "number"
    assert schema["properties"]["da"]["enum"] == list(UNITA_AMMESSE) == schema["properties"]["a"]["enum"]
    assert "Celsius" in strumenti[0].description

def test_chiamata_riuscita(caplog):
    caplog.set_level(logging.INFO, logger="server_mcp")
    r = con_client(lambda c: c.call_tool(NOME_CONVERTITORE, {"valore": 2.5, "da": "km", "a": "m"}))
    assert not r.is_error and r.structured_content["risultato"] == 2500
    assert json.loads(r.content[0].text)["grandezza"] == "lunghezza"
    assert "tool=converti_unita" in caplog.text and "esito=ok" in caplog.text

def test_errore_come_errore_mcp(caplog):
    caplog.set_level(logging.INFO, logger="server_mcp")
    r = con_client(lambda c: c.call_tool(NOME_CONVERTITORE, {"valore": 1, "da": "C", "a": "m"}, raise_on_error=False))
    assert r.is_error and "Unità sconosciuta" in r.content[0].text and r.structured_content is None
    assert "esito=errore" in caplog.text
```

- [ ] **Step 3:** `python -m pytest tests/test_server_mcp.py -v`. Atteso: FAIL (`server_mcp.server` assente).

- [ ] **Step 4: implementare `crea_server()` in `server_mcp/server.py`**

`FastMCP(NOME_SERVER)` con un tool registrato come `NOME_CONVERTITORE`. Parametri:
- `valore: Annotated[Any, WithJsonSchema({"type": "number", "description": "Numero da convertire, con il punto decimale (es. 2.5)"})]`;
- `da` e `a`: `Annotated[Any, WithJsonSchema({"type": "string", "enum": list(UNITA_AMMESSE), "description": ...})]`.

Il tipo è `Any` apposta, perché la validazione e i messaggi italiani li fa `converti` (fatto verificato).

Descrizione (testo esatto): `Converte un valore tra unità metriche della stessa grandezza (lunghezza, massa, volume) o tra gradi Celsius e Fahrenheit. Esempio: valore=2.5, da="km", a="m".`

Il corpo restituisce il `dict` di `converti`. Per i log usa `logging.getLogger("server_mcp")` con livello INFO e righe:
- `chiamata tool=converti_unita argomenti=<json compatto> esito=ok risultato=<json compatto>`;
- in caso di errore `... esito=errore messaggio=<testo>`, poi `raise ToolError(str(errore))`.

Il JSON è compatto con `ensure_ascii=False`.

- [ ] **Step 5: implementare `server_mcp/__main__.py`**
  - `argparse` con `--porta` obbligatoria (`type=int`);
  - `logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stderr)`;
  - una riga `avvio server porta=<p>`;
  - poi `crea_server().run(transport="http", host="127.0.0.1", port=porta, path="/mcp", show_banner=False, stateless_http=True, json_response=True, log_level="warning")`;
  - una riga `arresto server` in un `finally`. Se il segnale di arresto la salta, la prova dell'arresto resta la riga `server spento` nel log dell'agente (Task 4).

- [ ] **Step 6:** `python -m pytest -q`. Atteso: tutti PASS, prove reali `skipped`.
- [ ] **Step 7:** commit `feat(server): esponi converti_unita con un server FastMCP` con `requirements.txt`, `server_mcp/server.py`, `server_mcp/__main__.py` e `tests/test_server_mcp.py`.

---

### Task 3: ponte sincrono verso gli strumenti MCP

**Files:**
- Create: `assistente/client_mcp.py`
- Test: `tests/test_client_mcp.py`

**Interfaces:**
- Produces:
  - `NOME_CONNESSIONE = "laboratorio"`, `TIMEOUT_CHIAMATA = 10.0`, `TIPO_STRUMENTO = "strumento"`, `TIPO_COLLEGAMENTO = "collegamento"`, `ORIGINE_MCP = "mcp"`;
  - `class ErroreServerMCP(Exception)`;
  - `avvolgi(strumento: BaseTool, timeout: float = TIMEOUT_CHIAMATA) -> BaseTool`;
  - `scopri_strumenti(url: str, timeout_scoperta: float = TIMEOUT_CHIAMATA) -> list[BaseTool]`;
  - `unisci_strumenti(locali: list[BaseTool], remoti: list[BaseTool]) -> list[BaseTool]`.
- Contratto del ponte: il tool restituito ha lo stesso `name`, `description` e `args_schema`, `metadata={"origine": "mcp"}`. `invoke(argomenti)` restituisce sempre una stringa:
  - in caso di successo, il testo dei blocchi `text` concatenati;
  - in caso di errore, `{"errore": "...", "tipo": "strumento"|"collegamento"}`.

- [ ] **Step 1: scrivere i test** con tool asincroni finti, senza server:

```python
import asyncio, json, pytest
from langchain_core.tools import StructuredTool, ToolException
from assistente.client_mcp import ErroreServerMCP, avvolgi, unisci_strumenti
from assistente.strumenti import crea_strumento_orologio

SCHEMA = {"type": "object", "properties": {"valore": {"type": "number"}}, "required": ["valore"]}

def finto(corpo, nome="converti_unita"):
    return StructuredTool(name=nome, description="desc", args_schema=SCHEMA, coroutine=corpo,
                          response_format="content_and_artifact")

def test_successo_e_contratto():
    async def ok(**a): return [{"type": "text", "text": '{"risultato": 2500}'}], None
    ponte = avvolgi(finto(ok))
    assert (ponte.name, ponte.description, ponte.args_schema, ponte.metadata) == ("converti_unita", "desc", SCHEMA, {"origine": "mcp"})
    assert json.loads(ponte.invoke({"valore": 2.5})) == {"risultato": 2500}

@pytest.mark.parametrize("eccezione, tipo, frammento", [
    (ToolException("Unità sconosciuta: 'C'"), "strumento", "Unità sconosciuta: 'C'"),
    (ExceptionGroup("g", [ConnectionRefusedError("rifiutata")]), "collegamento", "Server MCP non raggiungibile: ConnectionRefusedError: rifiutata"),
])
def test_errori(eccezione, tipo, frammento):
    async def fallisce(**a): raise eccezione
    risultato = json.loads(avvolgi(finto(fallisce)).invoke({"valore": 1}))
    assert risultato["tipo"] == tipo and frammento in risultato["errore"] and "risultato" not in risultato

def test_timeout():
    async def lento(**a): await asyncio.sleep(5)
    risultato = json.loads(avvolgi(finto(lento), timeout=0.1).invoke({"valore": 1}))
    assert risultato == {"errore": "Server MCP: nessuna risposta entro 0.1 secondi.", "tipo": "collegamento"}

def test_unisci_e_conflitto():
    async def ok(**a): return [], None
    orologio = crea_strumento_orologio()
    assert [s.name for s in unisci_strumenti([orologio], [finto(ok)])] == ["ora_corrente", "converti_unita"]
    with pytest.raises(ErroreServerMCP, match="ora_corrente"):
        unisci_strumenti([orologio], [finto(ok, nome="ora_corrente")])
```

- [ ] **Step 2:** `python -m pytest tests/test_client_mcp.py -v`. Atteso: FAIL (modulo assente).

- [ ] **Step 3: implementare `assistente/client_mcp.py`**

`avvolgi` crea `StructuredTool(name, description, args_schema=strumento.args_schema, func=esegui, metadata={"origine": ORIGINE_MCP})`. Dentro `esegui(**argomenti)`:
- esegue `asyncio.run(asyncio.wait_for(strumento.ainvoke(argomenti), timeout))`;
- su `ToolException` restituisce un errore di tipo strumento;
- su `TimeoutError` restituisce `Server MCP: nessuna risposta entro {timeout:g} secondi.`;
- su qualsiasi altra `Exception` restituisce `Server MCP non raggiungibile: <Tipo>: <messaggio>`. Se è un `BaseExceptionGroup` si scende alla prima sotto-eccezione, ricorsivamente; se il messaggio è vuoto, solo il tipo.

Il JSON degli errori è con `ensure_ascii=False`.

`scopri_strumenti`:
- crea `MultiServerMCPClient({NOME_CONNESSIONE: {"transport": "streamable_http", "url": url, "timeout": TIMEOUT_CHIAMATA}}, handle_tool_errors=False)`;
- esegue `asyncio.run(asyncio.wait_for(client.get_tools(), timeout_scoperta))`;
- restituisce i tool passati da `avvolgi`;
- lascia propagare le eccezioni, che gestisce il chiamante (Task 4).

`unisci_strumenti`: se un nome remoto coincide con uno locale, solleva `ErroreServerMCP(f"Lo strumento MCP '{nome}' ha lo stesso nome di uno strumento locale: rinominalo nel server.")`.

- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(mcp): aggiungi il ponte sincrono verso gli strumenti MCP` con `assistente/client_mcp.py` e `tests/test_client_mcp.py`.

---

### Task 4: avvio, attesa e arresto del server

**Files:**
- Create: `assistente/avvio_server.py`, `tests/server_vuoto.py`
- Modify: `tests/conftest.py` (fixture `porta`)
- Test: `tests/test_avvio_server.py`

**Interfaces:**
- Consumes: `scopri_strumenti`, `ErroreServerMCP` (Task 3); comando `python -m server_mcp --porta` (Task 2).
- Produces:
  - `ATTESA_AVVIO = 10.0`, `ATTESA_ARRESTO = 5.0`;
  - `url_server(porta: int) -> str`;
  - `porta_libera(porta: int) -> bool`;
  - `ultime_righe(percorso: Path, quante: int = 10) -> str`;
  - `ferma(processo: subprocess.Popen, attesa: float = ATTESA_ARRESTO) -> None`;
  - `@dataclass(frozen=True) ServerAvviato(processo: subprocess.Popen, url: str, strumenti: list[BaseTool])`;
  - `@contextmanager avvia_server_mcp(porta: int, percorso_log: Path, attesa: float = ATTESA_AVVIO, comando: list[str] | None = None) -> Iterator[ServerAvviato]`;
  - logger `assistente.avvio`, con righe `server avviato porta=… pid=…`, `catalogo strumenti=[…]` e `server spento codice=…`.

- [ ] **Step 1: scrivere i test**
  - In `tests/conftest.py`, due fixture (servono anche al Task 6):
    - `porta`, che restituisce una porta libera ottenuta con `bind(("127.0.0.1", 0))`;
    - `popen_registrati(monkeypatch)`, che sostituisce `assistente.avvio_server.subprocess.Popen` con un involucro del `Popen` originale, aggiunge ogni processo creato a una lista e restituisce la lista.
  - In `tests/server_vuoto.py`: un `FastMCP("vuoto")` senza strumenti, avviato sulla porta di `--porta` con gli stessi argomenti `run` del Task 2.
  - I test:

```python
import json, socket, sys
from pathlib import Path
import pytest
from assistente import avvio_server
from assistente.avvio_server import avvia_server_mcp
from assistente.client_mcp import ErroreServerMCP
from server_mcp.conversioni import UNITA_AMMESSE

def test_ciclo_completo(porta, tmp_path):
    log = tmp_path / "server_mcp.log"
    with avvia_server_mcp(porta, log) as avviato:
        assert avviato.url == f"http://127.0.0.1:{porta}/mcp"
        (strumento,) = avviato.strumenti
        assert strumento.name == "converti_unita" and strumento.args_schema["properties"]["da"]["enum"] == list(UNITA_AMMESSE)
        assert json.loads(strumento.invoke({"valore": 2.5, "da": "km", "a": "m"}))["risultato"] == 2500
        errore = json.loads(strumento.invoke({"valore": 1, "da": "Mars", "a": "m"}))   # errore controllato, slide 23
        assert errore["tipo"] == "strumento" and "Unità sconosciuta" in errore["errore"] and "risultato" not in errore
    assert avviato.processo.poll() is not None                                          # nessun processo orfano
    dopo = json.loads(strumento.invoke({"valore": 1, "da": "km", "a": "m"}))
    assert dopo["tipo"] == "collegamento"

def test_log_del_server_in_utf8(porta, tmp_path):
    log = tmp_path / "server_mcp.log"
    with avvia_server_mcp(porta, log) as avviato:
        avviato.strumenti[0].invoke({"valore": -300, "da": "°C", "a": "°F"})
    testo = log.read_text(encoding="utf-8")
    assert "tool=converti_unita" in testo and "°C" in testo and "zero assoluto" in testo

def test_nessun_output_nel_terminale(porta, tmp_path, capfd):
    with avvia_server_mcp(porta, tmp_path / "s.log") as avviato:
        avviato.strumenti[0].invoke({"valore": 1, "da": "km", "a": "m"})
    assert capfd.readouterr() == ("", "")

def test_porta_occupata(porta, tmp_path):
    with socket.socket() as occupante:
        occupante.bind(("127.0.0.1", porta)); occupante.listen()
        with pytest.raises(ErroreServerMCP) as errore:
            with avvia_server_mcp(porta, tmp_path / "s.log"): pass
    assert f"Porta {porta} già in uso" in str(errore.value) and "MCP_PORTA" in str(errore.value)

def test_server_che_non_parte(porta, tmp_path):
    comando = [sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(1)"]
    with pytest.raises(ErroreServerMCP) as errore:
        with avvia_server_mcp(porta, tmp_path / "s.log", comando=comando): pass
    assert "Il server MCP non è partito" in str(errore.value) and "boom" in str(errore.value)

def test_server_che_non_risponde_viene_spento(porta, tmp_path, popen_registrati):
    creati = popen_registrati
    with pytest.raises(ErroreServerMCP, match="non è partito"):
        with avvia_server_mcp(porta, tmp_path / "s.log", attesa=1, comando=[sys.executable, "-c", "import time; time.sleep(60)"]): pass
    assert creati[0].poll() is not None

def test_catalogo_vuoto(porta, tmp_path, popen_registrati):
    creati = popen_registrati
    comando = [sys.executable, str(Path(__file__).parent / "server_vuoto.py"), "--porta", str(porta)]
    with pytest.raises(ErroreServerMCP, match="non espone nessuno strumento"):
        with avvia_server_mcp(porta, tmp_path / "s.log", comando=comando): pass
    assert creati[0].poll() is not None

def test_ctrl_c_durante_l_avvio_spegne_il_server(porta, tmp_path, popen_registrati, monkeypatch):
    creati = popen_registrati
    def interrompi(*a, **k): raise KeyboardInterrupt
    monkeypatch.setattr(avvio_server, "scopri_strumenti", interrompi)
    with pytest.raises(KeyboardInterrupt):
        with avvia_server_mcp(porta, tmp_path / "s.log"): pass
    assert creati[0].poll() is not None
```

- [ ] **Step 2:** `python -m pytest tests/test_avvio_server.py -v`. Atteso: FAIL (modulo assente).

- [ ] **Step 3: implementare `assistente/avvio_server.py`**

`porta_libera`: un `bind` su `127.0.0.1` senza `SO_REUSEADDR`; un `OSError` significa occupata.

`avvia_server_mcp`, in ordine:
1. Se la porta è occupata solleva `ErroreServerMCP(f"Porta {porta} già in uso: chiudi il programma che la usa o cambia MCP_PORTA nel .env.")`.
2. Crea la cartella del log e apre il file in append, UTF-8.
3. Avvia `subprocess.Popen(comando or [sys.executable, "-m", "server_mcp", "--porta", str(porta)], cwd=<cartella del progetto>, stdin=DEVNULL, stdout=log, stderr=STDOUT, env={**os.environ, "PYTHONUTF8": "1"})`, con `creationflags=CREATE_NEW_PROCESS_GROUP` su Windows e `start_new_session=True` altrove. La cartella del progetto è `Path(__file__).resolve().parent.parent`.
4. Ciclo fino alla scadenza di `attesa`:
   - se `processo.poll()` non è `None`, il server è terminato: errore;
   - altrimenti prova `scopri_strumenti(url, timeout_scoperta=min(2.0, tempo rimasto))`;
   - un'eccezione ordinaria fa ripetere dopo 0,25 s.
5. Se il processo è terminato o il tempo è scaduto: `ErroreServerMCP(f"Il server MCP non è partito (porta {porta}). Ultime righe di {percorso_log}:\n{ultime_righe(...)}")`.
6. Con un catalogo vuoto: `ErroreServerMCP("Il server MCP non espone nessuno strumento.")`.
7. `yield ServerAvviato(...)`.

Un `try/finally` attorno a tutto, dal `Popen` in poi, chiama sempre `ferma` e chiude il file, anche con `KeyboardInterrupt`.

`ferma`: se il processo è vivo, su Windows `send_signal(signal.CTRL_BREAK_EVENT)`, altrove `terminate()`. Poi `wait(attesa)`; su `TimeoutExpired`, `kill()` e `wait()`.

`ultime_righe` legge con `encoding="utf-8", errors="replace"`.

Se `test_nessun_output_nel_terminale` trova avvisi delle librerie client (logger `mcp`, `httpx`) su stderr, alzare il loro livello a ERROR in `client_mcp.py`. Il terminale della chat deve restare pulito (Review Focus 3).

- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS. I test di questo file avviano server reali e richiedono qualche secondo ciascuno.
- [ ] **Step 5:** commit `feat(mcp): avvia, attendi e spegni il server MCP` con `assistente/avvio_server.py`, `tests/server_vuoto.py`, `tests/conftest.py` e `tests/test_avvio_server.py`.

---

### Task 5: registro delle chiamate e grafo

**Files:**
- Create: `assistente/registro.py`
- Modify: `assistente/grafo.py`, `tests/finti.py`
- Test: `tests/test_registro.py`, `tests/test_grafo.py` (aggiunte)

**Interfaces:**
- Consumes: `ORIGINE_MCP` (Task 3), tramite `metadata["origine"]` dei tool.
- Produces:
  - in `registro.py`: `CARTELLA_LOG = <cartella progetto>/"logs"`, `LOG_ASSISTENTE = CARTELLA_LOG/"assistente.log"`, `LOG_SERVER = CARTELLA_LOG/"server_mcp.log"`, `configura_registro(percorso: Path = LOG_ASSISTENTE) -> None`, `formatta(campi: Mapping[str, object]) -> str`;
  - nel grafo, logger `assistente.strumenti`;
  - in `finti.py`, `chiamata_convertitore(valore, da, a, id="m1") -> AIMessage` e `strumento_finto(risposta: str, nome="converti_unita") -> BaseTool`, che restituisce sempre `risposta` e ha `metadata={"origine": "mcp"}`.
- Esiti nel log: `ok`, `errore_tool`, `errore_collegamento`, `strumento_sconosciuto`, `limite`.

- [ ] **Step 1: scrivere i test di `registro.py`**

```python
import logging
from assistente.registro import configura_registro, formatta

def test_formatta():
    assert formatta({"tool": "x", "argomenti": {"valore": 2.5, "da": "°C"}, "risultato": "a\nb"}) == \
        'tool=x argomenti={"valore":2.5,"da":"°C"} risultato=a b'

def test_crea_la_cartella(tmp_path):
    percorso = tmp_path / "nuova" / "assistente.log"
    logger = logging.getLogger("assistente")
    prima = list(logger.handlers)
    try:
        configura_registro(percorso); configura_registro(percorso)   # idempotente
        logging.getLogger("assistente.strumenti").info("riga °C")
        for h in logger.handlers: h.flush()
        assert percorso.read_text(encoding="utf-8").count("riga °C") == 1
    finally:
        for h in logger.handlers[len(prima):]: h.close(); logger.removeHandler(h)
        logger.propagate = True
```

- [ ] **Step 2: aggiungere i test del grafo** (`caplog.set_level(logging.INFO, logger="assistente.strumenti")`). `prepara` riceve anche strumenti extra:

```python
def test_chiamata_mcp_registrata(caplog):          # ok: status success, riga completa
    ...  # modello: chiamata_convertitore(2.5, "km", "m", "m1"), AIMessage("2500 m")
    assert risultato.tool_call_id == "m1" and risultato.status == "success"
    for campo in ("origine=mcp", "tool=converti_unita", "call_id=m1", '"da":"km"', "esito=ok", "tool_message.call_id=m1"):
        assert campo in caplog.text

@pytest.mark.parametrize("risposta, esito", [
    ('{"errore": "Unità sconosciuta", "tipo": "strumento"}', "esito=errore_tool"),
    ('{"errore": "Server MCP non raggiungibile", "tipo": "collegamento"}', "esito=errore_collegamento"),
])
def test_errori_mcp_marcati(caplog, risposta, esito):   # status == "error" e esito nel log

def test_errore_orologio_marcato(caplog):           # fuso "Mars/Olympus": status "error", "origine=locale", "esito=errore_tool"
def test_strumento_sconosciuto_registrato(caplog):  # "esito=strumento_sconosciuto"
def test_limite_registrato(caplog):                 # 4 chiamate: la quarta ha "esito=limite"
def test_testi_generici():
    assert "strumenti" in TESTO_LIMITE and "orologio" not in TESTO_LIMITE
    sistema = messaggio_sistema(FUSO).content
    assert "ora_corrente" in sistema and "conversioni di unità" in sistema
```

- [ ] **Step 3:** `python -m pytest tests/test_registro.py tests/test_grafo.py -v`. Atteso: FAIL sui nuovi test.

- [ ] **Step 4: implementare `registro.py`**
  - `formatta` scrive `chiave=valore` separati da spazio: le stringhe con gli a capo sostituiti da spazi, gli altri valori come JSON compatto con `ensure_ascii=False`.
  - `configura_registro` crea la cartella e aggiunge un solo `FileHandler` (append, UTF-8, formato `%(asctime)s %(message)s`, data `%Y-%m-%d %H:%M:%S`) al logger `assistente`, con livello INFO e `propagate=False`.

- [ ] **Step 5: modificare `grafo.py`**

Testi esatti:
- `TESTO_LIMITE = "Non sono riuscito a completare la richiesta: troppe chiamate agli strumenti. Prova a riformularla."`;
- il messaggio di sistema guadagna la riga `Per conversioni di unità e altri calcoli usa sempre lo strumento adatto tra quelli disponibili: non farli a mente.`;
- il testo per gli argomenti non JSON diventa `Argomenti non validi: devono essere un oggetto JSON con gli argomenti dello strumento.`

In `nodo_strumenti`, per ogni chiamata:
- `origine` vale `(strumento.metadata or {}).get("origine", "locale")`, oppure `"sconosciuta"`;
- `esito` è calcolato dal contenuto:
  - JSON con `"errore"` e `"tipo" == "collegamento"` → `errore_collegamento`;
  - un altro `"errore"` → `errore_tool`;
  - altrimenti `ok`;
  - in più, eccezione all'invocazione → `errore_tool` e strumento assente → `strumento_sconosciuto`;
- `ToolMessage(..., status="success" if esito == "ok" else "error")`;
- una riga `formatta({"origine", "tool", "call_id", "argomenti", "esito", "risultato", "tool_message.call_id"})`.

Le chiamate malformate e quelle chiuse da `nodo_limite` sono registrate con `errore_tool` e `limite`.

Nota per il resoconto: ora anche l'errore dell'orologio (fuso inesistente) ha `status="error"`, quindi il terminale non stampa più `[orologio: …]` per una chiamata fallita. È coerente con la regola «riga solo per le chiamate riuscite».

- [ ] **Step 6:** `python -m pytest -q`. Atteso: tutti PASS, compresi i test del grafo già esistenti.
- [ ] **Step 7:** commit `feat(grafo): registra ogni chiamata e marca gli esiti di errore` con `assistente/registro.py`, `assistente/grafo.py`, `tests/finti.py`, `tests/test_registro.py` e `tests/test_grafo.py`.

---

### Task 6: configurazione, terminale e avvio unico

**Files:**
- Modify: `assistente/configurazione.py`, `assistente/terminale.py`, `assistente/__main__.py`, `.env.example`, `.gitignore`, `tests/test_configurazione.py`, `tests/test_modello.py:67`, `tests/test_terminale.py`
- Test: `tests/test_avvio_unico.py`

**Interfaces:**
- Consumes: `avvia_server_mcp` e le fixture `porta`/`popen_registrati` (Task 4), `unisci_strumenti` e `ErroreServerMCP` (Task 3), `configura_registro`, `LOG_ASSISTENTE` e `LOG_SERVER` (Task 5), `strumento_finto` e `chiamata_convertitore` (Task 5).
- Produces:
  - `Configurazione(base_url: str, modello: str, porta_mcp: int)`;
  - `esegui_sessione(grafo, fuso, leggi=input, scrivi=print, strumenti_mcp: Sequence[str] = ())`.

- [ ] **Step 1: scrivere i test**
  - **Configurazione**:
    - gli ambienti di prova esistenti guadagnano `"MCP_PORTA": "8765"` e i confronti diventano `Configurazione(..., ..., 8765)`;
    - `MCP_PORTA` mancante compare nell'elenco delle mancanti;
    - con i valori `"abc"`, `"80"`, `"70000"`, `"8765.0"` il messaggio contiene `MCP_PORTA non valida: '<valore>'` e `tra 1024 e 65535`;
    - `tests/test_modello.py:67` diventa `Configurazione(URL, "google/gemma-4-e2b", 8765)`.
  - **Terminale**:

```python
def test_conversazione_con_convertitore():   # modello: chiamata_convertitore(2.5, "km", "m"), AIMessage("Sono 2500 m.")
    # grafo con strumento_finto('{"risultato": 2500}'): "[convertitore: 2.5 km → m]" stampata prima di "Assistente: Sono 2500 m."
def test_convertitore_fallito_non_stampa():  # strumento_finto('{"errore": "x", "tipo": "strumento"}'): nessuna riga "[convertitore:"
def test_benvenuto_con_strumenti_mcp():      # strumenti_mcp=["converti_unita"] → "Strumenti MCP: converti_unita"; senza → nessuna riga "Strumenti MCP"
```

  - **Avvio unico** (`tests/test_avvio_unico.py`), con il server reale e senza LM Studio. Monkeypatch su `assistente.__main__`:
    - `load_dotenv` → no-op;
    - `verifica_server` → no-op;
    - `crea_modello` → `ModelloFinto([AIMessage("ciao")])`;
    - `LOG_ASSISTENTE`/`LOG_SERVER` → `tmp_path`;
    - `esegui_sessione` → un involucro che passa `leggi` da una lista `["ciao", "esci"]` e `scrivi=stampate.append`;
    - `configura_registro` → la versione reale su `tmp_path`, con pulizia degli handler come nel Task 5.

    L'ambiente si imposta con `monkeypatch.setenv`.

```python
def test_avvio_completo(...):                # main() == 0; "Strumenti MCP: converti_unita" in stampate; il Popen registrato è terminato;
                                             # LOG_SERVER e LOG_ASSISTENTE esistono; "catalogo" nel log dell'assistente
def test_porta_occupata_esce_con_errore(...):  # porta occupata da un socket: main() == 1, stderr contiene "Errore: Porta" e nessun traceback
def test_porta_mancante(...):                # MCP_PORTA assente: main() == 1, stderr contiene "MCP_PORTA"
```

- [ ] **Step 2:** `python -m pytest tests/test_configurazione.py tests/test_terminale.py tests/test_avvio_unico.py -v`. Atteso: FAIL sui nuovi test.

- [ ] **Step 3: implementare**
  - **`configurazione.py`**:
    - `OBBLIGATORIE` comprende `MCP_PORTA`;
    - la conversione accetta solo cifre (`isdigit`) nell'intervallo, altrimenti `ErroreConfigurazione(f"MCP_PORTA non valida: '{valore}'. Usa un numero intero tra 1024 e 65535, per esempio 8765.")`.
  - **`terminale.py`**:
    - `_righe_orologio` diventa `_righe_strumenti`;
    - per i ToolMessage con `status != "error"`, il nome `converti_unita` (costante locale `NOME_CONVERTITORE`, senza importare `server_mcp`) produce `f"[convertitore: {valore} {da} → {a}]"` dagli argomenti della richiesta;
    - il benvenuto stampa `Strumenti MCP: <nomi separati da ", ">` se `strumenti_mcp` non è vuoto, subito dopo la riga del fuso.
  - **`__main__.py`**, in ordine:
    1. `load_dotenv`;
    2. `carica_configurazione`;
    3. `configura_registro(LOG_ASSISTENTE)`;
    4. `verifica_server`;
    5. `rileva_fuso`;
    6. `with avvia_server_mcp(config.porta_mcp, LOG_SERVER) as avviato:`, poi `strumenti = unisci_strumenti([crea_strumento_orologio()], avviato.strumenti)`, poi grafo e `esegui_sessione(grafo, fuso, strumenti_mcp=[s.name for s in avviato.strumenti])`.

    `ErroreServerMCP` si aggiunge alle eccezioni che stampano `Errore: …` su stderr e restituiscono 1.
  - **`.env.example`**: aggiungere `# Porta locale del server MCP avviato dall'assistente` e `MCP_PORTA=8765`.
  - **`.gitignore`**: aggiungere `logs/`.

- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(avvio): avvia agente e server MCP con un solo comando` con i file del task.

---

### Task 7: Docker e prove reali

**Files:**
- Modify: `Dockerfile` (`COPY server_mcp/ server_mcp/` dopo la copia di `assistente/`), `compose.yaml` (`volumes: ["./logs:/app/logs"]`), `.dockerignore` (`logs`), `tests/test_reale_docker.py`
- Create: `tests/test_reale_convertitore.py`

**Interfaces:**
- Consumes: tutto quanto sopra.

- [ ] **Step 1: controllare il `.env` reale**
  - Verificare che contenga `MCP_PORTA`.
  - Se manca, **chiedere all'utente** di aggiungere `MCP_PORTA=8765`. Il `.env` è suo: non modificarlo senza il suo consenso.
  - Verificare che LM Studio risponda e che Docker Desktop sia acceso.

- [ ] **Step 2: scrivere `tests/test_reale_convertitore.py`** (`pytestmark = pytest.mark.lmstudio`)

La fixture `ambiente` (modulo):
- `load_dotenv`, `carica_configurazione`, `verifica_server`;
- `configura_registro(LOG_ASSISTENTE)` e `avvia_server_mcp(config.porta_mcp, LOG_SERVER)` aperto per tutto il modulo, con i log reali come prova;
- grafo con `unisci_strumenti([crea_strumento_orologio()], avviato.strumenti)`.

```python
CASI = [
    ("Quanti metri sono 2,5 km?", (2.5, "km", "m"), 2500),
    ("Converti 750 ml in litri", (750, "ml", "l"), 0.75),
    ("Quanti grammi sono 3 kg?", (3, "kg", "g"), 3000),
    ("Quanto sono 100 °F in gradi Celsius?", (100, "°F", "°C"), 37.78),
    ("Converti 37 °C in Fahrenheit", (37, "°C", "°F"), 98.6),
]
# Per ogni caso, sessione nuova. Criterio dalla spec (5 su 5, correzione ammessa), sull'ULTIMA chiamata a converti_unita del turno:
#   float(args["valore"]) == valore atteso, args["da"]/["a"] attesi;
#   il suo ToolMessage (stesso tool_call_id) ha status "success" e json["risultato"] == atteso;
#   la risposta finale contiene una delle forme_del_numero(atteso).
# Stampare domanda, tutte le chiamate (anche quelle fallite prima della correzione), risultati e risposta.
```

`forme_del_numero(x)`:
- per un intero: `str(x)`, più per `x >= 1000` le forme con `.` e `,` come separatore delle migliaia;
- per un decimale: `repr` con `.` e con `,`, più l'arrotondamento a 1 decimale con `.` e con `,`.

- [ ] **Step 3: aggiungere `test_convertitore_in_docker` a `tests/test_reale_docker.py`**
  - `esegui` diventa `esegui(comando, ingresso=INGRESSO)`;
  - con l'ingresso `"Quanti metri sono 2,5 km?\nesci\n"`, tramite `avvia.ps1 -SenzaTty`:
    - codice 0;
    - `"Strumenti MCP: converti_unita"` e `"[convertitore:"` in stdout;
    - `logs/assistente.log` e `logs/server_mcp.log` sull'host contengono `tool=converti_unita`.

- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS, prove reali `skipped`.
- [ ] **Step 5:** `python -m pytest --lmstudio -m lmstudio -v -s`. Atteso: i 5 casi del convertitore e i casi dell'orologio PASS.
  - Se un caso fallisce: al massimo due ritocchi alla descrizione del tool o alla riga del messaggio di sistema, rieseguendo ogni volta tutti i test automatici.
  - Se fallisce ancora: fermarsi e riportare all'utente i casi falliti con le chiamate stampate, proponendo di cambiare solo `LMSTUDIO_MODEL`.
- [ ] **Step 6:** `python -m pytest --docker -m docker -v -s`. Atteso: tutti PASS, compreso il nuovo.
- [ ] **Step 7:** commit `test(reale): aggiungi le prove reali del convertitore e il supporto Docker` con `Dockerfile`, `compose.yaml`, `.dockerignore`, `tests/test_reale_convertitore.py` e `tests/test_reale_docker.py`.

---

### Task 8: README e CLAUDE.md

**Files:**
- Modify: `README.md`, `../CLAUDE.md`

- [ ] **Step 1: aggiornare il README**, riportando solo comandi eseguiti con successo nei task precedenti:
  - **Configurazione**: `MCP_PORTA`, da aggiungere al `.env` esistente;
  - **Avvio diretto**: avvia anche il server, e la riga `Strumenti MCP: …`;
  - avvio del solo server: `python -m server_mcp --porta 8765`, per MCP Inspector o altri client, con URL `http://127.0.0.1:8765/mcp`;
  - **Log**: i due file, cosa contengono e come confrontarli;
  - **Test**: i tempi più lunghi dei test con server reale e la nuova prova reale;
  - **Diagnosi**: la tabella per livelli della spec, sezione 11.
- [ ] **Step 2: aggiornare `../CLAUDE.md`**, come dice la spec alla sezione 11:
  - struttura (`server_mcp/`, `client_mcp.py`, `avvio_server.py`, `registro.py`, `logs/`);
  - nei «Confini», MCP fa parte del progetto: solo gli strumenti concordati, uno alla volta;
  - nelle «Scelte tecniche», il codice è sincrono tranne il ponte MCP.
- [ ] **Step 3:** rileggere i comandi del README confrontandoli con quelli eseguiti nei Task 6 e 7. `python -m pytest -q`: tutti PASS.
- [ ] **Step 4:** commit `docs: documenta il convertitore MCP, i log e la diagnosi` con `assistente-laboratorio/README.md` e `CLAUDE.md`.
