# Piano — Lezione 6, step 1: router dell'ambito

Specifica: [`specs/2026-11-09-router-ambito-design.md`](../specs/2026-11-09-router-ambito-design.md). Branch `dev-router`. Ogni task: test che fallisce, codice minimo, `python -m pytest`, commit.

1. **Ambito in configurazione.** `risorse/ambito.json` e `assistente/ambito.py` (`Ambito`, `carica_ambito`, errori chiari). Test: `tests/test_ambito.py`. Commit `feat(ambito): ...`.
2. **Router.** `assistente/router.py`: `DecisioneRouter`, `prompt_router`, `messaggi_router` (ultimi 6 messaggi testuali), `decidi` (fallback su output non valido, errori di collegamento propagati, riga di log). `crea_router(config)` in `assistente/modello.py`. Test: `tests/test_router.py`, `RouterFinto` in `tests/finti.py`. Commit `feat(router): ...`.
3. **Grafo.** Nodi `router` e `rifiuto`, `instrada_dopo_router`, riga `nodo=modello`; `crea_grafo(modello, strumenti, router=None, ambito=None)`. Test in `tests/test_grafo_router.py`. Commit `feat(grafo): ...`.
4. **Avvio.** `__main__.py` e `tests/reale.py` creano router e ambito; prova reale `tests/test_reale_router.py`. Commit `feat(avvio): ...`.
5. **Verifica e documenti.** `python -m pytest`, prova reale `--lmstudio`, README, `docs/studio` (04 con scheda e scaletta, più i capitoli toccati), checkpoint. Commit `docs: ...`.
