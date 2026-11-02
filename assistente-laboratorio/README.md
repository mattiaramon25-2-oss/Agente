# Assistente del laboratorio

Assistente da terminale che conversa con un modello locale servito da LM Studio.
Il flusso è un grafo LangGraph esplicito (`assistente/grafo.py`): il nodo `modello` chiama il modello,
il nodo `strumenti` esegue l'orologio quando il modello lo chiede, il nodo `limite` chiude il turno
dopo 3 giri di strumento. La cronologia resta in memoria per la sessione e si perde alla chiusura.

L'unico strumento è `ora_corrente(fuso)`: restituisce data e ora attuali nel fuso IANA indicato
(per esempio `Asia/Tokyo`). Ogni volta che viene eseguito, il terminale mostra una riga come
`[orologio: Asia/Tokyo]`.

## Requisiti

- Python 3.14
- LM Studio sullo stesso computer, con il server attivo (porta predefinita 1234) e un modello
  scaricato. Provato con `google/gemma-4-e2b`.

## Configurazione

Tutti i comandi si eseguono in PowerShell dalla cartella `assistente-laboratorio`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Poi aprire `.env` e controllare i valori:

| Variabile | Obbligatoria | Significato |
|---|---|---|
| `LMSTUDIO_BASE_URL` | sì | indirizzo del server di LM Studio, per esempio `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL` | sì | identificativo del modello, come restituito da `GET /v1/models` |
| `LMSTUDIO_BASE_URL_DOCKER` | solo per Docker | indirizzo di LM Studio visto dal container |
| `FUSO_ORARIO` | no | fuso IANA di riserva se il rilevamento automatico non riesce |

Per vedere gli identificativi disponibili:

```powershell
(Invoke-RestMethod http://localhost:1234/v1/models).data.id
```

Nessuna credenziale è necessaria: il file `.env` resta fuori da Git.

## Avvio diretto

```powershell
.\.venv\Scripts\Activate.ps1
python -m assistente
```

All'avvio il programma controlla che LM Studio risponda e che il modello configurato sia
nell'elenco, poi mostra il fuso orario in uso e da dove viene. Si esce scrivendo `esci`,
con `Ctrl+C` o a fine input.

Esempio (ingresso inviato con una pipe):

```powershell
"ciao", "che ore sono a Tokyo?", "e a Roma?", "esci" | python -m assistente
```

```
Assistente del laboratorio
Fuso orario: Europe/Berlin (computer locale)
Scrivi «esci» o premi Ctrl+C per uscire.
Tu: Assistente: Ciao! Come posso aiutarti oggi?
Tu: [orologio: Asia/Tokyo]
Assistente: Attualmente a Tokyo sono le **22:57:34 di lunedì**.
Tu: [orologio: Europe/Rome]
Assistente: Attualmente a Roma sono le **14:57:58 di lunedì**.
Tu: Arrivederci.
```

## Avvio con Docker

Serve Docker Desktop acceso. LM Studio resta sull'host: il container lo raggiunge all'indirizzo
`LMSTUDIO_BASE_URL_DOCKER` del file `.env` (`http://host.docker.internal:1234/v1`), che
`compose.yaml` passa all'applicazione come `LMSTUDIO_BASE_URL`. Su questo computer non è
servito attivare in LM Studio l'opzione per servire sulla rete locale.

```powershell
docker compose build
.\avvia.ps1
```

Perché lo script: dentro il container il fuso del sistema è UTC, non quello dell'utente.
`avvia.ps1` legge il fuso di Windows (`(Get-TimeZone).Id`, per esempio `W. Europe Standard Time`)
e lo passa al container in `FUSO_HOST_WINDOWS`; la riga di benvenuto mostra
`Fuso orario: Europe/Berlin (host Windows)`.

Avviando a mano senza lo script, il fuso viene da `FUSO_ORARIO` del file `.env`
(`Fuso orario: Europe/Rome (FUSO_ORARIO)`); se manca anche quello si usa UTC con un avviso.
Con l'ingresso da una pipe serve l'opzione `-T`:

```powershell
"Che ore sono?", "esci" | docker compose run --rm -T assistente
```

> Verificato con ingresso da pipe (`avvia.ps1 -SenzaTty` e il comando sopra). L'avvio interattivo
> `.\avvia.ps1` da tastiera va ancora confermato.

## Test

Test automatici (non servono né LM Studio né Docker; il modello è simulato):

```powershell
python -m pytest
```

Le prove reali sono saltate (`skipped`) se non vengono richieste esplicitamente.
Prova reale con LM Studio acceso: cinque domande sull'ora, ciascuna in una sessione nuova;
per ognuna controlla che il modello chiami davvero `ora_corrente` con il fuso giusto e che l'ora
della risposta sia quella calcolata dallo strumento.

```powershell
python -m pytest --lmstudio -m lmstudio -v -s
```

Prova reale con Docker (Docker Desktop e LM Studio accesi): costruisce l'immagine, avvia con
`avvia.ps1 -SenzaTty` e controlla che il fuso venga dall'host Windows e che l'orologio sia chiamato;
poi avvia con `docker compose run` senza lo script e controlla che si usi `FUSO_ORARIO`.

```powershell
python -m pytest --docker -m docker -v -s
```

Il fuso dell'utente è rilevato una volta sola all'avvio, in quest'ordine:

1. `FUSO_HOST_WINDOWS` (impostata dallo script di avvio con Docker), convertita in nome IANA;
2. fuso del computer (solo fuori da Docker);
3. `FUSO_ORARIO` dal file `.env`;
4. `UTC`, con un avviso ben visibile nella riga di benvenuto.

## Diagnosi

- **`Impossibile raggiungere LM Studio all'indirizzo …`**: LM Studio è chiuso, il server non è
  attivo, oppure `LMSTUDIO_BASE_URL` è sbagliato. Il programma esce con codice 1.
- **`Il modello '…' non è disponibile su LM Studio`**: l'identificativo in `LMSTUDIO_MODEL` non è
  tra quelli restituiti dal server; il messaggio li elenca. Si possono vedere anche con
  `(Invoke-RestMethod http://localhost:1234/v1/models).data.id`.
- **`Variabili d'ambiente mancanti`**: manca il file `.env` (copiarlo da `.env.example`) o una variabile è vuota.
- **La prima risposta è lenta**: l'elenco di LM Studio può includere modelli scaricati ma non
  ancora caricati in memoria; il primo messaggio li carica. Le chiamate hanno un timeout di 120 secondi.
- **`required variable LMSTUDIO_BASE_URL_DOCKER is missing a value`** (con Docker): aggiungere
  `LMSTUDIO_BASE_URL_DOCKER` al file `.env`, come in `.env.example`.
- **Il container non raggiunge LM Studio** (`Impossibile raggiungere LM Studio all'indirizzo
  http://host.docker.internal:1234/v1/models`): controllare che il server di LM Studio sia attivo;
  se basta da fuori ma non dal container, attivare in LM Studio l'opzione per servire sulla rete locale.
- **`.\avvia.ps1` non può essere eseguito perché l'esecuzione di script è disabilitata**: avviarlo
  con `powershell -NoProfile -ExecutionPolicy Bypass -File .\avvia.ps1`, che vale solo per quel comando.
- **`Fuso orario: Europe/Berlin` anche se si è in Italia**: Windows chiama il fuso dell'Europa centrale
  `W. Europe Standard Time`, che la tabella standard traduce in `Europe/Berlin`. È la stessa ora di Roma.
