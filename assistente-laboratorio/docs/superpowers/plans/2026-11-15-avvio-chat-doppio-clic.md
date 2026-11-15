# Avvio della chat con un doppio clic — piano

> **Per chi esegue:** SOTTO-SKILL RICHIESTA: usare superpowers:subagent-driven-development (consigliata) oppure superpowers:executing-plans per eseguire il piano un task alla volta. I passi usano le caselle (`- [ ]`).

**Obiettivo:** un file `avvia-chat.cmd` che con un doppio clic accende ciò che manca e apre la chat nel browser.

**Architettura:** il `.cmd` lancia `python -m avvio_chat`. Il pacchetto `avvio_chat` ha i passi in `passi.py`, ognuno una funzione che riceve come parametri ciò che tocca il mondo esterno (esecuzione di comandi, richieste HTTP, browser, orologio). I servizi si avviano con `processo_in_attesa` di `assistente/avvio_server.py`, dentro un `ExitStack` che li spegne in ordine inverso.

**Tecnologie:** Python 3.14, libreria standard (`subprocess`, `urllib`, `webbrowser`, `contextlib`), `python-dotenv` già presente. Nessuna dipendenza nuova.

**Specifica:** `docs/superpowers/specs/2026-11-15-avvio-chat-doppio-clic-design.md`

## Vincoli globali

- Lavorare solo su `dev-avvio-chat`. Nessun merge in `main` e nessun push senza richiesta.
- Nessuna modifica a `compose.yaml`, `Dockerfile`, `requirements*.txt`, `frontend/`, `servizio_agente/`, `servizio_backend/`, `assistente/` (solo riuso).
- TDD: ogni comportamento parte da un test che fallisce. La suite `python -m pytest` resta verde.
- I test automatici non usano Docker, LM Studio, la rete né i dati dell'utente: comandi finti, porte libere scelte dal sistema, cartelle temporanee.
- Messaggi in italiano, che dicono che cosa sistemare. Codice sincrono, moduli piccoli.
- `avvia-chat.cmd` solo in ASCII, con fine riga CRLF.
- Il file non spegne mai ciò che non ha avviato e non tocca chat, note, `.env`.
- Commit: Conventional Commits in italiano, staging selettivo, nessuna riga `Co-Authored-By`.

## Punti da controllare

1. **Secondo doppio clic con tutto acceso.** Apre il browser, non avvia e non spegne niente, esce con 0. Test: `test_tutto_gia_acceso_apre_solo_il_browser`.
2. **Chat da terminale aperta.** `MCP_PORTA` occupata e agente spento: messaggio che lo dice, nessun processo avviato. Test: `test_porta_mcp_occupata_dice_di_chiudere_il_terminale`.
3. **Mancano `.venv` o `.env`.** La finestra resta aperta con il messaggio. Test: `test_cmd_controlla_la_venv`, `test_main_senza_env_esce_con_1`.
4. **Chiusura con la X.** Nessun processo rimasto: porte dell'agente, del back-end e del server MCP libere. Solo prova reale, task 3.
5. **Prima costruzione dell'immagine della pagina.** Può durare minuti: l'attesa di Compose è 600 secondi e la finestra dice di aspettare. Test: `test_container_usa_wait_e_attesa_lunga`.

---

### Task 1: Impostazioni e programmi esterni

**File:**
- Crea: `avvio_chat/__init__.py` (vuoto), `avvio_chat/passi.py`
- Test: `tests/test_avvio_chat.py`

**Interfacce prodotte:**

