# Passo 6 — Meteo da Open-Meteo — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** lo strumento MCP `get_weather(city)`, che incapsula le API pubbliche di Open-Meteo (geocoding e forecast). Dichiara la città scelta e distingue sempre gli errori di rete da «città non trovata».

**Architecture:** `logica/meteo.py` riceve un `httpx.Client`, così i test usano `httpx.MockTransport` senza rete. Il server crea un client vero e registra lo strumento; nei test riceve il client simulato. È il caso «MCP sopra un servizio HTTP esterno» della slide 27.

**Tech Stack:** `httpx` 0.28.1 (fissato nel passo 3); il resto come nel passo 1.

**Spec:** `docs/superpowers/specs/2026-11-08-strumenti-lezione-5-design.md`, sezioni 5.7 e 13.

**Branch:** `dev-meteo`, creato da `dev`. Se il passo 5 non è ancora unito, il branch parte da `dev-note`.

## Global Constraints

Valgono quelli del passo 1. In più:

- **Geocoding:** `GET https://geocoding-api.open-meteo.com/v1/search` con `name=<city>`, `count=5`, `language=it`, `format=json`. Le corrispondenze sono in `results`; se non ce ne sono, la chiave `results` manca.
- **Forecast:** `GET https://api.open-meteo.com/v1/forecast` con `latitude`, `longitude`, `current=temperature_2m,weather_code,wind_speed_10m` e `timezone=auto`. I valori sono in `current`, con `current.time` nel formato `AAAA-MM-GGTHH:MM` e `utc_offset_seconds` alla radice.
- **Unità** nel risultato: `°C` e `km/h`, cioè i predefiniti di Open-Meteo.
- **Timeout:** 4 s per ciascuna richiesta, perché le due insieme restino sotto i 10 s del ponte MCP.
- **Città scelta:** la prima corrispondenza. `altre_corrispondenze` elenca le altre, al massimo 4, come `"Nome (regione, paese)"`. Una parte mancante si omette insieme alla sua virgola.
- **Risultato:** chiavi esattamente come nell'esempio della specifica (sezione 5.7). `ora_riferimento` è `current.time` con lo scarto ricavato da `utc_offset_seconds`, per esempio `2026-11-08T10:15+01:00`.
- **Descrizione** (testo esatto): `Restituisce il meteo attuale (temperatura in °C, vento in km/h, condizioni) per una città, usando il servizio pubblico Open-Meteo. Se il nome è ambiguo sceglie la prima corrispondenza e lo dichiara nel risultato.`
- **Messaggi d'errore:**
  - `Indica il nome di una città.`;
  - `Città non trovata: '<city>'.`;
  - `Servizio meteo: nessuna risposta entro 4 secondi.`;
  - `Servizio meteo non disponibile: <Tipo>: <messaggio>` (connessione impossibile o risposta `5xx`);
  - `Risposta non valida dal servizio meteo: <dettaglio>.` (JSON malformato, campi mancanti, stato inatteso).
- **Condizioni:** la tabella `DESCRIZIONI_WMO` copre i codici WMO usati da Open-Meteo: 0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99. Un codice sconosciuto dà `condizioni non classificate (codice <n>)`. Il testo italiano di ciascun codice è lasciato al costruttore.

## Review Focus

1. **Rete assente e città inesistente devono avere messaggi diversi.** Lo verifica il Task 1 (`test_errori`).
2. **Città ambigua** (`Paris`, `San Marco`): la scelta è dichiarata e le alternative elencate. Lo verifica il Task 1 (`test_citta_ambigua`).
3. **Risposta 200 senza `current`, o con campi `null`:** errore «risposta non valida», mai una temperatura `None` presentata come dato. Lo verifica il Task 1 (`test_errori`).
4. **Caratteri speciali nel nome** (`Forlì`, `Reggio nell'Emilia`): vanno passati come parametri e non concatenati nell'URL. Lo verifica il Task 1 (`test_parametri_della_richiesta`).
5. **Il container Docker non raggiunge Internet:** l'errore è di servizio non disponibile, distinto da un errore del server MCP. Lo verifica il passo 7 (prova Docker).

---

### Task 0: branch

