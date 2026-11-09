# Piano — streaming della risposta e nuovo testo del rifiuto

Specifica: [`specs/2026-11-09-streaming-rifiuto-design.md`](../specs/2026-11-09-streaming-rifiuto-design.md). Branch `dev-streaming`.

1. **Rifiuto.** Nuovo testo in `risorse/ambito.json`; `tests/test_ambito.py` aggiornato prima. Commit `feat(ambito): ...`.
2. **Grafo.** `esegui_turno_in_streaming` con test in `tests/test_streaming.py`. Commit `feat(grafo): ...`.
3. **Terminale e avvio.** `scrivi_pezzo` in `esegui_sessione`, `__main__` lo passa; test in `tests/test_terminale.py`. Commit `feat(terminale): ...`.
4. **Prova reale.** `tests/test_reale_streaming.py`; aggiornamento di `tests/test_reale_router.py` se serve. Commit `test(streaming): ...`.
5. **Verifica e documenti.** `python -m pytest`, `--lmstudio`, README, `docs/studio` (03, 04 e i capitoli toccati), checkpoint. Commit `docs: ...`.
