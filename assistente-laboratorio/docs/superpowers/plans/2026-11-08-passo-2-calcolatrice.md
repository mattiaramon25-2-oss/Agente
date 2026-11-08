# Passo 2 — Calcolatrice sicura nelle varianti MCP e locale — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** lo strumento `calcola` esposto dal server MCP e, in alternativa, come `@tool` locale nell'agente. Le due versioni sono identiche nel contratto, e la variante attiva si sceglie con `VARIANTE_CALCOLATRICE`.

**Architecture:**
- **Logica:** la valutazione sicura sta in `logica/calcolatrice.py` e usa l'albero `ast` filtrato su una lista chiusa di nodi, con aritmetica `Decimal`.
- **Variante MCP:** il server la registra con `esegui_registrato`.
- **Variante locale:** l'agente la registra con `@tool` in `assistente/calcolatrice_locale.py`.
- **Scelta della variante:** `assistente/varianti.py` crea il sostituto, e `seleziona_strumenti` toglie la versione MCP quando la variante è `locale`.

**Tech Stack:** solo la libreria standard per la logica; il resto come nel passo 1.

**Spec:** `docs/superpowers/specs/2026-11-08-strumenti-lezione-5-design.md`, sezioni 5.3, 6 e 13.

**Branch:** `dev-calcolatrice`, creato da `dev`. Se il passo 1 non è ancora unito, il branch parte da `dev-infrastruttura-mcp`.

## Global Constraints

Valgono quelli del piano del passo 1 (`2026-11-08-passo-1-infrastruttura-mcp.md`). In più:

- **Nome e argomento:** lo strumento si chiama `calcola`, con un unico argomento obbligatorio `espressione` di tipo testo.
- **Descrizione** (testo esatto, identico nelle due varianti): `Calcola un'espressione aritmetica con numeri decimali (punto come separatore), + - * / % ** e parentesi. Esempio: espressione="(3 + 4) * 2".`
- **Limiti:**
  - espressione al massimo di 200 caratteri;
  - esponente intero, in valore assoluto al massimo 1000;
  - un risultato in valore assoluto maggiore o uguale a `1e300` è «troppo grande»;
  - le divisioni non esatte si arrotondano a 15 cifre significative.
- **Risultato:** `{"espressione": <testo ricevuto>, "risultato": <numero>}`. Un intero si scrive senza `.0`.
- **Variabile `VARIANTE_CALCOLATRICE`:** obbligatoria, con valori `mcp` o `locale`.
- **Origine:** la versione locale ha `metadata={"origine": "locale"}`.

## Review Focus

1. **Espressioni «da attacco»** (`__import__('os')`, `().__class__`, `9**9**9`, `2**10000`, `10**999 * 10**999`): danno un rifiuto immediato, senza bloccare il programma e senza eseguire codice. Lo verifica il Task 1 (`test_rifiuti`).
2. **Numeri che Python accetterebbe ma la specifica no** (`1_000`, `1e3`, `0x10`): vanno rifiutati. Lo verifica il Task 1 (`test_rifiuti`).
3. **Variante dichiarata e variante usata:** con `locale`, la chiamata non arriva al server, quindi nel log del server non c'è una riga `tool=calcola`. Lo verifica il Task 4 (`test_variante_locale_non_tocca_il_server`).
4. **Contratti divergenti:** se qualcuno modifica la docstring locale o la descrizione MCP, un test se ne accorge. Lo verifica il Task 3 (`test_contratto_identico`).
5. **`.env` senza `VARIANTE_CALCOLATRICE`:** messaggio chiaro che elenca i valori ammessi. Lo verifica il Task 4.

---

### Task 0: branch

- [ ] **Step 1:** `git switch -c dev-calcolatrice`, partendo dal branch indicato nell'intestazione.

---

### Task 1: logica della calcolatrice

**Files:**
- Create: `logica/calcolatrice.py`
- Test: `tests/test_calcolatrice.py`

**Interfaces:**
- Produces: `LUNGHEZZA_MASSIMA = 200`, `ESPONENTE_MASSIMO = 1000`, `calcola(espressione: object) -> dict`, che solleva `ErroreStrumento`.

- [ ] **Step 1: scrivere i test**

