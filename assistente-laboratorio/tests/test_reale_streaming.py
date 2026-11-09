"""Prova reale: la risposta di LM Studio arriva a pezzi e il rifiuto ha il testo del file.

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s
"""

import pytest
from langchain_core.messages import AIMessage

from assistente.ambito import carica_ambito
from assistente.grafo import esegui_turno_in_streaming
from tests.reale import ambiente_reale

pytestmark = pytest.mark.lmstudio


@pytest.fixture(scope="module")
def ambiente():
    with ambiente_reale() as (grafo, fuso_utente, strumenti):
        yield grafo, fuso_utente


def _esegui(ambiente, domanda):
    grafo, fuso_utente = ambiente
    pezzi = []
    cronologia = esegui_turno_in_streaming(grafo, [], fuso_utente, domanda, pezzi.append)
    print(f"\n  domanda: {domanda}\n  pezzi:   {len(pezzi)} {pezzi[:8]}\n  finale:  {cronologia[-1].text!r}")
    return cronologia, pezzi


def test_risposta_a_pezzi(ambiente):
    cronologia, pezzi = _esegui(ambiente, "Ciao! Che cosa sai fare? Rispondi in due frasi.")
    assert len(pezzi) > 1, "la risposta non è arrivata in streaming"
    assert isinstance(cronologia[-1], AIMessage)
    assert "".join(pezzi).strip() == cronologia[-1].text.strip()


def test_rifiuto_con_il_nuovo_testo_senza_streaming(ambiente):
    cronologia, pezzi = _esegui(ambiente, "scrivimi una poesia sul mare")
    assert pezzi == []
    assert cronologia[-1].text == carica_ambito().rifiuto
    assert "altro provider" in cronologia[-1].text
