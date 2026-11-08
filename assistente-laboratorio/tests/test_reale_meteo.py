"""Prova reale del meteo: modello di LM Studio, server MCP e servizio Open-Meteo veri.

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s
Richiede la rete: senza, il test fallisce con l'errore «Servizio meteo non disponibile»,
che è proprio l'evidenza voluta (distinto da «città non trovata»).
"""

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistente.grafo import esegui_turno
from tests.reale import ambiente_reale

pytestmark = pytest.mark.lmstudio


@pytest.fixture(scope="module")
def ambiente():
    with ambiente_reale() as (grafo, fuso_utente, strumenti):
        yield grafo, fuso_utente, strumenti


def forme_della_temperatura(valore: float) -> set[str]:
    forme = set()
    for testo in (f"{valore:.1f}", f"{round(valore):d}", repr(valore)):
        forme |= {testo, testo.replace(".", ",")}
    return forme


def test_il_modello_usa_il_meteo(ambiente):
    grafo, fuso_utente, _ = ambiente
    domanda = "Che tempo fa a Udine?"
    cronologia = esegui_turno(grafo, [], fuso_utente, domanda)
    chiamate = [c for m in cronologia if isinstance(m, AIMessage) for c in m.tool_calls if c["name"] == "get_weather"]
    risultati = {m.tool_call_id: m for m in cronologia if isinstance(m, ToolMessage)}
    risposta = cronologia[-1]
    print(f"\n  domanda:   {domanda}")
    for c in chiamate:
        r = risultati.get(c["id"])
        print(f"  chiamata:  {c['args']} -> {r.status if r else '?'} {r.content if r else ''}")
    print(f"  risposta:  {risposta.text if isinstance(risposta, AIMessage) else risposta!r}")

    assert chiamate, "il modello non ha chiesto get_weather"
    ultima = chiamate[-1]
    assert "udine" in str(ultima["args"].get("city", "")).casefold()
    messaggio = risultati[ultima["id"]]
    assert messaggio.status == "success", messaggio.content
    dati = json.loads(messaggio.content)
    assert isinstance(risposta, AIMessage) and "udine" in risposta.text.casefold()
    assert any(f in risposta.text for f in forme_della_temperatura(dati["temperatura"]["valore"]))


def test_errore_controllato_meteo(ambiente):
    """Slide 23: invocazione diretta, senza modello, con una città che non esiste."""
    _, _, strumenti = ambiente
    errore = json.loads(next(s for s in strumenti if s.name == "get_weather").invoke({"city": "Xqzvbnmlkj"}))
    print(f"\n  errore controllato: {errore}")
    assert errore["tipo"] == "strumento" and "Città non trovata" in errore["errore"]