- [ ] **Step 1:** `git switch -c dev-meteo`, partendo dal branch indicato nell'intestazione.

---

### Task 1: logica del meteo

**Files:**
- Create: `logica/meteo.py`
- Test: `tests/test_meteo.py`

**Interfaces:**
- Produces: `URL_GEOCODING`, `URL_FORECAST`, `TIMEOUT_METEO = 4.0`, `DESCRIZIONI_WMO: dict[int, str]`, `meteo_attuale(city: object, http: httpx.Client, timeout: float = TIMEOUT_METEO) -> dict`, che solleva `ErroreStrumento`.

- [ ] **Step 1: scrivere i test** con un `httpx.MockTransport` che smista per host:

```python
UDINE = {"name": "Udine", "admin1": "Friuli Venezia Giulia", "country": "Italia", "latitude": 46.06, "longitude": 13.24}
CORRENTE = {"utc_offset_seconds": 3600, "current": {"time": "2026-11-08T10:15", "temperature_2m": 8.4,
                                                    "weather_code": 2, "wind_speed_10m": 12.0}}

def test_risultato():
    r = meteo_attuale("Udine", client(geo={"results": [UDINE]}, forecast=CORRENTE))
    assert r == {"citta": {"nome": "Udine", "regione": "Friuli Venezia Giulia", "paese": "Italia",
                           "latitudine": 46.06, "longitudine": 13.24},
                 "altre_corrispondenze": [], "temperatura": {"valore": 8.4, "unita": "°C"},
                 "vento": {"valore": 12.0, "unita": "km/h"}, "condizioni": DESCRIZIONI_WMO[2],
                 "ora_riferimento": "2026-11-08T10:15+01:00", "fonte": "Open-Meteo"}

def test_citta_ambigua():
    altre = [{"name": "Paris", "admin1": "Texas", "country": "Stati Uniti", "latitude": 33.6, "longitude": -95.5}]
    r = meteo_attuale("Paris", client(geo={"results": [{**UDINE, "name": "Parigi", "admin1": "Île-de-France", "country": "Francia"}, *altre]}, forecast=CORRENTE))
    assert r["citta"]["nome"] == "Parigi" and r["altre_corrispondenze"] == ["Paris (Texas, Stati Uniti)"]

def test_parametri_della_richiesta():   # registra le richieste: name="Forlì", count=5, language=it; latitude/longitude dalla prima corrispondenza
                                        # current=temperature_2m,weather_code,wind_speed_10m, timezone=auto

@pytest.mark.parametrize("geo, forecast, frammento", [
    ({}, CORRENTE, "Città non trovata: 'Atlantide'"),
    ({"results": []}, CORRENTE, "Città non trovata"),
    (solleva(httpx.ConnectError("no rete")), CORRENTE, "Servizio meteo non disponibile: ConnectError"),
    (risposta(503), CORRENTE, "Servizio meteo non disponibile"),
    (solleva(httpx.ReadTimeout("lento")), CORRENTE, "nessuna risposta entro 4 secondi"),
    ({"results": [UDINE]}, solleva(httpx.ConnectTimeout("lento")), "nessuna risposta entro 4 secondi"),
    ({"results": [UDINE]}, testo("non json"), "Risposta non valida"),
    ({"results": [UDINE]}, {"utc_offset_seconds": 3600}, "Risposta non valida"),
    ({"results": [UDINE]}, {**CORRENTE, "current": {**CORRENTE["current"], "temperature_2m": None}}, "Risposta non valida"),
    ({"results": [{"name": "Udine"}]}, CORRENTE, "Risposta non valida"),
])
def test_errori(geo, forecast, frammento): ...   # la città è "Atlantide" nel primo caso, "Udine" negli altri

@pytest.mark.parametrize("city", ["", "   ", None, 3])
def test_citta_non_valida(city): ...             # "Indica il nome di una città", senza nessuna richiesta HTTP

def test_codice_sconosciuto():                   # weather_code 1234 → "condizioni non classificate (codice 1234)"
```