```python
@pytest.mark.parametrize("espressione, atteso", [
    ("(3 + 4) * 2", 14), ("0.1 + 0.2", 0.3), ("2 + 3 * 4", 14), ("2 ** 3 ** 2", 512), ("-2 ** 2", -4),
    ("10 / 4", 2.5), ("1 / 3", 0.333333333333333), ("7 % 3", 1), ("-7 % 3", -1), ("4 / 2", 2),
    ("2 ** -1", 0.5), ("  5  ", 5), ("+3", 3),
])
def test_calcoli(espressione, atteso):
    r = calcola(espressione)
    assert r == {"espressione": espressione, "risultato": atteso} and type(r["risultato"]) is type(atteso)

@pytest.mark.parametrize("espressione, frammento", [
    ("__import__('os')", "non consentit"), ("().__class__", "non consentit"), ("abs(-1)", "non consentit"),
    ("1_000 + 1", "non consentit"), ("1e3", "non consentit"), ("0x10", "non consentit"), ("7 // 2", "non consentit"),
    ("2,5 + 1", "punto"), ("", "vuota"), ("   ", "vuota"), ("1+" * 101 + "1", "200 caratteri"),
    ("(1 + 2", "sintassi"), ("1 / 0", "zero"), ("5 % 0", "zero"),
    ("2 ** 0.5", "Esponente"), ("2 ** 10000", "Esponente"), ("9 ** 9 ** 9", "Esponente"),
    ("10 ** 999 * 10 ** 999", "troppo grande"),
])
def test_rifiuti(espressione, frammento):
    with pytest.raises(ErroreStrumento, match=frammento):
        calcola(espressione)

@pytest.mark.parametrize("valore", [None, 14, True, ["1+1"]])
def test_non_testo(valore):
    with pytest.raises(ErroreStrumento, match="testo"):
        calcola(valore)
```

- [ ] **Step 2:** `python -m pytest tests/test_calcolatrice.py -v`. Atteso: FAIL.
- [ ] **Step 3: implementare `calcola`.**
  - **Controlli preliminari, in quest'ordine:**
    1. un valore non testo dà `L'espressione deve essere un testo.`;
    2. un testo vuoto dopo `strip` dà `Espressione vuota.`;
    3. più di 200 caratteri dà `Espressione troppo lunga: al massimo 200 caratteri.`;
    4. la presenza di `,` dà `Usa il punto come separatore decimale, per esempio 2.5.`;
    5. un carattere fuori da `0-9 . + - * / % ( )` e dallo spazio dà `Carattere non consentito: '<c>'. Sono ammessi numeri, + - * / % ** e parentesi.`
  - **Analisi:** poi `ast.parse(testo, mode="eval")`; un `SyntaxError` dà `Espressione non valida: errore di sintassi.` Una visita ricorsiva accetta solo:
    - `Expression`;
    - `BinOp` con `Add`, `Sub`, `Mult`, `Div`, `Mod` e `Pow`;
    - `UnaryOp` con `USub` e `UAdd`;
    - `Constant`, letto come `Decimal(ast.get_source_segment(testo, nodo))`.

    Ogni altro nodo, `//` compreso, dà `Operazione non consentita.`
  - **Calcolo:**
    - un contesto `Decimal` locale con precisione 50;
    - un divisore zero in `/` o `%` dà `Divisione per zero.`;
    - in `**`, un esponente non intero o con valore assoluto oltre 1000 dà `Esponente non ammesso: deve essere un intero tra -1000 e 1000.`, prima di calcolare;
    - dopo ogni operazione, se `abs(valore) >= Decimal("1e300")`, l'errore è `Risultato troppo grande.` Va gestita anche l'`InvalidOperation`/`Overflow` di `Decimal`.
  - **Uscita:** `int(valore)` se è intero, altrimenti `float(round(valore, 15 cifre significative))`.
- [ ] **Step 4:** `python -m pytest tests/test_calcolatrice.py -v`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(logica): aggiungi la calcolatrice sicura senza eval`.

---

### Task 2: `calcola` nel server MCP

**Files:**
- Modify: `server_mcp/server.py`
- Test: `tests/test_server_mcp.py`

**Interfaces:**
- Consumes: `logica.calcolatrice.calcola`; `esegui_registrato` (passo 1).
- Produces: `NOME_CALCOLATRICE = "calcola"` e `DESCRIZIONE_CALCOLATRICE` (testo dei Global Constraints) in `server_mcp/server.py`.

- [ ] **Step 1: test**
  - `test_catalogo` si aspetta `{"converti_unita", "ora_corrente", "calcola"}`.
  - Nuovi test:

```python
def test_calcola_via_mcp():
    r = con_client(lambda c: c.call_tool("calcola", {"espressione": "(3 + 4) * 2"}))
    assert r.structured_content == {"espressione": "(3 + 4) * 2", "risultato": 14}

