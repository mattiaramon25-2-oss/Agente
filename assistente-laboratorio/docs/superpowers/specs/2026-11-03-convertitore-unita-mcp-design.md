# Convertitore di unità tramite MCP — specifica

Data: 2026-11-03 · Stato: approvata (2026-11-03) · Branch: `dev`

Estende l'assistente descritto in `2026-11-02-assistente-laboratorio-design.md`, che resta valida per tutto ciò che qui non cambia. Le regole generali di lavoro sono nel `CLAUDE.md` alla radice della repository.

## 1. Intento

Lezione 5 del corso («MCP: dalle funzioni agli strumenti condivisi»). L'assistente riceve il suo primo strumento esposto tramite **MCP**: un convertitore di unità. Il percorso deve essere reale e verificabile:

1. il catalogo arriva dal server (discovery);
2. il modello chiede lo strumento;
3. il server lo esegue;
4. il risultato rientra nella cronologia come ToolMessage correlato alla richiesta;
5. tutto resta tracciato nei log.

Il convertitore è il primo dei sei strumenti proposti nella lezione (slide 25). Gli altri arriveranno in incrementi successivi, nello **stesso server MCP**: questa specifica copre solo il convertitore e l'infrastruttura che gli serve.

## 2. Obiettivi

1. Strumento `converti_unita` per unità metriche di lunghezza, massa e volume, più °C ↔ °F.
2. Un unico server MCP («server degli strumenti»), scritto con `fastmcp`, che gira come processo a sé e comunica con Streamable HTTP. Ospiterà anche gli strumenti futuri.
3. L'agente scopre gli strumenti dal server (`tools/list`) con `langchain-mcp-adapters` e li passa al modello con `bind_tools`. Nome, descrizione e schema non sono riscritti a mano nel client.
4. Un solo comando avvia tutto: l'agente avvia il server, controlla che risponda in MCP e alla fine lo spegne. Se qualcosa va storto stampa un errore chiaro.
5. Due file di log permettono di dimostrare che il modello ha usato davvero lo strumento.
6. Il grafo resta sincrono e riconoscibile, e `ora_corrente` resta uno strumento locale.

## 3. Non obiettivi

- Gli altri cinque strumenti della lezione: calcolatrice, scadenze, catalogo, note, meteo.
- Portare `ora_corrente` nel server MCP: resta locale, come ammette la slide 3.
- Unità non metriche (miglia, libbre, galloni…), con l'unica eccezione di °F. Restano fuori anche kelvin, tonnellate, quintali, m³/cm³ e i prefissi µ.
- Trasporto stdio, resources e prompts MCP.
- Grafo o interfaccia asincroni.
- Server raggiungibile dalla rete o da altri computer, autenticazione.

## 4. Anti-obiettivi (lo renderebbero un fallimento anche se "funziona")

- Il modello calcola la conversione da solo e la risposta sembra giusta, ma lo strumento non è stato usato (falso successo).
- Nome, descrizione o schema dello strumento scritti a mano nel client invece che ricevuti dal server.
- Una conversione non valida restituisce comunque un numero.
- Un errore di collegamento (server spento, timeout) si presenta come "unità sconosciuta", o il contrario.
- Dopo l'uscita dall'agente resta acceso un processo del server.
- I risultati mostrano artefatti della virgola mobile, come `100.00000000000001`.
- Test con modello o risposte simulate presentati come prova che il modello locale sa usare lo strumento.

## 5. Comportamento

### 5.1 Strumento `converti_unita`

**Argomenti** (tutti obbligatori):

| Nome | Tipo | Note |
|---|---|---|
| `valore` | numero | il valore da convertire |
| `da` | unità | unità di partenza |
| `a` | unità | unità di arrivo |

**Numeri scritti come testo** — *scelta mia*. I modelli piccoli a volte mandano il valore come testo:
- `"2.5"`, con il punto decimale, è accettato come 2.5. È il comportamento predefinito della validazione;
- `"2,5"`, con la virgola, è rifiutato con un messaggio che chiede di usare il punto (`2.5`). La virgola è ambigua (`1,000` e `1.000`), quindi il modello deve riprovare.

Nello schema `valore` resta di tipo numero.

