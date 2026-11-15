# Avvio della chat con un doppio clic — specifica breve

Data: 15 novembre 2026. Branch: `dev-avvio-chat`, da `dev` (`162babc`).

## Intento

L'utente vuole avviare la chat nel browser con un solo gesto: doppio clic su un file, e si apre il sito. Oggi servono quattro comandi in tre terminali, più LM Studio e Docker Desktop aperti a mano.

## Obiettivi

- Un file `avvia-chat.cmd` nella cartella `assistente-laboratorio`: doppio clic, una finestra mostra i passi, poi il browser si apre sulla chat.
- Il file accende da solo ciò che manca: Docker Desktop, il server di LM Studio, i container `database` e `frontend`, il servizio dell'agente e il back-end.
- Un secondo doppio clic, con tutto già acceso, apre solo il browser.
- Se qualcosa non parte, la finestra resta aperta e dice che cosa fare.
- Chiudendo la finestra si spengono l'agente e il back-end avviati dal file.

## Non obiettivi

- Non è lo step 9 della lezione 6: agente e back-end restano programmi Python sul computer, non container.
- Nessuna modifica a `compose.yaml`, ai servizi esistenti, al front-end.
- Nessuna sorveglianza: se un servizio cade dopo l'avvio, il file non lo riavvia.
- Nessun file per Linux o macOS: il progetto gira su Windows.
- Il file non sceglie il modello: resta quello di `LMSTUDIO_MODEL` nel `.env`.

## Anti-obiettivi

- Processi che restano accesi di nascosto dopo la chiusura della finestra.
- Spegnere servizi che il file non ha avviato.
- Una finestra che sparisce senza spiegare l'errore.
- Toccare i dati dell'utente: chat, note, password.

## Approcci considerati

| Approccio | Pro | Contro | Scelta |
|---|---|---|---|
| File `.cmd` che chiama un programma Python nuovo, `python -m avvio_chat` | si prova con `pytest` come il resto; riusa `processo_in_attesa`, che già avvia, aspetta e spegne i processi | due file invece di uno | **scelto** |
| Solo PowerShell (`.ps1` più `.cmd`) | come `avvia.ps1` e `avvia-agente.ps1` | la logica non si prova con i test del progetto | scartato |
| Solo batch, tutto nel `.cmd` | un file solo | attese e controlli HTTP in batch sono fragili e illeggibili | scartato |
| Fare lo step 9: quattro container | un solo `docker compose up` | è un passo della lezione con la sua evidenza; non accende LM Studio né apre il browser | rimandato: è un altro lavoro |

## Decisioni dell'utente (15 novembre 2026)

- Alla chiusura della finestra si spengono agente e back-end. I container `database` e `frontend` restano accesi.
- Se Docker Desktop o LM Studio sono chiusi, il file prova ad accenderli da solo, con `docker desktop start` e `lms server start`.

## Che cosa si costruisce

| File | Contenuto |
|---|---|
| `avvia-chat.cmd` | poche righe, solo ASCII: va nella sua cartella, controlla che `.venv` esista, lancia `python -m avvio_chat`; se il programma esce con un errore, aspetta un tasto |
| `avvio_chat/__main__.py` | legge il `.env`, costruisce le dipendenze vere, chiama `avvia_chat`, traduce gli errori in `Errore: …` e nel codice di uscita |
| `avvio_chat/passi.py` | i passi, uno per funzione, con le dipendenze passate come parametri |
| `tests/test_avvio_chat.py`, `tests/servizio_salute_finto.py` | test automatici, senza Docker e senza LM Studio |
| `.gitattributes` | `*.cmd text eol=crlf`: il file del doppio clic ha sempre la fine riga di Windows |

### I passi

1. **Docker.** `docker info` riesce? Se no: `docker desktop start`, poi si riprova fino a 180 secondi.
2. **LM Studio.** `GET /v1/models` risponde? Se no: `lms server start`, poi si riprova fino a 60 secondi. Poi `verifica_server`: se il modello del `.env` non è nell'elenco, l'errore è quello di sempre e il file non fa altro.
3. **Container.** `docker compose up -d --wait database frontend`. La prima volta l'immagine della pagina va costruita: fino a 10 minuti.
4. **Agente.** Se `/salute` risponde è già acceso e non si tocca. Altrimenti `python -m servizio_agente`, atteso fino a 60 secondi.
5. **Back-end.** Come l'agente, con `python -m servizio_backend`.
6. **Browser.** Si apre `http://127.0.0.1:<FRONTEND_PORTA>` (predefinita 8780).
7. **Attesa.** La finestra resta aperta. Scrivendo `esci`, con `Ctrl+C` o a fine input i servizi avviati dal file si spengono in ordine inverso: prima il back-end, poi l'agente.