def test_calcola_rifiuto_via_mcp():
    r = con_client(lambda c: c.call_tool("calcola", {"espressione": "__import__('os')"}, raise_on_error=False))
    assert r.is_error and "non consentit" in r.content[0].text
```

- [ ] **Step 2:** `python -m pytest tests/test_server_mcp.py -v`. Atteso: FAIL.
- [ ] **Step 3:** registrare `calcola` con il parametro `espressione: Annotated[Any, WithJsonSchema({"type": "string", "description": "Espressione aritmetica, per esempio (3 + 4) * 2"})]` e la descrizione esatta.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(server): esponi la calcolatrice via MCP`.

---

### Task 3: variante locale con `@tool`

**Files:**
- Create: `assistente/calcolatrice_locale.py`
- Test: `tests/test_calcolatrice_locale.py`

**Interfaces:**
- Consumes: `logica.calcolatrice.calcola`; `TIPO_STRUMENTO` (passo 1).
- Produces: `crea_calcolatrice_locale() -> BaseTool`, con nome `calcola` e `metadata={"origine": "locale"}`.

- [ ] **Step 1: test**

```python
def test_contratto_identico():
    (mcp,) = [s for s in con_client(lambda c: c.list_tools()) if s.name == "calcola"]   # client in memoria, come in test_server_mcp
    locale = crea_calcolatrice_locale()
    schema = locale.tool_call_schema.model_json_schema()
    assert locale.name == mcp.name and locale.description == mcp.description
    assert schema["required"] == mcp.inputSchema["required"] == ["espressione"]
    assert schema["properties"]["espressione"]["type"] == mcp.inputSchema["properties"]["espressione"]["type"] == "string"

@pytest.mark.parametrize("espressione", ["(3 + 4) * 2", "0.1 + 0.2", "1 / 0", "__import__('os')", "2,5"])
def test_stesso_esito_delle_due_varianti(espressione):
    locale = json.loads(crea_calcolatrice_locale().invoke({"espressione": espressione}))
    r = con_client(lambda c: c.call_tool("calcola", {"espressione": espressione}, raise_on_error=False))
    if r.is_error:
        assert locale == {"errore": r.content[0].text, "tipo": "strumento"}
    else:
        assert locale == r.structured_content

def test_origine_locale():
    assert crea_calcolatrice_locale().metadata == {"origine": "locale"}
```

- [ ] **Step 2:** `python -m pytest tests/test_calcolatrice_locale.py -v`. Atteso: FAIL.
- [ ] **Step 3: implementare.**
  - Dentro `crea_calcolatrice_locale`, una funzione `def calcola(espressione: str) -> str:` decorata con `@tool`. La docstring è **esattamente** la descrizione dei Global Constraints: slide 19, il contratto nasce da firma e docstring.
  - Il corpo restituisce `json.dumps(logica.calcolatrice.calcola(espressione), ensure_ascii=False)`. In caso di `ErroreStrumento` restituisce `{"errore": str(e), "tipo": "strumento"}`.
  - Poi si imposta `metadata`.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(calcolatrice): aggiungi la variante locale con @tool`.

---

### Task 4: scelta della variante con `VARIANTE_CALCOLATRICE`

**Files:**
- Modify: `assistente/configurazione.py`, `assistente/varianti.py`, `assistente/avvio.py`, `.env.example`, `tests/test_configurazione.py`, `tests/test_avvio_unico.py`, `tests/test_varianti.py`

**Interfaces:**
- Consumes: `crea_calcolatrice_locale` (Task 3); `prepara_strumenti`, `seleziona_strumenti` e `Configurazione` (passo 1).
- Produces:
  - `Configurazione.variante_calcolatrice: str = "mcp"`;
  - `VARIANTI_CALCOLATRICE = ("mcp", "locale")`;
  - `varianti.crea_sostituti(config: Configurazione) -> list[BaseTool]`. Il passo 3 aggiunge un secondo argomento facoltativo, solo per parola chiave.

- [ ] **Step 1: test**
  - **Configurazione:**
    - `VARIANTE_CALCOLATRICE` mancante compare tra le mancanti;
    - `"MCP"`, `" locale "` e `"mcp"` sono accettati, normalizzati con `strip().lower()`;
    - `"remoto"` dà `VARIANTE_CALCOLATRICE non valida: 'remoto'. Valori ammessi: mcp, locale.`
  - **`test_varianti.py`:** `crea_sostituti` con `mcp` restituisce `[]`, con `locale` restituisce un tool `calcola` con origine `locale`.
  - **`test_avvio_unico.py`:**

```python
def test_variante_locale_non_tocca_il_server(...):   # VARIANTE_CALCOLATRICE=locale, modello finto: chiamata("calcola", {"espressione": "(3 + 4) * 2"}), AIMessage("14")
    # main() == 0; "calcola (locale)" e "[calcola · locale: (3 + 4) * 2]" nelle righe stampate;
    # LOG_ASSISTENTE contiene "origine=locale tool=calcola"; LOG_SERVER non contiene "tool=calcola"