```python
ATTESA_DOCKER = 180.0
ATTESA_LMSTUDIO = 60.0
ATTESA_CONTAINER = 600.0
PORTA_FRONTEND_PREDEFINITA = 8780

@dataclass(frozen=True)
class Impostazioni:
    base_url: str          # LMSTUDIO_BASE_URL
    modello: str           # LMSTUDIO_MODEL
    porta_mcp: int
    porta_agente: int
    porta_backend: int
    porta_frontend: int
    # proprietà: url_agente, url_backend, url_chat → "http://127.0.0.1:<porta>"

def carica_impostazioni(env: Mapping[str, str]) -> Impostazioni
    # usa carica_configurazione, leggi_porta_agente, carica_configurazione_backend; FRONTEND_PORTA con leggi_porta

@dataclass(frozen=True)
class Esito:
    codice: int
    uscita: str            # stdout e stderr insieme

Esegui = Callable[[list[str], float], Esito]   # FileNotFoundError se il programma non esiste

def esegui_comando(comando: list[str], limite: float) -> Esito
    # subprocess.run nella cartella del progetto; alla scadenza Esito(124, "nessuna risposta entro N secondi")

def assicura_docker(esegui: Esegui, scrivi: Callable[[str], None], *, attesa: float = ATTESA_DOCKER,
                    pausa: Callable[[float], None] = time.sleep, orologio: Callable[[], float] = time.monotonic) -> None
def lmstudio_risponde(base_url: str, limite: float = 3.0) -> bool
def trova_lms() -> str | None      # shutil.which("lms"), poi ~/.lmstudio/bin/lms.exe
def assicura_lmstudio(imp: Impostazioni, esegui: Esegui, scrivi, *, risponde=lmstudio_risponde,
                      verifica=verifica_server, lms=trova_lms, attesa: float = ATTESA_LMSTUDIO,
                      pausa=time.sleep, orologio=time.monotonic) -> None
def assicura_container(esegui: Esegui, scrivi) -> None
```

Comandi esatti: `["docker", "info", "--format", "{{.ServerVersion}}"]`, `["docker", "desktop", "start"]`, `[<lms>, "server", "start"]`, `["docker", "compose", "up", "-d", "--wait", "database", "frontend"]`. Tutti gli errori sono `ErroreAvvio` (`assistente/errori.py`).

