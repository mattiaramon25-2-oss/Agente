# Avvio rapido

Una pagina per far partire l'assistente del laboratorio. I dettagli e tutti i casi particolari restano nel [README](README.md).

Tutti i comandi si scrivono in **PowerShell**, dalla cartella `assistente-laboratorio`.

## Scegli come usarlo

| Modo | Che cosa ottieni | Che cosa deve essere acceso | Comandi |
|---|---|---|---|
| **A · Chat da terminale** | la chat nella finestra di PowerShell | LM Studio | 1 |
| **B · Chat nel browser** | la chat in una pagina web, con le conversazioni salvate | LM Studio e Docker Desktop | 4, in 3 terminali |
| **C · Terminale in Docker** | come A, ma dentro un container | LM Studio e Docker Desktop | 2 |

Se vuoi solo provarlo, parti da **A**.

**Uno alla volta.** Non usare A e B insieme: usano la stessa porta per il server degli strumenti (`MCP_PORTA`), e il secondo che parte si ferma con `Porta … già in uso`. Non usare C insieme ad A o a B: condividono l'archivio delle note.

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

I pezzi da avviare sono quattro. Ognuno parla solo con il vicino:

```text
Browser ──► nginx :8780 ──► back-end :8768 ──► agente :8767 ──► LM Studio :1234
            (container)          │                   │
                                 ▼                   ▼
                          PostgreSQL :5432    server degli strumenti :8765
                            (container)        (lo avvia l'agente)
```

Servono **tre terminali**, tutti nella cartella `assistente-laboratorio` e con l'ambiente attivato. I due comandi `docker compose` tornano subito al prompt; l'agente e il back-end restano in primo piano.

| # | Terminale | Comando | Quando è pronto |
|---|---|---|---|
| 1 | primo | `docker compose up -d database` | `docker compose ps` mostra `database` con `healthy` |
| 2 | secondo | `python -m servizio_agente` | compare `Servizio dell'agente in ascolto su 127.0.0.1:8767 …` |
| 3 | terzo | `python -m servizio_backend` | compare `Back-end delle chat in ascolto su http://127.0.0.1:8768 …` |
| 4 | primo | `docker compose up -d --build frontend` | il comando finisce senza errori |

Poi apri **<http://127.0.0.1:8780>** in Edge o in Chrome.

Per controllare che tutto sia collegato, dal primo terminale:

```powershell
Invoke-RestMethod http://127.0.0.1:8768/salute
```

La risposta deve dire `stato ok`, `database ok`, `agente ok`.

**Da sapere.**

- Il modello attuale ragiona prima di rispondere: un turno può durare 1–2 minuti.
- Le chat restano salvate anche dopo lo spegnimento.
- Dopo una modifica ai file di `frontend/` va ripetuto il comando 4.

**Per fermare tutto:**

1. `Ctrl+C` nel terminale del back-end e in quello dell'agente.
2. Nel primo terminale:

   ```powershell
   docker compose stop frontend
   docker compose stop database
   ```

Attenzione: `docker compose down -v` **cancella tutte le chat e i progetti**. Per spegnere usa `stop`.

---

## C · Terminale in Docker

```powershell
docker compose build
.\avvia.ps1
```

La chat è la stessa del modo A, ma gira in un container. LM Studio resta sul computer. La riga di benvenuto mostra `Fuso orario: Europe/Berlin (host Windows)`. Si esce con `esci`.

`docker compose build` serve la prima volta e dopo ogni modifica al codice o ai file di `risorse/`.

---

## Se qualcosa non parte

| Che cosa leggi | Che cosa fare |
|---|---|
| `Impossibile raggiungere LM Studio all'indirizzo …` | LM Studio è chiuso o il suo server non è attivo: aprilo e attiva il server |
| `Il modello '…' non è disponibile su LM Studio` | `LMSTUDIO_MODEL` nel `.env` non è tra i modelli di LM Studio: il messaggio li elenca, copiane uno |
| `Variabili d'ambiente mancanti: …` | manca il file `.env` o una riga è vuota: confrontalo con `.env.example` |
| `Porta … già in uso` oppure `La porta … è occupata` | un altro programma, o un avvio precedente rimasto acceso, usa quella porta: chiudilo o cambia la porta nel `.env`. Succede anche se provi il modo A con il servizio dell'agente del modo B acceso: usane uno alla volta |
| `Il database PostgreSQL non risponde su 127.0.0.1:…` | il database è spento: `docker compose up -d database` |
| lo stesso messaggio, con `password authentication failed` | la password nel `.env` è diversa da quella con cui il database è stato creato. Rimetti quella vecchia, oppure dai al database quella nuova (vedi sotto): in tutti e due i casi le chat restano. `docker compose down -v` invece **cancella tutte le chat** |
| striscia rossa «Il back-end non risponde: avvialo con python -m servizio_backend.» | il back-end è spento: avvialo (comando 3). La striscia sparisce da sola |
| `required variable … is missing a value` | Docker Compose non trova una variabile: aggiungila al `.env` come in `.env.example` |
| `.\avvia.ps1` non può essere eseguito perché l'esecuzione di script è disabilitata | `powershell -NoProfile -ExecutionPolicy Bypass -File .\avvia.ps1` |
| la prima risposta è molto lenta | LM Studio sta caricando il modello in memoria: aspetta |

**Cambiare la password del database senza perdere le chat.** Con il database acceso, scrivi la password nuova nel `.env` e poi dalla stessa cartella (al posto di `la-password-nuova` metti la tua, senza apici dentro):

```powershell
docker compose exec -T database psql -U assistente -d assistente -c "ALTER USER assistente WITH PASSWORD 'la-password-nuova';"
```

La risposta è `ALTER ROLE`. Se il back-end è acceso, riavvialo: legge la password solo all'avvio. `assistente` è il valore di `POSTGRES_USER` e di `POSTGRES_DB` in `.env.example`: se nel tuo `.env` sono diversi, usa i tuoi.

Per tutto il resto: sezione «Diagnosi» del [README](README.md#diagnosi).

## Dove andare dopo

- **Per studiare il progetto:** [`docs/studio/00-indice.md`](docs/studio/00-indice.md).
- **Per provare gli strumenti:** «Quanto fa (3+4)*2?» deve dare 14; «Se parto il 23 dicembre 2026, quando scadono 3 giorni lavorativi?» deve dare il 29 dicembre 2026.
- **Per i test:** `python -m pytest` (non servono né LM Studio né Docker).

---

*Comandi presi dal README. Rieseguiti il 15 novembre 2026: l'avvio e l'uscita del modo A; nel modo B il servizio dell'agente e il back-end, con `/salute` che risponde `ok` sia direttamente sia attraverso nginx (`http://127.0.0.1:8780/api/salute`), con database e `frontend` già accesi; il cambio della password del database, dopo il quale le chat c'erano ancora; il modo A con il servizio dell'agente acceso, che si ferma con `Porta 8765 già in uso`. Non rieseguiti il 15 novembre: una conversazione completa con il modello, i comandi 1 e 4 del modo B (i due container erano già accesi) e il modo C. Per il modo C il README segnala che l'avvio con la tastiera va ancora confermato: finora è stato provato con l'ingresso da una pipe.*
