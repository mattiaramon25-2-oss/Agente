"""Prova reale: il modello di LM Studio usa davvero converti_unita, servito dal server MCP.

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s
Criterio (specifica del convertitore, sezione 10): 5 casi su 5. Conta l'ULTIMA chiamata a
converti_unita del turno, così una correzione dopo un errore dello strumento è ammessa.
"""

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistente.grafo import esegui_turno
from tests.reale import ambiente_reale, posizione_log, righe_del_log

pytestmark = pytest.mark.lmstudio

NOME = "converti_unita"

CASI = [
    ("Quanti metri sono 2,5 km?", (2.5, "km", "m"), 2500),
    ("Converti 750 ml in litri", (750, "ml", "l"), 0.75),
    ("Quanti grammi sono 3 kg?", (3, "kg", "g"), 3000),
    ("Quanto sono 100 °F in gradi Celsius?", (100, "°F", "°C"), 37.78),
    ("Converti 37 °C in Fahrenheit", (37, "°C", "°F"), 98.6),
]


@pytest.fixture(scope="module")
def ambiente():
    with ambiente_reale() as (grafo, fuso_utente, strumenti):
        yield grafo, fuso_utente, strumenti


def forme_del_numero(x: float) -> set[str]:
    """Modi accettabili di scrivere il numero nella risposta."""
    if float(x).is_integer():
        n = int(x)
        forme = {str(n)}
        if n >= 1000:
            forme |= {f"{n:,}", f"{n:,}".replace(",", ".")}
        return forme
    forme = {repr(x), repr(x).replace(".", ",")}
    uno = f"{x:.1f}"
    return forme | {uno, uno.replace(".", ",")}


@pytest.mark.parametrize("domanda, argomenti, atteso", CASI, ids=[c[0] for c in CASI])
def test_il_modello_usa_il_convertitore(ambiente, domanda, argomenti, atteso):
    grafo, fuso_utente, _ = ambiente
    inizio_log = posizione_log()

    cronologia = esegui_turno(grafo, [], fuso_utente, domanda)  # sessione nuova a ogni caso

    chiamate = [c for m in cronologia if isinstance(m, AIMessage) for c in m.tool_calls if c["name"] == NOME]
    risultati = {m.tool_call_id: m for m in cronologia if isinstance(m, ToolMessage)}
    risposta = cronologia[-1]
    print(f"\n  domanda:   {domanda}")
    for c in chiamate:
        r = risultati.get(c["id"])
        print(f"  chiamata:  {c['args']} -> {r.status if r else '?'} {r.content if r else ''}")
    print(f"  risposta:  {risposta.text if isinstance(risposta, AIMessage) else risposta!r}")

    assert chiamate, "il modello non ha chiesto converti_unita"
    ultima = chiamate[-1]
    valore, da, a = argomenti
    assert float(ultima["args"]["valore"]) == valore
    assert (ultima["args"]["da"], ultima["args"]["a"]) == (da, a)
    messaggio = risultati[ultima["id"]]
    assert messaggio.status == "success" and json.loads(messaggio.content)["risultato"] == atteso
    assert isinstance(risposta, AIMessage)
    assert any(forma in risposta.text for forma in forme_del_numero(atteso)), f"numero {atteso} non nella risposta"
    assert f"origine=mcp tool={NOME}" in righe_del_log(inizio_log)
