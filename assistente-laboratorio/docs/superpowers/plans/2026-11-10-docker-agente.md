# Piano — il servizio dell'agente in Docker

Specifica: [`specs/2026-11-10-docker-agente-design.md`](../specs/2026-11-10-docker-agente-design.md). Branch `dev-docker-agente`.

1. **`AGENTE_HOST`.** `leggi_host_agente` in `configurazione.py` (predefinito `127.0.0.1`, IP valido); `servizio_agente/__main__.py` la usa per uvicorn e per il messaggio di avvio. Test prima. Commit `feat(servizio-agente): ...`.
2. **Immagine e Compose.** `Dockerfile` copia `servizio_agente/`; servizio `agente` in `compose.yaml`; `avvia-agente.ps1`; `.env.example`. Verifica: `docker compose config` e `docker compose build`. Commit `feat(docker): ...`.
3. **Prova Docker del servizio.** Nuovo test in `tests/test_reale_docker.py` (o file dedicato): avvio, `/salute`, `/chat`, fuso, arresto ordinato. Commit `test(docker): ...`.
4. **Verifica completa.** `python -m pytest`, `--docker` (tutte), `--lmstudio` (tutte), prova manuale con `avvia-agente.ps1`. Correzioni in commit `fix(...)` separati se servono.
5. **Documenti.** README (Docker), `CLAUDE.md` (comando), `docs/studio` 08 e 13 (scheda e scaletta), checkpoint. Commit `docs: ...`.
