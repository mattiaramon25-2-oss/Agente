# Avvio rapido

Una pagina per far partire l'assistente del laboratorio. I dettagli e tutti i casi particolari restano nel [README](README.md).

Tutti i comandi si scrivono in **PowerShell**, dalla cartella `assistente-laboratorio`.

## Il modo più semplice: un doppio clic

Fai doppio clic su **`avvia-chat.cmd`**, nella cartella `assistente-laboratorio`. Si apre una finestra che accende ciò che manca e poi apre la chat nel browser:

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

- **Accende da solo ciò che è spento:** Docker Desktop, il server di LM Studio e i quattro container (database, agente, back-end e pagina). Aspetta che la chat risponda davvero prima di aprire il browser.
- **Per spegnere:** scrivi `esci` nella finestra e premi Invio, oppure chiudi la finestra. Si spengono l'agente e il back-end, se li ha accesi lui; il database e la pagina restano accesi in Docker. Il browser, Docker Desktop e LM Studio restano aperti.
- **Se agente e back-end sono già accesi**, il doppio clic apre solo il browser e la finestra si chiude.
- **Dopo un aggiornamento del codice** ricostruisci una volta le immagini dei container: `docker compose up -d --build`.
- **Per fermare anche database e pagina:** `docker compose stop`.
- **Prima serve** aver fatto una volta i passi di «La prima volta», più sotto.

Il resto di questa pagina spiega gli stessi passi fatti a mano, e gli altri due modi di usare l'assistente.

## Scegli come usarlo

| Modo | Che cosa ottieni | Che cosa deve essere acceso | Comandi |
|---|---|---|---|
| **A · Chat da terminale** | la chat nella finestra di PowerShell | LM Studio | 1 |
| **B · Chat nel browser** | la chat in una pagina web, con le conversazioni salvate | LM Studio e Docker Desktop | un doppio clic, oppure 1 a mano |
| **C · Terminale in Docker** | come A, ma dentro un container | LM Studio e Docker Desktop | 2 |

Se vuoi solo provarlo, parti da **A**.

**Uno alla volta.** A, B e C usano lo stesso archivio delle note (`archivio/note.sqlite3`): non usarli insieme. Con l'agente di B acceso, `.\avvia.ps1` (modo C) lo dice e chiede `S`/`N` prima di partire.

## La prima volta (si fa una volta sola)

Servono Python 3.14 e LM Studio con un modello scaricato. Docker Desktop serve solo per B e C.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Poi apri il file `.env` e controlla due righe:

1. **`LMSTUDIO_MODEL`**: deve essere uno degli identificativi che LM Studio restituisce. Con LM Studio aperto e il server attivo, li vedi così:

   ```powershell
   (Invoke-RestMethod http://localhost:1234/v1/models).data.id
   ```

2. **`POSTGRES_PASSWORD`** (solo per B): scegli una password e scrivila. Sceglila **prima** di avviare il database la prima volta e poi **non cambiarla**: PostgreSQL la legge solo quando crea il database.

## Prima di ogni avvio

1. Apri LM Studio e attiva il server (porta 1234).
2. Per B e C, apri Docker Desktop.
3. Apri PowerShell nella cartella `assistente-laboratorio` e attiva l'ambiente:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

---

## A · Chat da terminale

```powershell
python -m assistente
```

Devi vedere:

```text
Assistente del laboratorio
Fuso orario: Europe/Berlin (computer locale)
Strumenti: converti_unita (mcp), ora_corrente (mcp), calcola (mcp), calcola_scadenza (mcp), search_catalog (mcp), get_item (mcp), add_note (mcp), list_notes (mcp), delete_note (mcp), get_weather (mcp)
Scrivi «esci» o premi Ctrl+C per uscire.
Tu:
```

Prova con `che ore sono a Tokyo?`. Prima della risposta compare la riga dello strumento usato, per esempio `[ora_corrente · mcp: Asia/Tokyo]`.

