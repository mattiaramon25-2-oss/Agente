"""Prova reale: la stessa domanda sulle scadenze con la variante MCP e con la variante FastAPI.

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s
Conta l'ULTIMA chiamata a `calcola_scadenza` del turno (correzione dopo un errore ammessa).
"""

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistente.grafo import esegui_turno
from assistente.registro import LOG_API
from tests.reale import ambiente_reale, posizione_log, righe_del_log

pytestmark = pytest.mark.lmstudio

NOME = "calcola_scadenza"
DOMANDA = "Se parto il 23 dicembre 2026, quando scadono 3 giorni lavorativi?"


def dimensione(percorso) -> int:
    return percorso.stat().st_size if percorso.exists() else 0


def righe_dopo(percorso, inizio: int) -> str:
    if not percorso.exists():
        return ""
    with open(percorso, "rb") as file:
        file.seek(inizio)
        return file.read().decode("utf-8", errors="replace")


@pytest.mark.parametrize("variante", ["mcp", "fastapi"])
def test_il_modello_usa_le_scadenze(variante):
    inizio_api = dimensione(LOG_API)
    with ambiente_reale({"VARIANTE_SCADENZE": variante}) as (grafo, fuso_utente, strumenti):
        assert {s.name: (s.metadata or {}).get("origine") for s in strumenti}[NOME] == variante
        inizio_log = posizione_log()
        cronologia = esegui_turno(grafo, [], fuso_utente, DOMANDA)

    chiamate = [c for m in cronologia if isinstance(m, AIMessage) for c in m.tool_calls if c["name"] == NOME]
    risultati = {m.tool_call_id: m for m in cronologia if isinstance(m, ToolMessage)}
    risposta = cronologia[-1]
    print(f"\n  variante:  {variante}\n  domanda:   {DOMANDA}")
    for c in chiamate:
        r = risultati.get(c["id"])
        print(f"  chiamata:  {c['args']} -> {r.status if r else '?'} {r.content if r else ''}")
    print(f"  risposta:  {risposta.text if isinstance(risposta, AIMessage) else risposta!r}")

    assert chiamate, "il modello non ha chiesto calcola_scadenza"
    ultima = chiamate[-1]
    assert ultima["args"]["data_inizio"] == "2026-12-23"
    assert int(ultima["args"]["giorni"]) == 3 and ultima["args"]["lavorativi"] in (True, "true")
    messaggio = risultati[ultima["id"]]
    assert messaggio.status == "success" and json.loads(messaggio.content)["scadenza"] == "2026-12-29"
    assert isinstance(risposta, AIMessage) and "29" in risposta.text
    assert f"origine={variante} tool={NOME}" in righe_del_log(inizio_log)
    righe_api = righe_dopo(LOG_API, inizio_api)
    if variante == "fastapi":
        assert "endpoint=/scadenza" in righe_api
    else:
        assert "endpoint=/scadenza" not in righe_api


@pytest.mark.parametrize("variante", ["mcp", "fastapi"])
def test_errore_controllato_scadenze(variante):
    """Slide 23: invocazione diretta, senza modello, con una data inesistente."""
    with ambiente_reale({"VARIANTE_SCADENZE": variante}) as (_, _, strumenti):
        scadenze = next(s for s in strumenti if s.name == NOME)
        errore = json.loads(scadenze.invoke({"data_inizio": "2026-02-30", "giorni": 1, "lavorativi": True}))
    print(f"\n  variante {variante}, errore controllato: {errore}")
    assert errore["tipo"] == "strumento" and "Data non valida" in errore["errore"] and "scadenza" not in errore
