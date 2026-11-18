# Quattro container con un solo comando (step 9) — piano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** agente e back-end diventano container accanto a database e pagina; `avvia-chat.cmd` li accende con `docker compose up -d` e li spegne alla chiusura della finestra, senza importare sull'host librerie bloccate da Smart App Control.

**Architecture:** il back-end legge i suoi tre indirizzi da variabili d'ambiente (predefiniti invariati); Compose ha un servizio `backend` nuovo, healthcheck e `restart: on-failure` per agente e back-end, la CLI nel profilo `cli`; nginx risolve il back-end a ogni richiesta. Il launcher `avvio_chat` usa solo libreria standard e `python-dotenv`, guarda quali container erano già accesi, aspetta `/api/salute` attraverso nginx e alla chiusura della console lancia `docker compose stop` in un processo staccato. La suite automatica gira in un container perché sull'host `psycopg` non si carica.

**Tech Stack:** Python 3.14, FastAPI/uvicorn, psycopg 3 (solo nei container), Docker Compose 5.5, nginx-unprivileged 1.30.6, PowerShell 5.1, pytest 9.2.

**Spec:** `assistente-laboratorio/docs/superpowers/specs/2026-11-16-quattro-container-design.md`

## Global Constraints

- Branch `dev-quattro-container` (già creato da `dev` a `cbcee33`); comandi da `assistente-laboratorio/`.
- Nessuna dipendenza nuova: `requirements*.txt` e `package*.json` invariati.
- Porte pubblicate solo su `127.0.0.1`; `backend` non pubblica porte.
- Messaggi all'utente in italiano; ogni errore del launcher è `Errore: …` (o `Errore inatteso: …`), mai un traceback.
- `avvio_chat` non importa (nemmeno indirettamente) `psycopg`, `langchain_core`, `langchain_openai`, `httpx`.
- Valori predefiniti di `BACKEND_HOST`, `POSTGRES_HOST`, `AGENTE_INDIRIZZO`: `127.0.0.1`. `BACKEND_INDIRIZZO` predefinita `backend`.
- Attese del launcher: Docker 180 s, LM Studio 60 s, container 600 s, chat 90 s; X della finestra → container fermi entro 30 s.
- Conventional Commits in italiano, **senza righe `Co-Authored-By`**; prima di ogni commit `git status`, diff e staging selettivo. Nessun push, nessun merge.
- Mai toccare `.env`, `archivio/`, il volume `dati_postgres` dell'utente; le prove automatiche usano progetti Compose `-p` di prova.
- Suite in container: `docker compose run --rm test`. Sull'host: `python -m pytest tests/test_avvio_chat.py tests/test_avvia_ps1.py tests/test_nginx.py` e, con Docker, `python -m pytest --docker tests/test_compose_servizi.py tests/test_compose_frontend.py`.

## Review Focus

1. **Errore dopo `up`.** Se `/api/salute` non diventa tutto `ok` entro 90 s, i container che il launcher ha acceso vanno spenti prima di uscire con l'errore, come oggi si spegne l'agente se il back-end non parte → test in Task 4.
2. **Container accesi da qualcun altro.** Se `agente` è acceso ma `backend` no, alla fine il launcher ferma solo `backend` → test in Task 4.
3. **Agente vecchio fuori da Docker.** Con `python -m servizio_agente` ancora acceso, `compose up` fallisce per la porta occupata: il messaggio deve suggerire di chiuderlo → test in Task 4.
4. **nginx con il back-end spento.** La pagina resta accesa dopo `esci` (decisione del 15 novembre): nginx non deve fermarsi né restare bloccato su un indirizzo vecchio quando il back-end riparte con un altro IP → `resolver` con `valid` breve, prova in Task 3.
5. **`.\avvia.ps1` con il profilo `cli`.** `docker compose run --rm assistente` deve funzionare anche se `assistente` è in un profilo → prova in Task 3.

---

### Task 1: La suite automatica in un container

Senza questo task nessun test del back-end si può eseguire: sull'host `psycopg` non si carica.