**Per uscire:** scrivi `esci` oppure premi `Ctrl+C`. Il server degli strumenti si spegne da solo.

`Europe/Berlin` è normale anche in Italia: Windows chiama il fuso dell'Europa centrale `W. Europe Standard Time`, che la tabella standard traduce in `Europe/Berlin`. È la stessa ora di Roma.

---

## B · Chat nel browser

Il doppio clic su `avvia-chat.cmd` fa da solo tutti i passi di questa sezione. Qui c'è la versione a mano.

I pezzi sono quattro container, più LM Studio sul computer. Ognuno parla solo con il vicino:

```text
Browser ──► nginx :8780 ──► back-end ──► agente :8767 ──► LM Studio :1234
            (frontend)     (backend)        │
                               │            ▼
                               ▼      server degli strumenti
                          PostgreSQL   (dentro il container agente)
                          (database)
```

Il back-end non ha una porta sul computer: ci arriva solo nginx. Basta un comando:

| Comando | Quando è pronto |
|---|---|
| `docker compose up -d` | `docker compose ps` mostra `agente` e `backend` con `healthy` (l'agente ci mette fino a un minuto) |

Poi apri **<http://127.0.0.1:8780>** in Edge o in Chrome.

Per controllare che tutto sia collegato:

```powershell
Invoke-RestMethod http://127.0.0.1:8780/api/salute
```

La risposta deve dire `stato ok`, `database ok`, `agente ok`.

**Da sapere.**

- Il modello attuale ragiona prima di rispondere: un turno può durare 1–2 minuti.
- Le chat restano salvate anche dopo lo spegnimento.
- Dopo una modifica al codice: `docker compose up -d --build`.

**Per fermare tutto:**

```powershell
docker compose stop
```

Attenzione: `docker compose down -v` **cancella tutte le chat e i progetti**. Per spegnere usa `stop`.

---

## C · Terminale in Docker

```powershell
docker compose build assistente
.\avvia.ps1
```

La chat è la stessa del modo A, ma gira in un container. LM Studio resta sul computer. La riga di benvenuto mostra `Fuso orario: Europe/Berlin (host Windows)`. Si esce con `esci`.

`docker compose build assistente` serve la prima volta e dopo ogni modifica al codice o ai file di `risorse/`: il servizio della CLI non parte con `docker compose up` e non si ricostruisce con `docker compose build` senza nome. Se l'agente della chat nel browser è acceso, `.\avvia.ps1` avvisa che le note sono condivise e chiede `Aprire comunque la CLI? (S/N)`: con una risposta diversa da `S` esce.

---

## Se qualcosa non parte

| Che cosa leggi | Che cosa fare |
|---|---|
| `Impossibile raggiungere LM Studio all'indirizzo …` | LM Studio è chiuso o il suo server non è attivo: aprilo e attiva il server |
| `Il modello '…' non è disponibile su LM Studio` | `LMSTUDIO_MODEL` nel `.env` non è tra i modelli di LM Studio: il messaggio li elenca, copiane uno |
| `Variabili d'ambiente mancanti: …` | manca il file `.env` o una riga è vuota: confrontalo con `.env.example` |
| `Porta … già in uso` oppure `La porta … è occupata` | un altro programma, o un avvio precedente rimasto acceso, usa quella porta: chiudilo o cambia la porta nel `.env`. Con `(AGENTE_PORTA)` c'è probabilmente un `python -m servizio_agente` acceso fuori da Docker: chiudilo e rifai il doppio clic |
| `La chat non risponde del tutto dopo 90 secondi` | il messaggio dice che cosa manca (database, agente o back-end) e il comando per leggerne il log, per esempio `docker compose logs --tail 30 agente` |
| lo stesso messaggio, con `password authentication failed` | la password nel `.env` è diversa da quella con cui il database è stato creato. Rimetti quella vecchia, oppure dai al database quella nuova (vedi sotto): in tutti e due i casi le chat restano. `docker compose down -v` invece **cancella tutte le chat** |
| `Docker Desktop non risponde dopo 180 secondi` | apri Docker Desktop a mano, aspetta che sia pronto e rifai il doppio clic |
| `LM Studio non risponde su … dopo 60 secondi` | apri LM Studio, attiva il server e rifai il doppio clic |
| striscia rossa «Il back-end non risponde: avvialo con python -m servizio_backend.» | il back-end è spento: `docker compose up -d`, oppure rifai il doppio clic. La striscia sparisce da sola, fino a una decina di secondi dopo che il back-end è ripartito |
| `required variable … is missing a value` | Docker Compose non trova una variabile: aggiungila al `.env` come in `.env.example` |
| `.\avvia.ps1` non può essere eseguito perché l'esecuzione di script è disabilitata | `powershell -NoProfile -ExecutionPolicy Bypass -File .\avvia.ps1` |
| la prima risposta è molto lenta | LM Studio sta caricando il modello in memoria: aspetta |

**Cambiare la password del database senza perdere le chat.** Con il database acceso, scrivi la password nuova nel `.env` e poi dalla stessa cartella (al posto di `la-password-nuova` metti la tua, senza apici dentro):

```powershell
docker compose exec -T database psql -U assistente -d assistente -c "ALTER USER assistente WITH PASSWORD 'la-password-nuova';"
```

La risposta è `ALTER ROLE`. Se il back-end è acceso, riavvialo con `docker compose restart backend`: legge la password solo all'avvio. `assistente` è il valore di `POSTGRES_USER` e di `POSTGRES_DB` in `.env.example`: se nel tuo `.env` sono diversi, usa i tuoi.

Per tutto il resto: sezione «Diagnosi» del [README](README.md#diagnosi).

## Dove andare dopo

- **Per studiare il progetto:** [`docs/studio/00-indice.md`](docs/studio/00-indice.md).
- **Per provare gli strumenti:** «Quanto fa (3+4)*2?» deve dare 14; «Se parto il 23 dicembre 2026, quando scadono 3 giorni lavorativi?» deve dare il 29 dicembre 2026.
- **Per i test:** `docker compose run --rm test`, la suite in un container (non serve LM Studio). Su questo computer `python -m pytest` sull'host si ferma: Smart App Control di Windows blocca le DLL di `psycopg`.

---

*Comandi presi dal README. Rieseguiti il 15 novembre 2026: l'avvio e l'uscita del modo A; il cambio della password del database, dopo il quale le chat c'erano ancora. Con lo step 9 il modo A non è stato riprovato insieme all'agente in Docker (non si scontrano più sulla porta degli strumenti, che resta dentro il container, ma condividono le note). Per il modo C il README segnala che l'avvio con la tastiera va ancora confermato: finora è stato provato con l'ingresso da una pipe. Dal 18 novembre 2026 (step 9) il modo B gira in quattro container: provati `avvia-chat.cmd --senza-browser` con agente e back-end spenti (pronto in 15 secondi, `/api/salute` tutto `ok`), `esci` (fermi agente e back-end, accesi database e pagina), il doppio clic con tutto acceso (nessun container fermato), un turno vero con il modello attraverso nginx e la chat ancora presente dopo `docker compose restart backend`; `.\avvia.ps1` con l'agente acceso, con la risposta `N` da una pipe. `docker compose up -d --build` è stato provato con `--wait`. La chiusura della finestra è provata da un test automatico su una console vera e da una prova su un progetto Compose separato. Il 18 novembre l'utente ha chiuso la finestra con un clic vero sulla X: agente e back-end si sono fermati, database e pagina sono rimasti accesi (tipo di console non indicato; una scheda di Windows Terminal non è provata separatamente). Non provati dal vivo: `--ricostruisci` (solo test automatici), Docker spento, LM Studio spento e il doppio clic subito dopo l'accensione del PC.*
