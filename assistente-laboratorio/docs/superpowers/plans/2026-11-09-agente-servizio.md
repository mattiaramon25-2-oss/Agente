# Piano — Lezione 6, step 6: l'agente come servizio HTTP

Specifica: [`specs/2026-11-09-agente-servizio-design.md`](../specs/2026-11-09-agente-servizio-design.md). Branch `dev-grafica-gui`. Ogni task: test che fallisce, codice minimo, `python -m pytest`, commit.

1. **Costruzione comune dell'agente.** `assistente/agente.py` con `crea_agente(config, strumenti)`; `__main__.py` e `tests/reale.py` la usano. Test: `tests/test_agente.py`. Commit `refactor(avvio): ...`.
2. **Configurazione.** `AGENTE_PORTA` letta da una funzione dedicata (`leggi_porta_agente`), con controlli su intervallo e porte diverse; `.env.example`. Test in `tests/test_configurazione.py`. Commit `feat(configurazione): ...`.
3. **Applicazione FastAPI.** `servizio_agente/app.py` con `crea_app(grafo, fuso, modello, origini, parametri)`: `/salute`, `/chat`, errori in italiano, lock, riga di log. Funzione comune per le righe degli strumenti condivisa con il terminale. Test: `tests/test_servizio_agente.py` con `TestClient`. Commit `feat(servizio-agente): ...`.
4. **Avvio.** `servizio_agente/__main__.py` (`.env`, `verifica_server`, `prepara_strumenti`, uvicorn su `127.0.0.1:AGENTE_PORTA`, arresto ordinato). Test con il servizio avviato davvero e modello finto. Commit `feat(servizio-agente): ...`.
5. **Prova reale.** `tests/test_reale_servizio_agente.py`: stessa domanda a CLI e API. Commit `test(servizio-agente): ...`.
6. **Verifica e documenti.** `python -m pytest`, `--lmstudio`, README (avvio del servizio, esempi con `Invoke-RestMethod` di PowerShell), `docs/studio` (02, 08 e un capitolo sul servizio), `CLAUDE.md` (struttura e comandi), checkpoint. Commit `docs: ...`.