**Files:**
- Create: `Dockerfile.test`
- Create: `tests/compose_prova.py`
- Modify: `compose.yaml` (servizio `test`), `tests/postgres_prova.py`, `tests/frontend_prova.py`, `tests/test_compose_frontend.py`
- Modify: test che falliscono solo su Linux (`skipif`, vedi Step 4)

**Interfaces:**
- Produces: `tests/compose_prova.py` con `CARTELLA: Path`, `ENV_FINTO: dict[str, str]`, `LIMITE_COMPOSE: int`, `_porta_libera() -> int` (spostati da `postgres_prova.py`, che li reimporta). `test_compose_frontend.py` e `frontend_prova.py` importano da `tests.compose_prova`.
- Produces: comando `docker compose run --rm test`.

- [ ] **Step 1: `Dockerfile.test`.** `FROM python:3.14-slim`, `ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1`, `WORKDIR /app`, `COPY requirements.txt requirements-dev.txt ./`, `RUN pip install --no-cache-dir -r requirements-dev.txt`, `CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]`. Niente `ASSISTENTE_IN_DOCKER`: i test lo impostano da soli dove serve.
- [ ] **Step 2: servizio `test` in `compose.yaml`.** `build: {context: ., dockerfile: Dockerfile.test}`, `profiles: ["test"]`, `volumes: [".:/app"]`, nessun `env_file`, nessuna porta.
- [ ] **Step 3: `tests/compose_prova.py`** con le quattro definizioni elencate in Interfaces, senza `import psycopg`; aggiorna gli import nei tre file.
- [ ] **Step 4: prima esecuzione.** Run: `docker compose run --rm test`. Atteso: nessun errore di raccolta. Per ogni test fallito: se dipende da Windows (console, `SIGBREAK`, `CTRL_BREAK_EVENT`, `.cmd`, `powershell`), aggiungi `@pytest.mark.skipif(sys.platform != "win32", reason="…")` con il motivo; **qualunque altro fallimento: fermati e riportalo**, può essere un difetto vero.
- [ ] **Step 5: esito di riferimento.** Run di nuovo `docker compose run --rm test` → `0 failed`; annota passati e saltati (servono al checkpoint). Run sull'host: `python -m pytest --docker tests/test_compose_frontend.py -v` → passati (ora non importa più `psycopg`).
- [ ] **Step 6: commit.** `test: la suite gira in un container (Dockerfile.test, servizio test), compose_prova senza psycopg`

### Task 2: Gli indirizzi del back-end da variabili d'ambiente

