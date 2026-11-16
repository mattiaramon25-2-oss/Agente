# Quattro container con un solo comando (lezione 6, step 9) — specifica

Data: 16 novembre 2026. Branch: `dev-quattro-container`, da `dev` (`cbcee33`).

## Intento

L'utente vuole che, **appena acceso il PC**, il doppio clic su `avvia-chat.cmd` (l'eseguibile che già esiste) accenda la chat al primo colpo, senza blocchi.

Oggi l'avvio si blocca. La causa non è nel codice: dal 14 novembre circa **Smart App Control** di Windows 11 è attivo (`VerifiedAndReputablePolicyState = 1`) e blocca due DLL che il pacchetto `psycopg-binary` porta con sé (`psycopg_binary.libs\libssl-3-x64-….dll` e `libcrypto-3-x64-….dll`). Il registro eventi `Microsoft-Windows-CodeIntegrity/Operational` lo mostra il 16 novembre alle 9:06 (i tentativi dell'utente) e alle 9:17 (la prova di Claude). Conseguenze:

- `python -m avvio_chat` si ferma all'import di `servizio_backend.configurazione` con `ImportError: … An Application Control policy has blocked this file`; nella finestra del `.cmd` resta un traceback;
- `python -m servizio_backend` sull'host non può partire;
- `python -m pytest` sull'host si interrompe: 12 file di test non si caricano.

Spegnere Smart App Control è possibile solo all'utente e non si può più riaccendere senza reinstallare Windows. L'utente ha scelto l'altra strada: **tutto in Docker**, cioè lo step 9 della lezione 6. In un container Linux le DLL di Windows non servono e Smart App Control non entra in gioco.

## Obiettivi

- Quattro servizi Compose, `database`, `agente`, `backend`, `frontend`, accesi con **un solo comando**: `docker compose up -d` (evidenza della slide 19: «quattro container avviati con un comando»).
- **`avvia-chat.cmd` resta l'eseguibile**, con lo stesso comportamento visto dall'utente: controlla Docker e LM Studio (e li accende se servono), accende i quattro container, aspetta che la chat risponda davvero, apre il browser e resta aperto; chiudendo la finestra (o con `esci`) si spengono agente e back-end.
- Il launcher **non dipende da librerie con DLL native sull'host**: niente più blocchi da Smart App Control.
- Funziona al primo doppio clic **subito dopo l'accensione del PC**, anche se Docker Desktop e LM Studio stanno ancora partendo.
- Ogni errore è un messaggio in italiano che dice che cosa fare, mai un traceback.

## Non obiettivi

- **Nessun avvio automatico** all'accesso a Windows: l'utente fa doppio clic quando gli serve (decisione del 16 novembre).
- Nessuna modifica al grafo, agli strumenti, al front-end Svelte, al database (schema e dati).
- Il server MCP resta dentro il container dell'agente, come oggi.
- LM Studio resta sull'host (vincolo del `CLAUDE.md`).
- Il launcher non cambia impostazioni di Windows, di Docker Desktop o di LM Studio.
- Gli step 2–5 della lezione 6 non fanno parte di questo lavoro.

## Anti-obiettivi

- Un avvio che dice «pronto» quando la chat non risponde.
- Container dell'agente e del back-end che restano accesi di nascosto dopo la chiusura della finestra.
- Spegnere ciò che il launcher non ha acceso.
- Perdere le chat, le note o la password del database.
- Pubblicare porte su interfacce diverse da `127.0.0.1`.

## Decisioni dell'utente

- **15 novembre 2026**, restano valide: il file accende da solo Docker Desktop e LM Studio; alla chiusura della finestra si spengono agente e back-end, database e pagina restano accesi.
- **16 novembre 2026:**
  - tutto in Docker, invece di spegnere Smart App Control;
  - alla chiusura della finestra la chat si spegne (agente e back-end), come oggi;
  - nessun avvio automatico all'accesso: doppio clic a mano;
  - con l'agente in Docker acceso, `.\avvia.ps1` avvisa che le note sono condivise prima di aprire la CLI.

## Che cosa si costruisce

### `compose.yaml`