- [ ] **Step 2:** `python -m pytest tests/test_meteo.py -v`. Atteso: FAIL.
- [ ] **Step 3: implementare.**
  - Due richieste `http.get(url, params=..., timeout=timeout)`.
  - **Mappatura degli errori:**
    - `httpx.TimeoutException` → timeout;
    - un altro `httpx.TransportError` o uno stato `5xx` → non disponibile;
    - un altro stato diverso da 200, un `ValueError` sul JSON, o una chiave mancante, `None` o del tipo sbagliato (`KeyError`, `TypeError`) → risposta non valida.
  - La città richiesta si mostra con `strip()`.
- [ ] **Step 4:** `python -m pytest tests/test_meteo.py -v`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(logica): aggiungi il meteo attuale da Open-Meteo`.

---

### Task 2: `get_weather` nel server MCP

**Files:**
- Modify: `server_mcp/server.py` (`crea_server(*, ..., http: httpx.Client | None = None)`), `assistente/grafo.py` (riga del messaggio di sistema), `tests/test_grafo.py`
- Test: `tests/test_server_mcp.py`

**Interfaces:**
- Produces: `NOME_METEO = "get_weather"`. Senza `http`, il server crea un `httpx.Client()` alla creazione e lo usa per tutta la vita del processo.

- [ ] **Step 1: test**
  - **Catalogo:** contiene `get_weather` con `required == ["city"]`.
  - **Chiamata riuscita:** con `http` simulato restituisce `citta.nome == "Udine"`.
  - **Errori:**
    - con il geocoding vuoto, errore MCP con `Città non trovata`;
    - con `ConnectError`, errore MCP con `non disponibile`.

    Tutti e due vanno nel log del server con `esito=errore`.
  - **Messaggio di sistema:** contiene `città`.
  - **Nessun test usa la rete:** `con_client` passa sempre un `http` simulato.
- [ ] **Step 2:** `python -m pytest tests/test_server_mcp.py tests/test_grafo.py -v`. Atteso: FAIL.
- [ ] **Step 3: implementare.** Il messaggio di sistema guadagna: `Se lo strumento del meteo dichiara di aver scelto una città tra più corrispondenze, dillo all'utente nominando la città scelta.`
- [ ] **Step 4:** `python -m pytest -q`. Atteso: tutti PASS.
- [ ] **Step 5:** commit `feat(server): esponi il meteo via MCP`.

---

### Task 3: prove reali, documentazione e checkpoint

**Files:**
- Create: `tests/test_reale_meteo.py`, `docs/superpowers/checkpoint/AAAA-MM-GG-meteo.md`
- Modify: `README.md`

- [ ] **Step 1: controllo della rete senza modello.** Una richiesta diretta con `meteo_attuale("Udine", httpx.Client())`, eseguita a mano una volta. Conferma che i campi reali di Open-Meteo sono quelli dei Global Constraints. Se non lo sono, si corregge la logica e si aggiorna il test prima di proseguire, poi si riporta la differenza nel checkpoint.
- [ ] **Step 2: scrivere `tests/test_reale_meteo.py`** con `ambiente_reale()`. Richiede la rete; se manca, il test fallisce con l'errore di servizio non disponibile, che è proprio l'evidenza voluta.
  - «Che tempo fa a Udine?»: `get_weather` con una `city` che contiene `Udine`, ToolMessage `success`, e la risposta nomina Udine e contiene la temperatura restituita, arrotondata a 0 o 1 decimale.
  - **Errore controllato**: invocazione diretta con `{"city": "Xqzvbnmlkj"}`, che dà `tipo == "strumento"` e `Città non trovata`.
- [ ] **Step 3:** `python -m pytest -q`, poi `python -m pytest --lmstudio -m lmstudio -v -s`. Stessa regola di fallimento dei passi precedenti.
- [ ] **Step 4: README**, con:
  - lo strumento e la fonte (Open-Meteo, senza chiavi, uso non commerciale);
  - il requisito di rete;
  - nella diagnosi, «rete assente» distinta da «città non trovata».
- [ ] **Step 5: checkpoint** con **Fatto**, **Da fare** (passo 7) e **Stato attuale**.
- [ ] **Step 6:** commit `test(reale): prova reale del meteo e documentazione`.
- [ ] **Step 7:** **chiedere all'utente l'approvazione esplicita** per unire `dev-meteo` in `main`.