**Files:**
- Modify: `servizio_backend/configurazione.py`, `servizio_backend/__main__.py`
- Modify: `assistente/configurazione.py` (funzione comune per l'indirizzo IP)
- Test: `tests/test_configurazione_backend.py`, `tests/test_avvio_servizio_backend.py`

**Interfaces:**
- Consumes: `leggi_porta`, `ErroreConfigurazione`, `HOST_AGENTE_PREDEFINITO` da `assistente.configurazione`.
- Produces: `leggi_indirizzo_ip(nome: str, env: Mapping[str, str], predefinito: str = "127.0.0.1") -> str` in `assistente/configurazione.py`; `leggi_host_agente(env)` diventa `return leggi_indirizzo_ip("AGENTE_HOST", env)` con lo stesso messaggio d'errore di oggi (nome della variabile nel testo).
- Produces: `ValoriBackend` (dataclass frozen: `porta: int`, `host: str`, `porta_agente: int`, `indirizzo_agente: str`, `utente: str`, `password: str`, `database: str`, `host_postgres: str`, `porta_postgres: int`) e `leggi_valori_backend(env) -> ValoriBackend` in `servizio_backend/configurazione.py`: tutti i controlli di oggi più le tre variabili nuove, **senza psycopg**.
- Produces: `ConfigurazioneBackend` con i campi di oggi più `host: str` e `host_postgres: str`; `carica_configurazione_backend(env)` = `leggi_valori_backend` + DSN. `from psycopg.conninfo import make_conninfo` si sposta **dentro** `carica_configurazione_backend`.

- [ ] **Step 1: test che falliscono** in `tests/test_configurazione_backend.py`:
  - `test_indirizzi_predefiniti`: senza le tre variabili → `config.host == "127.0.0.1"`, `config.url_agente == "http://127.0.0.1:8767"`, `"host=127.0.0.1"` nel DSN.
  - `test_indirizzi_di_docker`: `BACKEND_HOST=0.0.0.0`, `POSTGRES_HOST=database`, `AGENTE_INDIRIZZO=agente` → `config.host == "0.0.0.0"`, `config.url_agente == "http://agente:8767"`, `"host=database"` nel DSN, `config.host_postgres == "database"`.
  - `test_backend_host_non_ip`: `BACKEND_HOST=localhost` → `ErroreConfigurazione` con `"BACKEND_HOST"` nel messaggio.
  - `test_spazi_contano_come_vuoti`: `POSTGRES_HOST="  "` → predefinito `127.0.0.1`.
  - `test_valori_senza_psycopg`: in un sottoprocesso `python -c "import sys; from servizio_backend.configurazione import leggi_valori_backend; print('psycopg' in sys.modules)"` stampa `False`.
- [ ] **Step 2:** Run `docker compose run --rm test python -m pytest tests/test_configurazione_backend.py -q` → FAIL.
- [ ] **Step 3: implementa** le Interfaces. In `__main__.py`: `uvicorn.run(..., host=config.host, ...)`; i messaggi «in ascolto su» e «Il database PostgreSQL non risponde su …» usano `config.host`/`config.host_postgres` e la porta del DSN.
- [ ] **Step 4: test dell'avvio** in `tests/test_avvio_servizio_backend.py`: `test_messaggio_database_con_indirizzo_vero` → con `POSTGRES_HOST=database` e database irraggiungibile il messaggio contiene `"database:"`. Run in container → PASS, insieme a `tests/test_configurazione.py` (AGENTE_HOST invariato).
- [ ] **Step 5:** `docker compose run --rm test` → `0 failed`.
- [ ] **Step 6: commit.** `feat(backend): indirizzi di ascolto, del database e dell'agente da BACKEND_HOST, POSTGRES_HOST e AGENTE_INDIRIZZO`

### Task 3: Compose, Dockerfile e nginx per i quattro container

**Files:**
- Modify: `compose.yaml`, `Dockerfile`, `frontend/nginx/default.conf.template`, `tests/frontend_prova.py`, `.env.example`
- Create: `tests/test_compose_servizi.py` (marcato `docker`, gira sull'host), `tests/test_nginx.py` (testo del modello, gira ovunque)

**Interfaces:**
- Consumes: le variabili del Task 2.
- Produces: servizio `backend`; `docker compose up -d` accende `database`, `agente`, `backend`, `frontend`; `docker compose ps --status running --services` li elenca (lo usa il Task 4).

- [ ] **Step 1: test che falliscono** in `tests/test_compose_servizi.py`, con `docker compose --env-file <prova.env> config --format json` come in `test_compose_frontend.py` (variabili da `ENV_FINTO` più `BACKEND_PORTA=8768`):
  - `test_quattro_servizi_senza_profilo`: i servizi senza `profiles` sono esattamente `{"database", "agente", "backend", "frontend"}`; `assistente` ha `profiles == ["cli"]`, `test` ha `["test"]`.
  - `test_backend_senza_porte_e_indirizzi_di_docker`: `backend` non ha `ports`; `environment` ha `BACKEND_HOST == "0.0.0.0"`, `POSTGRES_HOST == "database"`, `POSTGRES_PORTA == "5432"`, `AGENTE_INDIRIZZO == "agente"`; `depends_on.database.condition == "service_healthy"`.
  - `test_riavvio_e_healthcheck`: `agente` e `backend` hanno `restart == "on-failure"` e un `healthcheck`; `database` e `frontend` senza `restart`.
  - `test_porte_solo_su_127`: ogni porta pubblicata da ogni servizio ha `host_ip == "127.0.0.1"`.
  - `test_frontend_indirizzo_del_backend`: `frontend.environment.BACKEND_INDIRIZZO == "backend"`; con `BACKEND_INDIRIZZO=host.docker.internal` nel file → quel valore.
- [ ] **Step 2: test che falliscono** in `tests/test_nginx.py` (legge `frontend/nginx/default.conf.template`):
  - `test_niente_host_docker_internal_scritto`: il testo non contiene `host.docker.internal`.
  - `test_backend_risolto_a_ogni_richiesta`: contiene `resolver 127.0.0.11`, `${BACKEND_INDIRIZZO}:${BACKEND_PORTA}` e un `proxy_pass` con una variabile nginx (`proxy_pass $`).
  - `test_prefisso_api_tolto`: contiene una `rewrite` che toglie `/api/` (con `proxy_pass` a variabile l'URI non si sostituisce da solo).
- [ ] **Step 3:** Run sull'host `python -m pytest --docker tests/test_compose_servizi.py tests/test_nginx.py` → FAIL.
- [ ] **Step 4: `Dockerfile`:** aggiungi `COPY servizio_backend/ servizio_backend/` dopo gli altri `COPY` (dopo `pip install`, che resta in cache).
- [ ] **Step 5: `compose.yaml`** secondo la tabella della specifica. Healthcheck di `agente` e `backend`: `["CMD", "python", "-c", "<urllib.request.urlopen('http://127.0.0.1:<porta>/salute', timeout=3)>"]` con la porta letta da `os.environ` (`AGENTE_PORTA`, `BACKEND_PORTA`), `interval: 5s`, `timeout: 5s`, `retries: 6`, `start_period: 60s` per l'agente (scopre gli strumenti MCP), `20s` per il back-end. `frontend`: `BACKEND_INDIRIZZO: ${BACKEND_INDIRIZZO:-backend}`, `depends_on: [backend]`.
- [ ] **Step 6: nginx.** Togli il blocco `upstream`; in `location /api/`: `resolver 127.0.0.11 valid=10s ipv6=off;`, `set $backend http://${BACKEND_INDIRIZZO}:${BACKEND_PORTA};`, `rewrite ^/api/(.*)$ /$1 break;`, `proxy_pass $backend;`. Il resto (SSE, header, timeout) invariato.
- [ ] **Step 7: `tests/frontend_prova.py`:** `up -d --build --no-deps frontend` e `BACKEND_INDIRIZZO=host.docker.internal` nell'`env`. `.env.example`: righe commentate per `BACKEND_HOST`, `POSTGRES_HOST`, `AGENTE_INDIRIZZO`, `BACKEND_INDIRIZZO` («non servono: le imposta Compose»).
- [ ] **Step 8:** Run sull'host `python -m pytest --docker tests/test_compose_servizi.py tests/test_compose_frontend.py tests/test_nginx.py -v` → PASS; `docker compose run --rm test` → `0 failed`.
- [ ] **Step 9: prova dal vivo** (container dell'utente; agente e back-end sull'host sono spenti):
  - `docker compose up -d --build --wait` → codice 0; `docker compose ps` mostra quattro servizi, `agente` e `backend` `healthy`.
  - `Invoke-RestMethod http://127.0.0.1:8780/api/salute` → `stato ok`, `database ok`, `agente ok`.
  - `docker compose stop backend`, poi `Invoke-WebRequest http://127.0.0.1:8780/` → 200 (nginx vivo); `/api/salute` → 502 o 503; `docker compose start backend`, attesa `healthy`, `/api/salute` di nuovo `ok` (Review Focus 4).
  - Il nome `host.docker.internal` risolto dal DNS di Docker, per le prove del browser: `docker compose exec frontend nslookup host.docker.internal 127.0.0.11` → un indirizzo. Se non lo risolve, annotalo nel checkpoint (le prove del browser non si possono comunque eseguire).
  - `.\avvia.ps1 -SenzaTty` con ingresso `esci` → la CLI parte e saluta (Review Focus 5).
- [ ] **Step 10: commit.** `feat(docker): servizio backend, quattro container con un comando, nginx che risolve il back-end a ogni richiesta`

### Task 4: Il launcher accende e spegne i container

**Files:**
- Create: `assistente/lmstudio.py`, `avvio_chat/console.py` (segnaposto, riempito nel Task 5)
- Modify: `assistente/modello.py`, `avvio_chat/passi.py`, `avvio_chat/__main__.py` (che oggi importa `ErroreServer` da `assistente.modello` e `CARTELLA_PROGETTO` da `assistente.avvio_server`: entrambi portano `langchain`/`httpx` e vanno sostituiti con `assistente.lmstudio` e `avvio_chat.passi`)
- Test: `tests/test_avvio_chat.py` (riscritto dove cambia; gira sull'host), `tests/test_modello.py` (invariato, deve passare)

**Interfaces:**
- Produces: `assistente/lmstudio.py` (solo libreria standard) con `ErroreServer`, `_leggi_json_http`, `_controlla_indirizzo`, `verifica_server(base_url, modello, leggi_json=..., timeout=5.0)` spostati da `modello.py`, che li reimporta (`from assistente.lmstudio import ErroreServer, verifica_server, _leggi_json_http, _controlla_indirizzo`): gli import di oggi restano validi.
- Produces, in `avvio_chat/passi.py`:
  - `CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent` (non più da `assistente.avvio_server`);
  - `Impostazioni(base_url: str, modello: str, porta_agente: int, porta_frontend: int)` con `url_chat` e `url_salute` (`url_chat + "/api/salute"`);
  - `carica_impostazioni(env) -> Impostazioni`: `carica_configurazione`, `leggi_porta_agente`, `leggi_valori_backend` (Task 2), `FRONTEND_PORTA` predefinita 8780;
  - invariati: `Esito`, `esegui_comando` (con `cwd=CARTELLA_PROGETTO`), `assicura_docker`, `lmstudio_risponde`, `trova_lms`, `assicura_lmstudio` (predefinito `verifica=assistente.lmstudio.verifica_server`), con i passi rinumerati `[1/4]`, `[2/4]`;
  - `SERVIZI_DELLA_CHAT = ("agente", "backend")`;
  - `servizi_accesi(esegui: Esegui) -> set[str]`: `docker compose ps --status running --services`, una riga per servizio;
  - `assicura_container(esegui, scrivi, *, ricostruisci: bool = False) -> None`: `docker compose up -d --wait` (più `--build`), limite 600 s, `[3/4] Container: accesi`;
  - `leggi_salute(url: str, limite: float) -> dict` (GET, JSON);
  - `attendi_chat(imp, scrivi, *, salute=leggi_salute, attesa=90.0, pausa=time.sleep, orologio=time.monotonic) -> None`: riprova finché `stato`, `database`, `agente` sono `"ok"`; scrive `[4/4] Chat: risponde (database ok, agente ok)`;
  - `ferma_servizi(servizi: list[str], esegui: Esegui) -> None`: `docker compose stop <servizi>`;
  - `avvia_chat(imp, ingresso, scrivi, *, esegui=esegui_comando, apri=webbrowser.open, senza_browser=False, ricostruisci=False, risponde=lmstudio_risponde, verifica=verifica_server, lms=trova_lms, pausa=time.sleep, orologio=time.monotonic, salute=leggi_salute, alla_chiusura=installa_chiusura_console) -> int`.
- Consumes (Task 5): `installa_chiusura_console(comando: list[str]) -> None` da `avvio_chat/console.py`. In questo task basta un segnaposto che non fa nulla; il Task 5 lo riempie.

- [ ] **Step 1: test che falliscono** (il file non importa più `assistente.avvio_server` né `assistente.modello`; tolgono quelli di `servizio`, `processo_in_attesa`, porte MCP e log `avvio_*.log`; restano quelli di Docker, LM Studio, `esegui_comando`, `.cmd`, ambiente e password). `EseguiFinto` risponde anche a `("docker", "compose", "ps")`, `("docker", "compose", "up")`, `("docker", "compose", "stop")`; `salute` è una funzione finta.
  - `test_nessuna_libreria_bloccabile_dopo_l_import`: sottoprocesso `python -c "import sys, avvio_chat.__main__; print(sorted(m for m in ('psycopg', 'langchain_core', 'langchain_openai', 'httpx') if m in sys.modules))"` → stampa `[]`.
  - `test_avvio_completo_ed_esci`: `ps` → vuoto; esito 0; righe `[1/4]`…`[4/4]`, `«esci»`; browser aperto una volta; l'ultimo comando è `docker compose stop backend agente`; `alla_chiusura` ricevuto con lo stesso comando.
  - `test_tutto_gia_acceso_apre_solo_il_browser`: `ps` → `agente\nbackend\n` → nessuno `stop`, ingresso mai letto (`IngressoVietato`), testo «già accesi».
  - `test_agente_gia_acceso_si_ferma_solo_il_backend` (Review Focus 2): `ps` → `agente\ndatabase\n` → `stop backend` soltanto.
  - `test_ricostruisci`: con `ricostruisci=True` il comando `up` contiene `--build`; senza no; limite 600.
  - `test_chat_che_non_risponde_spegne_cio_che_ho_acceso` (Review Focus 1): `salute` → sempre `{"stato": "ok", "database": "ok", "agente": "non raggiungibile"}`; `ErroreAvvio` con `"agente"` e `"docker compose logs --tail 30 agente"`; eseguito `stop backend agente`; browser non aperto.
  - `test_chat_senza_backend_indica_i_log_del_backend`: `salute` solleva `OSError` fino alla scadenza → messaggio con `"docker compose logs --tail 30 backend"`.
  - `test_porta_dell_agente_occupata` (Review Focus 3): `up` → `Esito(1, "Bind for 127.0.0.1:8767 failed: port is already allocated")` → messaggio con `"python -m servizio_agente"`; lo stesso con `"ports are not available"`.
  - `test_fine_input_e_ctrl_c_fermano_come_esci`: ingresso vuoto e `IngressoInterrotto` → `stop` eseguito, codice 0.
  - `test_senza_browser`: nessuna apertura, l'indirizzo della chat è nel testo.
  - `test_main_errore_inatteso_senza_traceback`: `avvia_chat` finto che solleva `RuntimeError("guasto")` → codice 1, stderr contiene `"Errore inatteso: guasto"` e non `"Traceback"`.
  - `test_main_passa_ricostruisci`: `--ricostruisci` arriva come `ricostruisci=True`.
- [ ] **Step 2:** Run sull'host `python -m pytest tests/test_avvio_chat.py -q` → FAIL.
- [ ] **Step 3: sposta** la verifica in `assistente/lmstudio.py`; Run in container `docker compose run --rm test python -m pytest tests/test_modello.py -q` → PASS.
- [ ] **Step 4: implementa** `passi.py` e `__main__.py` secondo le Interfaces e la sezione «Il launcher» della specifica. Ordine in `avvia_chat`: Docker, LM Studio, `prima = servizi_accesi(...)`, `accesi_da_me = [s for s in ("backend", "agente") if s not in prima]`, `assicura_container`; da qui in poi un `try/finally` che, se `accesi_da_me` non è vuota, chiama `ferma_servizi(accesi_da_me, esegui)` (anche dopo un errore di `attendi_chat`); dentro il `try`: `alla_chiusura(["docker", "compose", "stop", *accesi_da_me])` se c'è qualcosa da fermare, `attendi_chat`, browser, poi uscita subito (niente acceso da me) oppure attesa di `esci`. Messaggi: quelli della sezione «Che cosa si vede». `__main__`: opzione `--ricostruisci`; `except Exception` finale → `Errore inatteso: {errore}` su stderr, codice 1; `CARTELLA_PROGETTO` da `passi`.
- [ ] **Step 5:** Run sull'host `python -m pytest tests/test_avvio_chat.py -q` → PASS; `docker compose run --rm test` → `0 failed`.
- [ ] **Step 6: commit.** `feat(avvio-chat): accende i quattro container, aspetta la chat attraverso nginx e ferma solo ciò che ha acceso, senza librerie bloccabili`

### Task 5: La chiusura della finestra ferma i container

**Files:**
- Modify: `avvio_chat/console.py` (riempie il segnaposto del Task 4)
- Test: `tests/test_avvio_chat.py` (sostituisce `test_chiudere_la_finestra_spegne_i_servizi`)

**Interfaces:**
- Produces: `installa_chiusura_console(comando: list[str]) -> None`. Su Windows registra con `ctypes.windll.kernel32.SetConsoleCtrlHandler` un gestore che, per `CTRL_CLOSE_EVENT` (2), `CTRL_LOGOFF_EVENT` (5) e `CTRL_SHUTDOWN_EVENT` (6), avvia `comando` con `subprocess.Popen(..., cwd=CARTELLA_PROGETTO, stdin/stdout/stderr=DEVNULL, creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)` e restituisce `True`; agli altri eventi restituisce `False` (così `Ctrl+C` resta un `KeyboardInterrupt`). Il riferimento al gestore resta in una variabile di modulo (altrimenti il garbage collector lo toglie). Fuori da Windows non fa nulla.

- [ ] **Step 1: test che fallisce** `test_chiudere_la_finestra_lancia_lo_spegnimento` (`skipif` non Windows), sullo schema del test di oggi: in una `conhost.exe` nascosta con titolo univoco gira `console.installa_chiusura_console([sys.executable, "-c", "<dorme 2 s, poi scrive 'fermato' in un file di tmp_path>"])` seguito da `time.sleep(120)`; si manda `WM_CLOSE` alla finestra; atteso: la console finisce e **il file compare entro 15 s** (il processo staccato è sopravvissuto alla finestra).
- [ ] **Step 2: test** `test_ctrl_c_non_passa_dal_gestore`: chiamando il gestore registrato con l'evento 0 restituisce `False` e non avvia niente (con `subprocess.Popen` sostituito da un finto).
- [ ] **Step 3:** Run `python -m pytest tests/test_avvio_chat.py -k "finestra or gestore" -v` → FAIL; implementa; Run → PASS; tutto il file → PASS.
- [ ] **Step 4: commit.** `feat(avvio-chat): chiudendo la finestra un processo staccato ferma i container accesi dal launcher`

### Task 6: L'avviso delle note in `avvia.ps1`

**Files:**
- Modify: `avvia.ps1`
- Create: `tests/test_avvia_ps1.py` (`skipif` non Windows; gira sull'host)

**Interfaces:**
- Consumes: `docker compose ps --status running --services` (Task 3).

- [ ] **Step 1: test che falliscono.** In `tmp_path` un `docker.cmd` finto che appende i suoi argomenti a un file e, se il primo argomento dopo `compose` è `ps`, stampa il contenuto di una variabile d'ambiente (`SERVIZI_FINTI`). Si lancia `powershell -NoProfile -ExecutionPolicy Bypass -File avvia.ps1` con `PATH` che inizia da `tmp_path`:
  - `test_agente_acceso_avvisa_e_rispetta_il_no`: `SERVIZI_FINTI=agente`, ingresso `N` → l'uscita contiene `note` e `archivio`; nel file degli argomenti non c'è `run`; codice 0.
  - `test_agente_acceso_e_si_apre_la_cli`: ingresso `S` → `run --rm` presente.
  - `test_agente_spento_nessuna_domanda`: `SERVIZI_FINTI` vuota → nessun avviso, `run --rm` presente.
  - `test_senza_tty_non_chiede`: `-SenzaTty` con `SERVIZI_FINTI=agente` → nessuna domanda, `run --rm -T` presente.
- [ ] **Step 2:** Run `python -m pytest tests/test_avvia_ps1.py -v` → FAIL.
- [ ] **Step 3: implementa** in `avvia.ps1`, prima di `docker compose run`: se non `-SenzaTty` e l'elenco dei servizi accesi contiene `agente`, scrivi l'avviso (le note in `archivio/note.sqlite3` sono usate anche dall'agente della chat: scriverle da due parti insieme può rovinarle) e chiedi «Aprire comunque la CLI? (S/N)»; tutto ciò che non è `S`/`s` esce con 0. Per leggere la risposta usa `Read-Host`; se nel test non legge l'ingresso rediretto, usa `[Console]::In.ReadLine()`.
- [ ] **Step 4:** Run → PASS. **Commit.** `feat(docker): avvia.ps1 avvisa che le note sono condivise quando l'agente della chat è acceso`

### Task 7: Prove reali

Nessun codice nuovo: si eseguono le prove della specifica e si annotano gli esiti (con orari e uscite) per il checkpoint. Se una prova fallisce, si torna al task che la riguarda.

- [ ] **Step 1** (Docker e LM Studio accesi, `docker compose stop agente backend`): `.\avvia-chat.cmd --senza-browser` in una console; atteso `[1/4]`…`[4/4]`, `/api/salute` tutto `ok`; poi `esci` → `docker compose ps` mostra `agente` e `backend` fermi, `database` e `frontend` accesi.
- [ ] **Step 2:** di nuovo con tutto acceso (`docker compose up -d --wait` prima) → «già accesi», uscita 0, nessun container fermato.
- [ ] **Step 3:** un turno vero con LM Studio: `Invoke-RestMethod` su `/api/chat` e poi sul turno in streaming come nel capitolo 14 (o dal browser); la risposta arriva ed è salvata; dopo `docker compose restart backend` la chat c'è ancora.
- [ ] **Step 4:** `.\avvia.ps1` con l'agente acceso → avviso; `N` esce.
- [ ] **Step 5, con l'utente:** doppio clic su `avvia-chat.cmd` (con browser), **clic vero sulla X** dopo «La chat è accesa»; entro 30 s `docker compose ps` mostra `agente` e `backend` fermi.
- [ ] **Step 6, con l'utente:** al prossimo avvio del PC, doppio clic appena compare il desktop; atteso: la chat si apre al primo colpo. Se l'utente non può farlo subito, resta in «Da fare» nel checkpoint.

### Task 8: Documenti e checkpoint

**Files:** quelli elencati in «Documenti da aggiornare» della specifica, più `docs/superpowers/checkpoint/2026-11-16-quattro-container.md`.

- [ ] **Step 1:** `README.md`, `AVVIO-RAPIDO.md` (doppio clic, `--ricostruisci` dopo un aggiornamento, `docker compose stop`, test con `docker compose run --rm test`), `CLAUDE.md` (struttura: `avvio_chat/` non è più «non lo step 9»; comandi di test nuovi; variabili nuove; log `avvio_*.log` tolti), `.env.example` già fatto nel Task 3.
- [ ] **Step 2:** capitoli 00, 02, 08 (7.9–7.12), 09, 14, 15 e le presentazioni `lezione-6.html`, `atlante.html`, `index.html`: solo ciò che è cambiato; i riferimenti `file:riga` controllati con `grep -n`. Le pagine HTML si aprono senza errori nella console del browser.
- [ ] **Step 3:** checkpoint con **Fatto**, **Da fare**, **Stato attuale**: esiti delle due esecuzioni (container e host) con passati e saltati, prove reali del Task 7 con esito, prove non eseguibili per Smart App Control (`test_reale_backend.py`, `test_reale_docker_backend.py`, `test_reale_browser*.py`), indice `docs/superpowers/README.md` aggiornato.
- [ ] **Step 4: commit.** `docs: quattro container con un comando (step 9) in README, guida, CLAUDE.md, studio e checkpoint`