| Servizio | Che cosa cambia |
|---|---|
| `assistente` (CLI) | `profiles: ["cli"]`: non parte con `docker compose up -d`. `.\avvia.ps1` (`docker compose run --rm assistente`) deve continuare a funzionare. |
| `database` | invariato. |
| `agente` | `restart: on-failure`; `healthcheck` su `GET /salute` (l'immagine non ha `curl`: un comando `python -c` con `urllib`). Porta ancora su `127.0.0.1:${AGENTE_PORTA}`. |
| `backend` (**nuovo**) | stessa immagine (`build: .`), comando `python -m servizio_backend`, `env_file: .env`; nell'`environment`: `BACKEND_HOST: 0.0.0.0`, `POSTGRES_HOST: database`, `POSTGRES_PORTA: "5432"` (la porta dentro la rete di Compose, non quella dell'host), `AGENTE_INDIRIZZO: agente`; volume `./logs:/app/logs`; `depends_on` con `database` sano e `agente` avviato; `restart: on-failure`; `healthcheck` su `/salute`. **Nessuna porta pubblicata**: ci arriva solo nginx. |
| `frontend` | nuova variabile `BACKEND_INDIRIZZO`, predefinita `backend`; `depends_on: backend`. `extra_hosts` resta, perché le prove del browser lo puntano a un back-end finto sull'host con `BACKEND_INDIRIZZO=host.docker.internal`. |

`restart: on-failure` (scelta di Claude): se l'agente o il back-end cadono durante la sessione, Docker li riavvia; dopo uno `stop` restano spenti, e al riavvio di Docker non ripartono da soli.

Le variabili obbligatorie restano senza `:?` dove oggi non ce l'hanno: Compose controlla tutto il file a ogni comando e `.\avvia.ps1` non deve fermarsi per variabili che servono solo alla chat.

### `Dockerfile`

Copia anche `servizio_backend/` (con `schema.sql`). L'ordine dei `COPY` resta tale che il livello di `pip install` si riusa dalla cache: la rete dell'utente è lenta (connessioni da 5–8 secondi, misurate il 12 novembre).

### Back-end: indirizzi da variabili d'ambiente

Oggi `servizio_backend` ha `127.0.0.1` scritto nel codice in tre punti. Diventano tre variabili facoltative, con i valori predefiniti di oggi, così fuori da Docker non cambia nulla:

| Variabile | Predefinita | Uso | Controllo |
|---|---|---|---|
| `BACKEND_HOST` | `127.0.0.1` | indirizzo di ascolto di uvicorn | un indirizzo IP, come `AGENTE_HOST` |
| `POSTGRES_HOST` | `127.0.0.1` | host del database nel DSN | non vuota dopo `strip` |
| `AGENTE_INDIRIZZO` | `127.0.0.1` | host di `url_agente` (`http://<indirizzo>:<AGENTE_PORTA>`) | non vuota dopo `strip` |

I messaggi d'avvio e d'errore di `servizio_backend/__main__.py` dicono l'indirizzo vero (per esempio «Il database PostgreSQL non risponde su database:5432»). Il controllo `porta_libera` resta.

### nginx

`frontend/nginx/default.conf.template` inoltra `/api/` a `${BACKEND_INDIRIZZO}:${BACKEND_PORTA}` invece che a `host.docker.internal`. nginx **non deve fermarsi** se all'avvio il nome `backend` non si risolve (per esempio quando il back-end è spento e la pagina resta accesa, come prevede la decisione del 15 novembre): il nome si risolve al momento della richiesta, con il DNS di Docker (`resolver 127.0.0.11`). Finché il back-end non risponde, `/api/` dà un errore 502 o 503 e la chat mostra la sua striscia d'errore, come già fa.

### Il fuso dell'utente

