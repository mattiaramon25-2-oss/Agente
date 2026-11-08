# Passo 4 — Catalogo locale — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** due strumenti MCP sullo stesso file di dati, `search_catalog(query, max_results)` e `get_item(code)`, con descrizioni abbastanza distinte da permettere al modello di scegliere quello giusto.

**Architecture:** il catalogo dei corsi è `risorse/catalogo_corsi.json`. La logica di ricerca e di dettaglio sta in `logica/catalogo.py`, e il server registra i due strumenti con `esegui_registrato`. L'agente non cambia: gli strumenti arrivano dalla discovery.

**Tech Stack:** come nel passo 1.

**Spec:** `docs/superpowers/specs/2026-11-08-strumenti-lezione-5-design.md`, sezioni 5.5 e 13.

**Branch:** `dev-catalogo`, creato da `dev`. Se il passo 3 non è ancora unito, il branch parte da `dev-scadenze`.

## Global Constraints

Valgono quelli del passo 1. In più:

- **Ogni corso** ha `codice`, `titolo`, `sede` e `durata_ore` (intero). I codici sono unici e il file contiene da 10 a 15 corsi immaginari dell'ITS.
- **Corsi obbligatori** nel file, che servono alle prove reali:
  - `{"codice": "DLL-01", "titolo": "Deep Learning e LLM: costruire chatbot e agenti", "sede": "Pordenone", "durata_ore": 120}`;
  - almeno due corsi con `Python` nel titolo.

  Nessun titolo contiene `astrofisica`.
- **`search_catalog`:**
  - `query` è un testo obbligatorio, non vuoto dopo `strip`;
  - `max_results` è facoltativo, intero da 1 a 20, predefinito 5;
  - cerca come sottostringa senza distinguere maiuscole e minuscole in `codice`, `titolo` e `sede`, nell'ordine del file;
  - risultato: `{"query": <query>, "risultati": [{"codice", "titolo", "sede"}...], "totale": <numero di corrispondenze, prima del taglio>}`.
- **`get_item`:** `code` deve corrispondere esattamente, e il risultato è il corso completo.
- **Descrizioni** (testo esatto):
  - `search_catalog`: `Cerca corsi nel catalogo dell'ITS per parola (titolo, sede o codice). Restituisce un elenco breve senza dettagli; per durata e dettagli usa get_item con il codice.`;
  - `get_item`: `Restituisce tutti i dettagli (titolo, sede, durata in ore) di un corso del catalogo dato il suo codice esatto, per esempio DLL-01.`
- **Messaggi d'errore:**
  - `La ricerca richiede una parola non vuota.`;
  - `max_results deve essere un intero tra 1 e 20.`;
  - `Nessun corso con codice '<code>'. Usa prima search_catalog per trovare il codice.`

## Review Focus

1. **Una ricerca senza risultati non è un errore:** lista vuota e `totale == 0`, senza elementi inventati. Lo verifica il Task 1 (`test_nessun_risultato`).
2. **`max_results` come testo (`"3"`) o come booleano:** il primo è accettato, il secondo rifiutato, con la stessa regola del convertitore. Lo verifica il Task 1.
3. **Maiuscole e spazi** (`"  python "`): trova i corsi di Python. Lo verifica il Task 1.
4. **File del catalogo malformato o con codici duplicati:** il server non deve partire in silenzio con dati sbagliati, quindi il caricamento fallisce con un messaggio chiaro. Lo verifica il Task 1 (`test_catalogo_malformato`).
5. **Domanda che richiede due chiamate** (ricerca, poi dettaglio): resta dentro il limite di 3 giri. Lo verifica il Task 3 (prova reale).

---

### Task 0: branch

- [ ] **Step 1:** `git switch -c dev-catalogo`, partendo dal branch indicato nell'intestazione.

---

### Task 1: dati e logica del catalogo

**Files:**
- Create: `risorse/catalogo_corsi.json`, `logica/catalogo.py`
- Test: `tests/test_catalogo.py`

**Interfaces:**
- Produces: `PERCORSO_CATALOGO: Path`, `carica_catalogo(percorso: Path = PERCORSO_CATALOGO) -> list[dict]`, `cerca(catalogo: list[dict], query: object, max_results: object = 5) -> dict`, `dettaglio(catalogo: list[dict], code: object) -> dict`.

- [ ] **Step 1: scrivere `risorse/catalogo_corsi.json`**, come lista JSON di oggetti con i vincoli dei Global Constraints.
- [ ] **Step 2: scrivere i test**, con un catalogo piccolo definito nel test, più due test sul file reale:

