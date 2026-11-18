# Checkpoint — le istruzioni del progetto rispettate anche con gli strumenti (lezione 6, correzione a parte)

Correzione nata durante le prove dello step 9: nella chat nel browser le istruzioni di un progetto («parla solo in francese») non venivano rispettate. Non ha una specifica sua: tocca il comportamento dello step 7 (campo `istruzioni`, specifica [`2026-11-10-backend-chat-design.md`](../specs/2026-11-10-backend-chat-design.md)).

## Fatto

- **La causa** (prove del 18 novembre 2026 con `google/gemma-4-e2b`). L'agente lega gli strumenti al modello (`bind_tools`); con gli strumenti nella richiesta il modello ignorava le istruzioni scritte in fondo al lungo messaggio di sistema. «Parla solo in francese»: in italiano 5 volte su 5 attraverso l'agente, 3 volte su 3 chiamando LM Studio direttamente con gli strumenti; in francese 3 volte su 3 senza strumenti. Riscrivere l'intestazione o spostare le istruzioni in cima al messaggio di sistema non bastava.
- **La correzione** (`67a6c5b`, poi `ad3e78a` dopo la revisione finale). Il nodo `modello` passa al modello `messaggi_per_il_modello(...)` (`assistente/grafo.py:86-94`): con istruzioni non vuote, l'ultimo `HumanMessage` è sostituito da una **copia** con in fondo «(Promemoria delle istruzioni del progetto, da rispettare in questa risposta: …)» (`_con_promemoria`, `:76-84`). Le istruzioni restano anche in fondo al messaggio di sistema. Lo stato e la cronologia salvata non cambiano; senza istruzioni i messaggi sono identici a prima. La prima versione (`67a6c5b`) metteva il promemoria in un secondo `SystemMessage` subito prima dell'ultima domanda: la revisione finale l'ha scartata perché i template di chat di Gemma 2 e 3 e della famiglia Mistral rifiutano un messaggio `system` dopo il primo posto (`400` a ogni turno con le istruzioni). Corretta anche la spaziatura di `TESTO_NON_JSON` (`grafo.py:37`).
- **Test** (`tests/test_grafo.py`): nessun `SystemMessage` dopo il primo posto; l'ultima domanda passata al modello contiene il promemoria, le precedenti no; dopo un giro di strumento il promemoria è ancora nella copia dell'ultima domanda; la cronologia restituita e quella passata non cambiano; senza istruzioni messaggi identici; contenuto a blocchi con un blocco di testo in più.
- **Documenti.** Capitolo 04, sezione 23 (tabella, motivo, prova dal vivo, limite) e D4 del capitolo 12. I riferimenti `grafo.py:N` di tutti i capitoli di studio (00–12) sono stati controllati sul contenuto, non spostati di un numero fisso: molti erano rimasti a versioni ancora precedenti del file. Cambiati 257 riferimenti (compresi la tabella «Righe» del messaggio di sistema nella sezione 15 del capitolo 04 e i riferimenti di seguito come `` `:172` ``), più 5 riferimenti a `tests/test_grafo.py`. Lasciati com'erano i testi di log e di pytest citati come output (capitolo 09).
- **Prova dal vivo dopo la correzione** (18 novembre 2026). Immagine `agente` ricostruita e ricreata con `docker compose up -d --build --wait agente` (solo quel container), poi `/chat` dell'agente senza stato su `127.0.0.1:8767` (nessuna scrittura nel database):
  - «ciao» con «parla solo in francese», 3 volte: «Bonjour ! Comment puis-je vous aider aujourd'hui ?» tutte e 3 (56, 57, 66 secondi);
  - «che ore sono?» con «parla solo in francese», 2 volte: «Il est actuellement 12h44:15 le mercredi 18 novembre 2026, heure de Rome (Europe/Rome).» e «Il est actuellement 12h45 le mercredi 18 novembre 2026 (heure de Rome).» (111 e 80 secondi), in francese anche dopo lo strumento dell'ora;
  - «ciao» senza istruzioni: «Ciao! Come posso aiutarti oggi?» (54 secondi).
- **La decisione.** È un passo a parte, sul branch `dev-istruzioni-progetto`, da unire **dopo** `dev-quattro-container`: il branch parte dallo step 9 e ne contiene le correzioni della revisione finale (unioni `168e060` e `705fbbd`).

## Da fare

- **Limite che resta:** dopo una chiamata a uno strumento la risposta finale può tornare nella lingua dell'utente. Con la prima versione era successo 1 volta su 2 per «che ore sono?»; dopo la correzione 2 volte su 2 in francese, ma due prove non bastano a escluderlo. Un promemoria anche dopo il risultato dello strumento non aveva aiutato (prova diretta con LM Studio). Il modello lo sceglie l'utente.
- **Immagini da ricostruire** dopo l'unione, perché il codice del grafo è nelle immagini: la chat con `avvia-chat.cmd --ricostruisci` oppure `docker compose up -d --build agente`; la CLI con `docker compose build assistente`.
- **Non provati dal vivo:** la chat nel browser con un progetto con istruzioni (provato solo `/chat` dell'agente), un modello con template Gemma 2/3 o Mistral (la ragione della correzione è dedotta dai template, non da una prova), la CLI (non passa istruzioni e non cambia).
- **Unione:** né in `dev` né in `main`; serve l'approvazione dell'utente, dopo quella di `dev-quattro-container`.

## Stato attuale

- **Branch:** `dev-istruzioni-progetto` (parte da `dev-quattro-container`). Commit: `67a6c5b`, unione `168e060`, `ad3e78a` (promemoria nella copia dell'ultima domanda), `ce72ae3` (documenti di studio), unione `705fbbd`; questo checkpoint è nel commit che li segue. Nessun push, nessuna unione in `dev` o `main`.
- **Test nel container**, 18 novembre 2026, `docker compose run --rm test`: **731 passati, 99 saltati, 0 falliti**.
- **Test sull'host** con `.venv`: `python -m pytest tests/test_grafo.py -q` 34 passati; `tests/test_avvio_chat.py tests/test_avvia_ps1.py tests/test_nginx.py -q` 106 passati e 1 saltato; `--docker tests/test_compose_servizi.py tests/test_compose_frontend.py -q` 7 passati.
- **Container dell'utente:** ricreato solo `agente` (immagine nuova, `healthy`); `database`, `backend` e `frontend` non toccati.