- [ ] **Passo 1: test delle impostazioni.** `test_impostazioni_dal_env` (porte 8765, 8767, 8768 e `url_chat == "http://127.0.0.1:8780"` senza `FRONTEND_PORTA`; con `FRONTEND_PORTA=8790` l'indirizzo cambia), `test_impostazioni_senza_password_del_database` (`ErroreConfigurazione` con `POSTGRES_PASSWORD` nel messaggio), `test_frontend_porta_non_valida`.
- [ ] **Passo 2:** eseguirli: falliscono perché `avvio_chat` non esiste.
- [ ] **Passo 3:** scrivere `Impostazioni` e `carica_impostazioni`; i test passano.
- [ ] **Passo 4: test di Docker**, con un `esegui` finto che registra i comandi e risponde da un copione:
  - `test_docker_acceso_non_avvia_niente`: `docker info` dà 0; nessun `docker desktop start`.
  - `test_docker_spento_lo_avvia_e_aspetta`: `docker info` dà 1, poi 1, poi 0; i comandi contengono una volta `["docker", "desktop", "start"]`.
  - `test_docker_che_non_parte`: `docker info` dà sempre 1, orologio finto oltre i 180 secondi; `ErroreAvvio` con «Docker Desktop non risponde».
  - `test_docker_non_installato`: `esegui` solleva `FileNotFoundError`; `ErroreAvvio` con «Docker non è installato».
- [ ] **Passo 5:** eseguirli, vederli fallire, scrivere `assicura_docker`, vederli passare.
- [ ] **Passo 6: test di LM Studio:**
  - `test_lmstudio_acceso_non_chiama_lms`.
  - `test_lmstudio_spento_avvia_il_server`: `risponde` dà False, False, True; i comandi contengono `[<lms>, "server", "start"]`; poi `verifica` è chiamata una volta.
  - `test_lmstudio_spento_senza_lms`: `lms` restituisce `None`; `ErroreAvvio` con «apri LM Studio».
  - `test_lmstudio_che_non_parte`: `risponde` sempre False oltre i 60 secondi; `ErroreAvvio`.
  - `test_modello_mancante_non_tocca_lms`: `risponde` True, `verifica` solleva `ErroreServer`; l'eccezione esce così com'è e nessun comando è stato eseguito.
- [ ] **Passo 7:** fallimento, `assicura_lmstudio`, successo.
- [ ] **Passo 8: test dei container:** `test_container_usa_wait_e_attesa_lunga` (comando esatto, limite 600), `test_container_che_falliscono` (codice 1 con uscita «port is already allocated»; `ErroreAvvio` che la contiene).
- [ ] **Passo 9:** fallimento, `assicura_container` ed `esegui_comando`, successo. `test_esegui_comando_vero` lancia `[sys.executable, "-c", "print('ciao')"]` e si aspetta `Esito(0, "ciao\n")`; con un limite di 0,2 secondi su uno `sleep` si aspetta il codice 124.
- [ ] **Passo 10:** `python -m pytest -q`; commit `feat(avvio-chat): impostazioni e avvio di Docker, LM Studio e container`.

---

### Task 2: Servizi, attesa e programma principale

**File:**
- Modifica: `avvio_chat/passi.py`
- Crea: `avvio_chat/__main__.py`, `tests/servizio_salute_finto.py`
- Test: `tests/test_avvio_chat.py`

**Interfacce:**
- Usa: `processo_in_attesa(comando, porta, percorso_log, prova, *, descrizione, variabile_porta, attesa)` e `porta_libera(porta)` da `assistente/avvio_server.py`; `Impostazioni`, `Esegui` del task 1.
- Produce:

```python
ATTESA_SERVIZIO = 60.0

def leggi_salute(url: str, limite: float) -> dict     # GET <url>/salute; solleva se non è un JSON con "stato": "ok"

@contextmanager
def servizio(descrizione: str, comando: list[str], porta: int, variabile_porta: str, log: Path,
             scrivi, *, salute=leggi_salute, attesa: float = ATTESA_SERVIZIO) -> Iterator[bool]
    # True se l'ha avviato questa funzione (e all'uscita lo spegne), False se era già acceso

def avvia_chat(imp: Impostazioni, ingresso: TextIO, scrivi, *, esegui: Esegui = esegui_comando,
               apri: Callable[[str], object] = webbrowser.open, comando_agente: list[str] | None = None,
               comando_backend: list[str] | None = None, cartella_log: Path = CARTELLA_LOG,
               senza_browser: bool = False, **opzioni_dei_passi) -> int

# avvio_chat/__main__.py
def main(argomenti: list[str] | None = None, ingresso: TextIO | None = None) -> int
```

`tests/servizio_salute_finto.py --porta N`: server della libreria standard che risponde a `GET /salute` con `{"stato": "ok"}` e a tutto il resto con 404.

- [ ] **Passo 1: test di `servizio`**, con il servizio finto vero e la fixture `popen_registrati`:
  - `test_servizio_avviato_e_spento`: dentro il `with` il valore è `True` e `/salute` risponde; dopo, il processo è terminato e la porta è libera.
  - `test_servizio_gia_acceso_non_si_tocca`: si avvia a parte il servizio finto; `servizio(...)` dà `False`, non crea processi e all'uscita il servizio finto risponde ancora.
  - `test_servizio_che_non_parte`: comando `[sys.executable, "-c", "print('Errore: prova'); raise SystemExit(1)"]`; `ErroreAvvio` che contiene «non è partito» e «Errore: prova».
- [ ] **Passo 2:** fallimento, `leggi_salute` e `servizio`, successo.
- [ ] **Passo 3: test di `avvia_chat`**, con `esegui` finto (Docker acceso, Compose riuscito), `risponde` e `verifica` finti, e come agente e back-end due servizi finti su porte libere:
  - `test_avvio_completo_ed_esci`: ingresso `"esci\n"`; codice 0; l'uscita contiene le cinque righe `[1/5]` … `[5/5]` e «La chat è accesa»; `apri` chiamata una volta con `imp.url_chat`; alla fine i due processi sono terminati.
  - `test_arresto_in_ordine_inverso`: il back-end termina prima dell'agente (si registrano gli istanti di `poll()` diverso da `None`).
  - `test_fine_input_spegne_come_esci`: ingresso vuoto.
  - `test_ctrl_c_spegne_tutto`: l'ingresso solleva `KeyboardInterrupt`; codice 0; processi terminati.
  - `test_tutto_gia_acceso_apre_solo_il_browser`: i due servizi finti avviati a parte; nessun processo creato; `apri` chiamata; codice 0 senza leggere l'ingresso; i servizi rispondono ancora.
  - `test_senza_browser`: `senza_browser=True`; `apri` mai chiamata.
  - `test_porta_mcp_occupata_dice_di_chiudere_il_terminale`: un socket occupa `imp.porta_mcp`, agente spento; `ErroreAvvio` con «chat da terminale»; nessun processo creato.
  - `test_backend_che_non_parte_spegne_l_agente`: comando del back-end che esce con 1; `ErroreAvvio`; il processo dell'agente è terminato.
- [ ] **Passo 4:** fallimento, `avvia_chat`, successo. Le uscite dei servizi vanno in `cartella_log / "avvio_agente.log"` e `"avvio_backend.log"`.
- [ ] **Passo 5: test di `main`:**
  - `test_main_senza_env_esce_con_1`: cartella temporanea come directory corrente, ambiente senza variabili; codice 1; su stderr «Errore: Variabili d'ambiente mancanti».
  - `test_main_riporta_gli_errori_di_avvio`: `avvia_chat` sostituita con una funzione che solleva `ErroreAvvio("prova")`; codice 1; stderr `Errore: prova`.
  - `test_main_passa_senza_browser`: `["--senza-browser"]` arriva a `avvia_chat`.
- [ ] **Passo 6:** fallimento, `__main__.py` (`configura_flussi`, `load_dotenv(override=False)`, `carica_impostazioni`, `avvia_chat`), successo.
- [ ] **Passo 7:** `python -m pytest -q`; commit `feat(avvio-chat): servizi, attesa di «esci» e programma principale`.

---

### Task 3: Il file `avvia-chat.cmd` e la prova reale

**File:**
- Crea: `avvia-chat.cmd`
- Test: `tests/test_avvio_chat.py`

Contenuto del file:

```bat
@echo off
rem Avvia la chat nel browser con un doppio clic. La logica sta in avvio_chat (python -m avvio_chat).
cd /d "%~dp0"
title Assistente del laboratorio - chat
if not exist ".venv\Scripts\python.exe" (
  echo Manca l'ambiente virtuale .venv. Segui "La prima volta" nel file AVVIO-RAPIDO.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m avvio_chat %*
if errorlevel 1 pause
```

- [ ] **Passo 1: test del file:** `test_cmd_solo_ascii_e_crlf` (ogni byte sotto 128; ogni riga finisce con `\r\n`), `test_cmd_controlla_la_venv` (contiene `if not exist ".venv\Scripts\python.exe"` e `pause`), `test_cmd_lancia_il_modulo` (contiene `-m avvio_chat %*` e `cd /d "%~dp0"`).
- [ ] **Passo 2:** fallimento, scrittura del file, successo; `python -m pytest -q`.
- [ ] **Passo 3: prova reale, primo avvio.** Con agente e back-end spenti (se sono accesi, li ferma l'utente o lo si chiede a lui): `cmd /c avvia-chat.cmd --senza-browser` con ingresso `esci`. Atteso: le cinque righe, codice 0; durante l'attesa `http://127.0.0.1:8780/api/salute` risponde `ok`; dopo, le porte dell'agente, del back-end e del server MCP sono libere.
- [ ] **Passo 4: prova reale, secondo avvio.** Con i servizi accesi a parte: il file dice che erano già accesi, esce con 0 e i servizi rispondono ancora.
- [ ] **Passo 5: prova reale, chiusura con la X.** Il file avviato in una finestra sua; chiusa la finestra, entro 10 secondi le tre porte sono libere. Se una resta occupata: test che lo riproduce, gestore della chiusura della console in `__main__.py` (`SetConsoleCtrlHandler` con `ctypes`), nuova prova.
- [ ] **Passo 6:** commit `feat(avvio-chat): file avvia-chat.cmd per il doppio clic`.

---

### Task 4: Documenti

**File:**
- Modifica: `AVVIO-RAPIDO.md` (in cima «Il modo più semplice: doppio clic su `avvia-chat.cmd`»; il modo B resta come avvio a mano; tabella degli errori con le righe nuove)
- Modifica: `README.md` (in «La chat nel browser» il doppio clic; in «Log» i due file nuovi)
- Modifica: `../CLAUDE.md` (struttura: `avvio_chat/` e `avvia-chat.cmd`; comandi)
- Modifica: `docs/studio/08-configurazione-avvio-docker.md` (una sezione nuova e un'idea nella scheda), `docs/studio/presentazioni/lezione-6.html` (la riga sullo step 9), `docs/studio/presentazioni/atlante.html` (didascalia dello schema `processi`)
- Modifica: `docs/superpowers/README.md`
- Crea: `docs/superpowers/checkpoint/2026-11-15-avvio-chat.md`

- [ ] **Passo 1:** aggiornare i documenti con i soli comandi eseguiti nel task 3 e i loro esiti.
- [ ] **Passo 2:** rieseguire la verifica delle pagine HTML modificate (nessun testo fuori dalla slide).
- [ ] **Passo 3:** `python -m pytest -q`; checkpoint con Fatto, Da fare, Stato attuale; commit `docs(avvio-chat): guida, README, capitolo 08 e checkpoint`.