```python
CORSI = [{"codice": "PY-01", "titolo": "Python di base", "sede": "Udine", "durata_ore": 40},
         {"codice": "PY-02", "titolo": "Python per l'analisi dati", "sede": "Pordenone", "durata_ore": 60},
         {"codice": "DLL-01", "titolo": "Deep Learning e LLM", "sede": "Pordenone", "durata_ore": 120}]

def test_ricerca():
    assert cerca(CORSI, "  python ") == {"query": "  python ", "totale": 2, "risultati": [
        {"codice": "PY-01", "titolo": "Python di base", "sede": "Udine"},
        {"codice": "PY-02", "titolo": "Python per l'analisi dati", "sede": "Pordenone"}]}

def test_taglio_e_totale():
    r = cerca(CORSI, "o", max_results="1")
    assert len(r["risultati"]) == 1 and r["totale"] == 3

def test_nessun_risultato():
    assert cerca(CORSI, "astrofisica") == {"query": "astrofisica", "risultati": [], "totale": 0}

@pytest.mark.parametrize("query", ["", "   ", None, 3])
def test_query_non_valida(query):
    with pytest.raises(ErroreStrumento, match="parola non vuota"): cerca(CORSI, query)

@pytest.mark.parametrize("n", [0, 21, True, 2.5, "tre"])
def test_max_results_non_valido(n):
    with pytest.raises(ErroreStrumento, match="tra 1 e 20"): cerca(CORSI, "python", n)

def test_dettaglio():
    assert dettaglio(CORSI, "DLL-01") == CORSI[2]

@pytest.mark.parametrize("code", ["dll-01", "XX-99", "", None])
def test_codice_inesistente(code):
    with pytest.raises(ErroreStrumento, match="Usa prima search_catalog"): dettaglio(CORSI, code)

def test_file_reale():
    corsi = carica_catalogo()
    assert 10 <= len(corsi) <= 15 and len({c["codice"] for c in corsi}) == len(corsi)
    assert dettaglio(corsi, "DLL-01")["durata_ore"] == 120 and cerca(corsi, "python")["totale"] >= 2
    assert cerca(corsi, "astrofisica")["totale"] == 0

def test_catalogo_malformato(tmp_path):   # codice duplicato, poi campo mancante: ValueError con il nome del file
```

- [ ] **Step 3:** `python -m pytest tests/test_catalogo.py -v`. Atteso: FAIL.
- [ ] **Step 4: implementare.**
  - `max_results` segue la stessa regola dei giorni del passo 3: `int` non `bool`, `float` intero o testo di sole cifre.
  - `carica_catalogo` valida campi, tipi e unicità dei codici. Se qualcosa non va solleva `ValueError(f"Catalogo non valido in {percorso}: …")`: è un errore di avvio del server, non dello strumento.
- [ ] **Step 5:** `python -m pytest tests/test_catalogo.py -v`. Atteso: tutti PASS.
- [ ] **Step 6:** commit `feat(logica): aggiungi il catalogo dei corsi con ricerca e dettaglio`.

---

### Task 2: `search_catalog` e `get_item` nel server MCP

**Files:**
- Modify: `server_mcp/server.py`, `assistente/grafo.py` (una riga del messaggio di sistema), `tests/test_grafo.py`
- Test: `tests/test_server_mcp.py`

**Interfaces:**
- Produces: `NOME_RICERCA = "search_catalog"`, `NOME_DETTAGLIO = "get_item"`. Il catalogo si carica una volta in `crea_server`.

- [ ] **Step 1: test**
  - Il catalogo MCP guadagna i due nomi.
  - Lo schema di `search_catalog` ha `required == ["query"]`, `max_results` di tipo `integer` con `default == 5`; lo schema di `get_item` ha `required == ["code"]`.
  - `search_catalog` con `{"query": "python"}` dà `totale >= 2`.
  - `get_item` con `{"code": "XX-99"}` dà un errore MCP con `Usa prima search_catalog`.
  - Le due descrizioni sono diverse e contengono rispettivamente `Cerca` e `dettagli`.
  - In `test_grafo.py`, il messaggio di sistema contiene `catalogo`.
- [ ] **Step 2:** `python -m pytest tests/test_server_mcp.py tests/test_grafo.py -v`. Atteso: FAIL.
- [ ] **Step 3: implementare.**
  - Registrazione con `Annotated[Any, WithJsonSchema(...)]`. Per `max_results` si usa `{"type": "integer", "minimum": 1, "maximum": 20, "default": 5}` con valore predefinito Python `5`.
  - Il messaggio di sistema guadagna: `Per domande sui corsi dell'ITS usa gli strumenti del catalogo e non inventare corsi che non compaiono nei risultati.`
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(server): esponi ricerca e dettaglio del catalogo via MCP`.

---

### Task 3: prove reali, documentazione e checkpoint

**Files:**
- Create: `tests/test_reale_catalogo.py`, `docs/superpowers/checkpoint/AAAA-MM-GG-catalogo.md`
- Modify: `README.md`, `../CLAUDE.md` (struttura: `risorse/catalogo_corsi.json`)

- [ ] **Step 1: scrivere `tests/test_reale_catalogo.py`** con `ambiente_reale()`. Ogni caso parte da una sessione nuova.

  | Domanda | Evidenza attesa |
  |---|---|
  | «Quali corsi di Python ci sono nel catalogo?» | almeno una `search_catalog` con una `query` che contiene `python`, senza distinguere maiuscole; la risposta nomina almeno un titolo restituito |
  | «C'è un corso di astrofisica?» | `search_catalog` con `totale == 0`; la risposta non contiene codici che non sono nel file |
  | «Quante ore dura il corso di Deep Learning e LLM?» | `search_catalog` seguita da `get_item` con `code == "DLL-01"` nello stesso turno; la risposta contiene `120` |

  Poi l'**errore controllato**: invocazione diretta di `get_item` con `{"code": "XX-99"}`. Il risultato ha `tipo == "strumento"`. In ogni caso il log dice quale strumento è stato scelto (slide 28), e lo si stampa.
- [ ] **Step 2:** `python -m pytest -q`, poi `python -m pytest --lmstudio -m lmstudio -v -s`. Stessa regola di fallimento dei passi precedenti.
- [ ] **Step 3: README**: i due strumenti, dove si trova il catalogo, come modificarlo e che il server lo rilegge solo al riavvio.
- [ ] **Step 4: checkpoint** con **Fatto**, **Da fare** (passo 5) e **Stato attuale**.
- [ ] **Step 5:** commit `test(reale): prove reali del catalogo e documentazione`.
- [ ] **Step 6:** **chiedere all'utente l'approvazione esplicita** per unire `dev-catalogo` in `main`.