Se agente e back-end erano già accesi tutti e due, il file apre il browser ed esce subito: non ha avviato niente, quindi non ha niente da spegnere.

### Che cosa si vede

```text
Assistente del laboratorio · avvio della chat
[1/5] Docker: acceso
[2/5] LM Studio: risponde, modello google/gemma-4-e2b presente
      Accendo database e pagina (la prima volta ci vuole qualche minuto)...
[3/5] Database e pagina: accesi
      Avvio il servizio dell'agente...
[4/5] Agente: pronto su http://127.0.0.1:8767
      Avvio il back-end delle chat...
[5/5] Back-end: pronto su http://127.0.0.1:8768
Apro http://127.0.0.1:8780
La chat è accesa. Per spegnerla scrivi «esci» e premi Invio, oppure chiudi questa finestra.
```

Le righe rientrate compaiono solo quando c'è qualcosa da accendere; quella dei container compare sempre.

### Errori

Ogni errore è una riga `Errore: …` in italiano, che dice che cosa sistemare; il programma esce con codice 1 e la finestra aspetta un tasto.

| Caso | Messaggio |
|---|---|
| manca `.venv` | lo dice il `.cmd`, e rimanda a «La prima volta» di `AVVIO-RAPIDO.md` |
| manca il `.env` o una variabile | quello di `carica_configurazione` e `carica_configurazione_backend` |
| `docker` non esiste | Docker non è installato o non è nel PATH |
| Docker non parte in 180 secondi | aprilo a mano e riprova |
| LM Studio non risponde e `lms` non c'è | apri LM Studio, attiva il server e riprova |
| modello non in elenco | quello di `verifica_server`, con l'elenco dei modelli |
| `docker compose up` fallisce | le ultime righe dell'uscita di Compose |
| `MCP_PORTA` occupata e agente spento | probabilmente è aperta la chat da terminale: chiudila e riprova |
| un servizio non parte | quello di `processo_in_attesa`, con le ultime righe della sua uscita |

L'uscita di agente e back-end va in `logs/avvio_agente.log` e `logs/avvio_backend.log`, fuori da Git come gli altri log.

## Scelte di costruzione (decise da Claude, correggibili)

- **`esci` per spegnere**, come nella chat da terminale. `Ctrl+C` funziona, ma dopo un file `.cmd` Windows chiede «Terminare il processo batch?»: `esci` è più pulito.
- **Un'opzione `--senza-browser`** per le prove: fa tutto tranne aprire il browser.
- **Nessun `--build`** nel comando di Compose: l'immagine si costruisce da sola se manca. Dopo una modifica al front-end resta valido `docker compose up -d --build frontend`.
- **Il pacchetto si chiama `avvio_chat`** e sta alla radice, come `servizio_agente` e `servizio_backend`. Non entra nell'immagine Docker.

## Verifica

- Test automatici con comandi e servizi finti: ogni passo, il riuso di ciò che è già acceso, l'arresto in ordine inverso, nessun processo rimasto, i codici di uscita. La suite resta verde.
- Prova reale, a mano e riportata nel checkpoint: `avvia-chat.cmd` con tutto il resto spento salvo Docker e LM Studio; secondo avvio con tutto acceso; `esci`; chiusura della finestra con la X, con il controllo che le porte dell'agente, del back-end e del server MCP siano libere.
- Se alla chiusura con la X resta un processo, si aggiunge un gestore della chiusura della console e si riprova.
- **Aggiornamento del 15 novembre, durante la costruzione.** Il gestore della console non è servito. Chiudendo la finestra, Windows chiude da sé i processi attaccati a quella console, cioè agente, back-end e server MCP: lo prova un test automatico, che avvia un servizio in una console vera e la chiude con il messaggio del pulsante X. Un Job Object di Windows, provato per primo, è stato tolto dopo la revisione: chiude tutti i discendenti del programma, quindi avrebbe chiuso anche il browser, Docker Desktop e LM Studio avviati dal file.
- I passi «Docker spento» e «LM Studio spento» si provano solo con i test automatici: per provarli dal vivo andrebbero spenti i programmi dell'utente.

## Lasciato a chi costruisce

Nomi delle funzioni interne, testo esatto dei messaggi non elencati qui, forma delle dipendenze finte nei test.