def test_variante_mcp(...):                          # VARIANTE_CALCOLATRICE=mcp: "calcola (mcp)"; LOG_SERVER contiene "tool=calcola"
```

- [ ] **Step 2:** `python -m pytest tests/test_configurazione.py tests/test_varianti.py tests/test_avvio_unico.py -v`. Atteso: FAIL sui nuovi test.
- [ ] **Step 3: implementare.**
  - `carica_configurazione` legge e valida la variante.
  - `crea_sostituti` restituisce `[crea_calcolatrice_locale()]` se la variante è `locale`.
  - `prepara_strumenti` passa `crea_sostituti(config)` a `seleziona_strumenti`, e scrive nel log `varianti calcolatrice=<v>`.
  - In `.env.example`, un commento su cosa cambia, seguito da `VARIANTE_CALCOLATRICE=mcp`.
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(varianti): scegli la variante della calcolatrice dal .env`.

---

### Task 5: prove reali, documentazione e checkpoint

**Files:**
- Create: `tests/test_reale_calcolatrice.py`
- Modify: `README.md`, `../CLAUDE.md` (struttura: `calcolatrice_locale.py`)
- Create: `docs/superpowers/checkpoint/AAAA-MM-GG-calcolatrice.md`

- [ ] **Step 1: controllare il `.env` reale.** Se manca `VARIANTE_CALCOLATRICE`, chiedere all'utente di aggiungerla.
- [ ] **Step 2: scrivere `tests/test_reale_calcolatrice.py`** (`pytestmark = pytest.mark.lmstudio`), parametrizzato su `variante in ("mcp", "locale")`. Ogni caso apre `ambiente_reale({"VARIANTE_CALCOLATRICE": variante})`.
  - **Domanda «Quanto fa (3+4)*2?»:**
    - l'ultima chiamata a `calcola` del turno ha un ToolMessage `success` con `risultato == 14`;
    - la risposta contiene `14`;
    - nel log compare `origine=<variante> tool=calcola`.
  - **Errore controllato** (slide 23): invocazione diretta dello strumento selezionato con `{"espressione": "__import__('os')"}`. Il risultato ha `tipo == "strumento"` e non ha `risultato`.
  - Si stampano domanda, chiamate, risultati e risposta.
- [ ] **Step 3:** `python -m pytest -q` (atteso: tutti PASS), poi `python -m pytest --lmstudio -m lmstudio -v -s` (atteso: PASS anche per i casi dei passi precedenti). Se fallisce: al massimo due ritocchi, poi si riporta l'esito. Il modello lo cambia l'utente.
- [ ] **Step 4: README**, con:
  - la variabile `VARIANTE_CALCOLATRICE`;
  - come confrontare le due varianti: stessa domanda, `.env` cambiato e riavvio;
  - dove si vede la differenza: riga del terminale e log del server.
- [ ] **Step 5: checkpoint** con **Fatto**, **Da fare** (passo 3) e **Stato attuale** (branch, ultimo commit, esiti).
- [ ] **Step 6:** commit `test(reale): prove reali della calcolatrice nelle due varianti e documentazione`.
- [ ] **Step 7:** **chiedere all'utente l'approvazione esplicita** per unire `dev-calcolatrice` in `main`.
