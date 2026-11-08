"""Prova reale: la stessa domanda con la calcolatrice in variante MCP e in variante locale.

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s
Conta l'ULTIMA chiamata a `calcola` del turno (correzione dopo un errore ammessa).
"""

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistente.grafo import esegui_turno
from tests.reale import ambiente_reale, posizione_log, righe_del_log

pytestmark = pytest.mark.lmstudio

NOME = "calcola"
DOMANDA = "Quanto fa (3+4)*2?"


@pytest.mark.parametrize("variante", ["mcp", "locale"])
def test_il_modello_usa_la_calcolatrice(variante):
    with ambiente_reale({"VARIANTE_CALCOLATRICE": variante}) as (grafo, fuso_utente, strumenti):
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

    assert chiamate, "il modello non ha chiesto calcola"
    messaggio = risultati[chiamate[-1]["id"]]
    assert messaggio.status == "success" and json.loads(messaggio.content)["risultato"] == 14
    assert isinstance(risposta, AIMessage) and "14" in risposta.text
    assert f"origine={variante} tool={NOME}" in righe_del_log(inizio_log)


@pytest.mark.parametrize("variante", ["mcp", "locale"])
def test_errore_controllato_calcolatrice(variante):
    """Slide 23: invocazione diretta, senza modello, di un'espressione vietata."""
    with ambiente_reale({"VARIANTE_CALCOLATRICE": variante}) as (_, _, strumenti):
        calcolatrice = next(s for s in strumenti if s.name == NOME)
        errore = json.loads(calcolatrice.invoke({"espressione": "__import__('os')"}))
    print(f"\n  variante {variante}, errore controllato: {errore}")
    assert errore["tipo"] == "strumento" and "risultato" not in errore