Nel container dell'agente vale `FUSO_HOST_WINDOWS` se Compose lo riceve, altrimenti `FUSO_ORARIO` del `.env`. **Il launcher non passa `FUSO_HOST_WINDOWS`** (scelta di Claude): se lo passasse, un `docker compose up -d` lanciato a mano vedrebbe un `environment` diverso e ricreerebbe l'agente a ogni alternanza. Vale quindi `FUSO_ORARIO` del `.env` (`Europe/Rome` nell'esempio). `avvia-agente.ps1` continua a passarlo come oggi; usarlo ricrea l'agente, ed è documentato.

### Il launcher: `avvia-chat.cmd` e `python -m avvio_chat`

`avvia-chat.cmd` resta com'è (controllo di `.venv`, pausa dopo un errore). `avvio_chat` si riscrive così:

1. **Docker.** Come oggi: `docker info`, se serve `docker desktop start`, attesa fino a 180 secondi. Subito dopo l'accensione del PC Docker Desktop può essere già in avvio: il launcher aspetta che risponda, senza errori intermedi.
2. **LM Studio.** Come oggi: `GET /v1/models`, se serve `lms server start`, attesa fino a 60 secondi. Poi controllo che il modello del `.env` sia nell'elenco.
3. **Che cosa è già acceso.** Il launcher guarda lo stato dei container `agente` e `backend` (per esempio con `docker compose ps`) **prima** di accenderli, per sapere se li ha accesi lui.
4. **Container.** `docker compose up -d --wait`, attesa fino a 10 minuti (la prima volta le immagini vanno costruite). Con l'opzione `--ricostruisci` aggiunge `--build`, da usare dopo un aggiornamento del codice.
5. **La chat risponde.** `GET http://127.0.0.1:<FRONTEND_PORTA>/api/salute`, cioè attraverso nginx, deve dire `stato`, `database` e `agente` tutti `ok`, entro 90 secondi (l'agente deve scoprire gli strumenti MCP).
6. **Browser.** Apre `http://127.0.0.1:<FRONTEND_PORTA>` (salvo `--senza-browser`).
7. **Attesa e spegnimento**, come oggi:
   - se agente e back-end erano **già accesi tutti e due** prima del passo 4, il launcher non li ha accesi e quindi esce subito con codice 0, senza spegnere niente;
   - altrimenti resta aperto e spegne **solo quelli che ha acceso lui** con `docker compose stop <servizi>` quando l'utente scrive `esci`, preme `Ctrl+C`, l'ingresso finisce, oppure **chiude la finestra con la X**. Database e pagina restano accesi.

**La chiusura con la X.** Oggi bastava che Windows chiudesse i processi attaccati alla console. Con i container non basta: i container vivono in Docker, non nella finestra. Il launcher intercetta l'evento di chiusura della console (Windows concede pochi secondi) e lancia lo spegnimento in un processo staccato dalla finestra, che finisce anche dopo che la finestra è sparita. Requisito: dopo un clic sulla X, entro 30 secondi i container accesi dal launcher sono fermi.

Vincolo: `avvio_chat` usa solo la libreria standard di Python e `python-dotenv`. Non importa `psycopg`, `langchain_*`, `httpx` né i moduli che li importano (per esempio `servizio_backend.configurazione`, `assistente.modello` e `assistente.avvio_server`): le richieste HTTP e il controllo del modello si riscrivono con `urllib`. Un test lo controlla, perché è proprio questo che oggi lo fa bloccare. Il `.env` si legge come oggi con `dotenv_values`, senza copiarlo nell'ambiente.

Spariscono i processi Python dell'agente e del back-end sull'host e i log `logs/avvio_agente.log` e `logs/avvio_backend.log`; i log dei servizi restano in `logs/` grazie ai volumi.

### Che cosa si vede

```text
Assistente del laboratorio · avvio della chat
[1/4] Docker: acceso
[2/4] LM Studio: risponde, modello google/gemma-4-e2b presente
      Accendo i container (la prima volta ci vuole qualche minuto)...
[3/4] Container: accesi
[4/4] Chat: risponde (database ok, agente ok)
Apro http://127.0.0.1:8780
La chat è accesa. Per spegnerla scrivi «esci» e premi Invio, oppure chiudi questa finestra.
```

Con agente e back-end già accesi, l'ultima riga diventa: «Agente e back-end erano già accesi: non li ho accesi io, quindi restano accesi.» e la finestra si chiude.

### Errori

Ogni errore è `Errore: …`, codice 1, e la finestra aspetta un tasto.

| Caso | Messaggio, in sostanza |
|---|---|
| manca `.venv` | lo dice il `.cmd`, come oggi |
| manca il `.env` o una variabile | quello della configurazione |
| Docker non installato, o non parte in 180 s | come oggi |
| LM Studio non risponde, o modello mancante | come oggi |
| `docker compose up` fallisce | le ultime righe di Compose; se la porta dell'agente è occupata, l'ipotesi «c'è ancora un agente acceso fuori da Docker (`python -m servizio_agente`): chiudilo e riprova» |
| `/api/salute` non dice tutto `ok` entro 90 s | che cosa manca (database o agente) e il comando per leggerne il log: `docker compose logs --tail 30 agente` (o `backend`) |
| qualunque altro errore imprevisto | una riga `Errore inatteso: …`, senza traceback |

### L'avviso delle note in `avvia.ps1`

Con l'agente sempre in Docker, la CLI (`.\avvia.ps1`) e l'agente avrebbero due server MCP che scrivono insieme `archivio/note.sqlite3`, su una cartella di Windows condivisa con Docker dove i blocchi di SQLite non sono affidabili. Se il container `agente` è acceso, `.\avvia.ps1` lo dice e chiede conferma (`S`/`N`) prima di aprire la CLI. `-SenzaTty` (le prove automatiche) non chiede: procede, come oggi.

## Test e verifica

**Vincolo.** Finché Smart App Control è attivo, `python -m pytest` sull'host non può caricare i test che importano `psycopg`, e la raccolta si interrompe. Per questo:

- **la suite automatica gira in un container**, con un comando documentato (per esempio un servizio Compose `test` nel profilo `test`, oppure `docker compose run --rm` con `requirements-dev.txt`);
- i test di `avvio_chat` girano sull'host, perché il launcher non importa `psycopg` e alcuni valgono solo su Windows (console, chiusura con la X);
- `npm test` del front-end gira sull'host come oggi;
- **«verde» vuol dire** (scelta di Claude): nessun fallimento in nessuna delle due esecuzioni, container e host, riportate separatamente nel checkpoint con passati e saltati. I saltati ammessi sono le prove reali e i test che valgono solo su un sistema.

I test che usano `docker compose config` (come `tests/test_compose_frontend.py`) restano sull'host, perché serve la CLI di Docker: si toglie dalla loro catena di import il modulo che importa `psycopg` (`tests/postgres_prova.py`), spostando costanti e funzioni comuni in un modulo che non lo importa. Nessuna dipendenza nuova (niente PyYAML).

**Test nuovi o cambiati**, senza LM Studio:

- configurazione del back-end: le tre variabili nuove, predefinite e sbagliate;
- `compose.yaml` letto con `docker compose config` (sull'host): quattro servizi senza profilo, profilo `cli` per `assistente`, `restart` di agente e back-end, porte solo su `127.0.0.1`, nessuna porta per `backend`;
- nginx: il modello usa `BACKEND_INDIRIZZO` e il `resolver`;
- `avvio_chat`, con comandi finti: i passi, il riconoscimento di ciò che era già acceso, lo spegnimento solo di ciò che ha acceso, `--ricostruisci`, `--senza-browser`, la salute parziale, l'errore imprevisto senza traceback, l'assenza di `psycopg`, `langchain_core` e `httpx` dopo l'import, e la chiusura della console che lancia lo spegnimento staccato (su una console vera, come il test di oggi sulla X);
- `avvia.ps1`: l'avviso compare solo con l'agente acceso.

**Prove reali**, riportate nel checkpoint:

1. Con agente e back-end spenti: doppio clic su `avvia-chat.cmd` → quattro container accesi, `/api/salute` tutto `ok`, browser aperto.
2. `esci` → `agente` e `backend` fermi, `database` e `frontend` accesi.
3. Doppio clic, poi **clic vero sulla X** → entro 30 secondi `agente` e `backend` fermi.
4. Doppio clic con tutto già acceso → apre il browser ed esce, nessun container fermato.
5. Un turno vero con LM Studio dalla chat nel browser (risposta in streaming e salvata); le chat restano dopo un nuovo avvio.
6. **Subito dopo l'accensione del PC**, fatto dall'utente: doppio clic appena compare il desktop, mentre Docker Desktop e LM Studio stanno ancora partendo → la chat si apre al primo colpo.
7. `.\avvia.ps1` funziona ancora, con l'avviso quando l'agente è acceso.

Le prove reali esistenti che lanciano processi Python con `psycopg` sull'host (`tests/test_reale_backend.py`, `test_reale_docker_backend.py`, `test_reale_browser*.py`) non si possono eseguire finché Smart App Control è attivo: si dichiara nel checkpoint, senza toglierle. `tests/frontend_prova.py` riceve `--no-deps` in `up -d --build frontend`, perché con il nuovo `depends_on` accenderebbe database, agente e back-end veri nel progetto di prova; la modifica resta non verificata dal vivo per lo stesso motivo, e lo si dichiara.

## Scelte di costruzione (decise da Claude, correggibili)

- Il servizio si chiama `backend`, come la cartella `servizio_backend` senza prefisso.
- Il back-end non pubblica porte sull'host; l'agente sì, su `127.0.0.1`, come oggi.
- `restart: on-failure` per agente e back-end; database e pagina senza politica di riavvio, come oggi.
- Il launcher non passa il fuso di Windows: vale `FUSO_ORARIO` del `.env`.
- Nomi delle variabili: `BACKEND_HOST` (come `AGENTE_HOST`), `POSTGRES_HOST`, `AGENTE_INDIRIZZO`, `BACKEND_INDIRIZZO`.
- Opzione `--ricostruisci` per `docker compose up -d --build`.
- «Verde» = nessun fallimento nelle due esecuzioni (container e host), riportate separatamente.

## Documenti da aggiornare

`README.md`, `AVVIO-RAPIDO.md`, `CLAUDE.md` (struttura, comandi, variabili, la riga «Non è lo step 9»), `.env.example` (variabili nuove commentate), capitoli di studio 00 (step 9 fatto), 02 (processi e diagramma), 08 (sezioni 7.9–7.12), 09 (test in container), 14 e 15 (dove dicono che il back-end gira sull'host), presentazioni `lezione-6.html`, `atlante.html`, `index.html`, indice `docs/superpowers/README.md`, checkpoint `docs/superpowers/checkpoint/2026-11-16-quattro-container.md`.

## Lasciato a chi costruisce

Forma esatta degli healthcheck e dei loro intervalli, nomi delle funzioni interne, testo esatto dei messaggi non elencati, meccanismo esatto per intercettare la chiusura della console e staccare lo spegnimento, forma del comando che fa girare la suite in un container.