**Unità ammesse**: un elenco chiuso, visibile nello schema del catalogo come enumerazione, così il modello lo riceve con la discovery. I simboli sono esatti e sensibili alle maiuscole; non ci sono alias (`L`, `Km`, `C`…) — *scelta mia*.

| Grandezza | Unità |
|---|---|
| lunghezza | `km`, `hm`, `dam`, `m`, `dm`, `cm`, `mm` |
| massa | `kg`, `hg`, `dag`, `g`, `dg`, `cg`, `mg` |
| volume | `hl`, `dal`, `l`, `dl`, `cl`, `ml` |
| temperatura | `°C`, `°F` |

**Calcolo**
- Si usa l'aritmetica decimale esatta, partendo dalla rappresentazione decimale del valore ricevuto. Così `0.1 km → m` dà `100` e non `100.00000000000001`.
- Lunghezza, massa e volume si convertono con le potenze di 10, senza arrotondamenti.
- Temperature: °F = °C × 9/5 + 32 e °C = (°F − 32) × 5/9. Il risultato è arrotondato a 2 decimali in **entrambe** le direzioni, per coerenza — *scelta mia*.
- Se `da` e `a` coincidono, il valore torna invariato e non è un errore — *scelta mia*.

**Risultato** (JSON, come quello dell'orologio):

```json
{"valore": 2.5, "da": "km", "a": "m", "risultato": 2500, "grandezza": "lunghezza"}
```

Un risultato intero si scrive senza `.0`. Il formato esatto dei numeri è lasciato al costruttore, purché non compaiano artefatti della virgola mobile.

**Errori dello strumento.** Hanno un messaggio in italiano, comprensibile al modello, e non contengono mai un risultato numerico:
- unità sconosciuta: il messaggio elenca le unità ammesse;
- grandezze incompatibili (`kg → m`, `°C → l`…);
- valore non numerico, non finito (NaN, infinito) o booleano;
- valore negativo per lunghezza, massa o volume (lo zero è ammesso);
- temperatura sotto lo zero assoluto (−273,15 °C / −459,67 °F);
- risultato troppo grande per essere rappresentato.

Se la validazione automatica dello schema non produce già un messaggio comprensibile in italiano con l'elenco delle unità ammesse, la validazione va fatta nel codice dello strumento.

Il server segnala questi errori con il meccanismo di errore di MCP (risultato con `isError`), non come un risultato normale — *scelta mia*: così l'errore resta riconoscibile anche a livello di protocollo.

### 5.2 Server MCP

- Un unico server, scritto con `fastmcp`. Nome visibile nel catalogo: «Strumenti laboratorio» — *scelta mia*.
- Trasporto Streamable HTTP, solo su `127.0.0.1`: il server non è raggiungibile da altri computer. Percorso `/mcp`, porta passata all'avvio.
- La logica di conversione sta in un modulo separato dalla registrazione MCP e non dipende da `fastmcp` (slide 18: separare logica, registrazione e messaggi). Così si testa da sola.
- Di norma il server lo avvia l'agente, ma si può avviare anche da solo con un comando documentato. Serve per provarlo con MCP Inspector o con un altro client MCP: è un servizio utilizzabile da applicazioni diverse — *scelta mia*.
- Il server scrive in `logs/server_mcp.log` (sezione 5.6). Il suo output non deve mai finire nel terminale della chat.

### 5.3 Avvio e arresto (un solo comando)

Il comando di avvio resta quello di oggi: `python -m assistente` per l'avvio diretto, `.\avvia.ps1` per Docker.

Sequenza:

1. Lettura della configurazione, compresa la nuova `MCP_PORTA` (sezione 6).
2. Controllo di LM Studio, invariato.
3. Controllo che la porta sia libera. Se è occupata, anche da un server rimasto acceso: *«Porta 8765 già in uso: chiudi il programma che la usa o cambia MCP_PORTA nel .env»*.
4. Avvio del server come processo separato, con lo stesso interprete Python. Il suo output va nel file di log del server.
5. Attesa che il server risponda **in MCP**: deve riuscire una discovery `tools/list`, non basta un HTTP 200 (slide 24). L'attesa dura al massimo 10 secondi — *scelta mia*. Se il processo termina prima, o il tempo scade: *«Il server MCP non è partito»*, con le ultime righe di `logs/server_mcp.log`.
6. Controllo del catalogo:
   - deve contenere almeno uno strumento, altrimenti *«Il server MCP non espone nessuno strumento»*;
   - nessun nome deve coincidere con quello di uno strumento locale (`ora_corrente`), altrimenti l'errore ha il nome in conflitto — *scelta mia*.
7. Riga di benvenuto e chat. *(Scelta mia)* La riga di benvenuto elenca anche gli strumenti MCP scoperti, per esempio `Strumenti MCP: converti_unita`.

In ogni caso di errore la chat non si apre, il server viene spento e il programma esce con codice diverso da zero, senza traceback, come succede oggi per LM Studio.

**Arresto.** All'uscita (`esci`, Ctrl+C, EOF, errore imprevisto) l'agente spegne sempre il server: prima con una richiesta di chiusura, poi in modo forzato dopo un breve tempo. Non devono restare processi orfani.

**Server che cade a sessione in corso.** La chiamata termina con un errore di collegamento (sezione 5.4), la chat continua e il problema compare nei log. L'agente non tenta di riavviare il server — *scelta mia*.

### 5.4 Collegamento agente ↔ server

- Client: `MultiServerMCPClient` di `langchain-mcp-adapters`, con una sola connessione Streamable HTTP a `http://127.0.0.1:<MCP_PORTA>/mcp`.
- Discovery una volta all'avvio. Gli strumenti ottenuti, che sono solo asincroni, vengono avvolti da un piccolo **ponte** in strumenti LangChain sincroni, con lo stesso nome, la stessa descrizione e lo stesso schema ricevuti dal server. Il grafo li tratta come qualsiasi altro strumento.
- Ogni chiamata è una richiesta indipendente: il ponte la esegue in modo sincrono e attende al massimo 10 secondi — *scelta mia*.
- Il ponte non solleva mai eccezioni verso il grafo. Restituisce sempre un contenuto `{"errore": "..."}` con `status="error"`, distinguendo almeno:
  - **errore dello strumento**: il messaggio del server (sezione 5.1);
  - **errore di collegamento**: server non raggiungibile, timeout o risposta non valida, per esempio *«Server MCP non raggiungibile: …»*.
- L'identificativo della chiamata del modello (`tool_call_id`) e l'id JSON-RPC del protocollo sono diversi (slide 12). Il server non riceve il `tool_call_id`.

### 5.5 Grafo, messaggio di sistema e terminale

- Struttura del grafo invariata. Gli strumenti passati a `crea_modello` e `crea_grafo` sono l'orologio locale più gli strumenti MCP scoperti.
- Messaggio di sistema: si aggiunge una regola generica, cioè per conversioni e calcoli usa sempre gli strumenti disponibili, senza farli a mente. Non serve nominare lo strumento — *scelta mia*: il nome e lo schema li fornisce il catalogo.
- Diventano generici i testi che oggi citano solo l'orologio:
  - il testo del limite di giri, oggi «troppe chiamate all'orologio»;
  - il messaggio per argomenti non JSON, che oggi usa l'esempio `{"fuso": …}`.
- Terminale: per ogni chiamata a `converti_unita` eseguita con successo nel turno compare una riga come `[convertitore: 2.5 km → m]`, accanto a quelle già esistenti `[orologio: …]`.

### 5.6 Log

Due file nella cartella `logs/`, esclusa da Git. Il formato esatto è lasciato al costruttore, purché siano righe leggibili, con data e ora e campi `chiave=valore`.

**`logs/assistente.log`** (lato agente):
- all'avvio: porta, server avviato, catalogo scoperto (nomi degli strumenti);
- per **ogni** chiamata a uno strumento, locale o MCP: `origine` (`locale`/`mcp`), `tool`, `call_id`, `argomenti`, `esito`, `risultato` o messaggio di errore, `tool_message.call_id`. L'esito vale `ok`, `errore_tool`, `errore_collegamento`, `strumento_sconosciuto` o `limite`;
- all'uscita: server spento.

Esempio:

```
2026-11-03 10:15:02 origine=mcp tool=converti_unita call_id=call_01 argomenti={"valore":2.5,"da":"km","a":"m"} esito=ok risultato={"risultato":2500,...} tool_message.call_id=call_01
```

**`logs/server_mcp.log`** (lato server):
- avvio e arresto;
- ogni chiamata ricevuta, con strumento, argomenti ed esito;
- l'output del processo, per esempio messaggi della libreria ed eventuali traceback.

Le due tracce si confrontano per strumento, argomenti e ora, perché il `call_id` non arriva al server.

I file si accumulano tra sessioni, con nuove righe in coda. Nessuna rotazione — *scelta mia*.

## 6. Configurazione

Nuova variabile, aggiunta a `.env.example`:

| Variabile | Obbligatoria | Esempio | Note |
|---|---|---|---|
| `MCP_PORTA` | sì | `8765` | porta locale del server MCP; intero tra 1024 e 65535 |

- Obbligatoria come le variabili di LM Studio, coerente con la regola «nessun valore di configurazione nel codice» — *scelta mia*. Se manca o non è valida, il messaggio è chiaro come quello di oggi.
- L'indirizzo è sempre `127.0.0.1`, perché agente e server stanno sullo stesso computer o nello stesso container. Non è configurabile.
- Il `.env` reale va aggiornato a mano dall'utente; il README lo dice.

## 7. Docker

- Server e agente girano nello **stesso container**: l'agente avvia il server come in locale. `compose.yaml` resta con un solo servizio e la porta non va pubblicata.
- Il `Dockerfile` copia anche il codice del server.
- `compose.yaml` monta `./logs` sulla cartella dei log del container, così i log restano leggibili sull'host anche dopo `--rm` — *scelta mia*.
- `logs` va aggiunta a `.dockerignore`.
- `avvia.ps1` resta invariato.
- Da verificare nel piano: compatibilità di `fastmcp` e `langchain-mcp-adapters` con Python 3.14, sia in locale sia nell'immagine `python:3.14-slim`.

## 8. Dipendenze

Le due nuove dipendenze sono concordate con l'utente:

| Pacchetto | Ruolo | Usato da |
|---|---|---|
| `fastmcp` | server MCP | server |
| `langchain-mcp-adapters` | client MCP e conversione del catalogo in strumenti LangChain | agente |

- Le versioni sono fissate e verificate su PyPI nel piano, compresa la compatibilità tra le due: entrambe dipendono dal pacchetto `mcp`.
- Compatibilità verificata dal revisore il 2026-11-03 su PyPI con Python 3.14 e le versioni già fissate (da riconfermare nel piano):
  - l'ultima `fastmcp` (4.x) richiede `mcp>=2.3`, mentre l'ultima `langchain-mcp-adapters` (0.3.2) richiede `mcp<2`, quindi non convivono;
  - la combinazione che si risolve senza conflitti è `fastmcp` 3.4.11 + `langchain-mcp-adapters` 0.3.2 (con `mcp` 1.30.0);
  - si resta quindi sulla serie 3.x di `fastmcp`.
- *(Scelta mia)* Si fissa anche `mcp` in `requirements.txt`, pur essendo una dipendenza indiretta. Una versione 2.x arrivata per sbaglio romperebbe l'adattatore all'importazione.
- Restano in un solo `requirements.txt` — *scelta mia*: agente e server condividono ambiente virtuale e container.
- Nessun'altra dipendenza diretta senza accordo.

## 9. Struttura

Tutto dentro `assistente-laboratorio/`. I nomi sono lasciati al costruttore, ma la separazione va rispettata:

- un nuovo pacchetto per il server, accanto ad `assistente/`, con:
  - la logica di conversione, pura;
  - la registrazione MCP;
  - il punto di avvio, con la porta come argomento;
- in `assistente/`:
  - gestione del processo del server (avvio, attesa, arresto);
  - client e ponte MCP;
  - configurazione dei log;
  - modifiche minime a `configurazione.py`, `grafo.py`, `terminale.py` e `__main__.py`;
- `logs/` in `.gitignore` e `.dockerignore`.

## 10. Test e verifiche

**Test automatici** (sempre eseguibili, senza LM Studio né Docker):

- **Logica di conversione**:
  - ogni grandezza con più prefissi;
  - esattezza decimale (`0.1 km → 100 m`);
  - °C ↔ °F in entrambe le direzioni, con arrotondamento;
  - stessa unità;
  - tutti gli errori della sezione 5.1.
- **Server senza rete** (client in memoria di `fastmcp`):
  - `tools/list` espone `converti_unita` con descrizione e schema, compresa l'enumerazione delle unità;
  - `tools/call` dà un risultato corretto con un input noto;
  - un errore dello strumento arriva come errore MCP.
- **Ponte e avvio con il server reale** in un processo locale su una porta libera, senza modello — *scelta mia*: sono veloci e locali, quindi stanno tra i test automatici:
  - discovery;
  - chiamata riuscita;
  - errore dello strumento;
  - errore di collegamento con il server spento;
  - porta occupata;
  - server che non parte, con le righe del log nel messaggio;
  - arresto senza processi orfani.
- **Grafo con modello finto** che chiede `converti_unita`:
  - ToolMessage correlato al `call_id`;
  - righe in `logs/assistente.log` con i campi della sezione 5.6;
  - il limite di giri funziona ancora.
- **Terminale**: riga `[convertitore: …]` solo per le chiamate riuscite.

**Prove reali** (attivate esplicitamente, come oggi):

- **LM Studio**: 5 domande di conversione, per esempio:
  - «Quanti metri sono 2,5 km?»
  - «Converti 750 ml in litri»
  - «Quanti grammi sono 3 kg?»
  - «100 °F in Celsius»
  - «37 °C in Fahrenheit»

  **Criterio deciso con l'utente: 5 su 5.** Vale come riuscita anche una domanda in cui il modello sbaglia gli argomenti, riceve l'errore dello strumento e si corregge entro il limite di giri. Conta l'ultima chiamata del turno, che deve:
  - chiamare `converti_unita` con argomenti corretti;
  - far comparire il risultato dello strumento nella cronologia;
  - portare a una risposta il cui numero coincide con quello calcolato.

  I tentativi corretti dopo un errore vengono comunque riportati nel resoconto.

  Il numero coincide se è scritto con il punto o con la virgola decimale, con o senza separatore delle migliaia (`2500`, `2.500`, `2,500`…). Per le temperature basta che sia arrotondato a 1 decimale (`37,8` per 37.78) — *scelta mia*.

  Se il modello fallisce: al massimo un paio di ritocchi alla descrizione e al messaggio di sistema, poi si riporta l'esito e si prova un altro modello cambiando solo `LMSTUDIO_MODEL`.
- **Errore controllato**: invocazione diretta dello strumento con un'unità non valida, senza passare dal modello (slide 23). Il risultato è un errore senza un falso risultato.
- **Docker**: avvio con `avvia.ps1` e una domanda di conversione. Nell'output compare `[convertitore: …]`, e le due tracce sono in `logs/` sull'host.

Ogni resoconto indica cosa è stato eseguito, con quale esito e cosa resta da provare.

## 11. Git e documentazione

- Lavoro nel branch `dev`, con commit in Conventional Commits in italiano e incrementi piccoli verificati.
- README: nuova variabile `MCP_PORTA`, avvio (anche del solo server), dove trovare i log, nuovi comandi di test, diagnosi per livelli. Solo comandi verificati. La diagnosi segue i livelli della slide 24:

  | Sintomo | Cosa controllare |
  |---|---|
  | processo del server non avviato | interprete, dipendenze, percorsi, variabili |
  | processo attivo, catalogo assente | trasporto, compatibilità delle versioni, output del server |
  | server HTTP avviato, client senza risposta | indirizzo, porta, trasporto, timeout |
  | strumento nel catalogo, ma nessuna chiamata | descrizione, messaggio di sistema, supporto al tool calling del modello |
  | risultato corretto, risposta sbagliata | ToolMessage, cronologia, interpretazione del modello |
- `CLAUDE.md`:
  - aggiornare la struttura e i comandi;
  - nei «Confini», MCP diventa parte del progetto: solo gli strumenti concordati, uno alla volta;
  - nelle «Scelte tecniche», il codice resta sincrono e il ponte MCP è l'unico punto che usa l'asincronia.

## 12. Lasciato al costruttore

- Nomi di moduli, funzioni e del pacchetto del server.
- Testo esatto della descrizione dello strumento, dei messaggi di errore e del messaggio di sistema, nel rispetto della sezione 5.
- Formato esatto delle righe di log e dei numeri nel risultato.
- Come controllare che la porta sia libera e come spegnere il server su Windows e nel container.
- Come realizzare il ponte sincrono, purché non sollevi eccezioni verso il grafo e rispetti il timeout.
- Come avviare un server reale nei test e come trovare una porta libera.
