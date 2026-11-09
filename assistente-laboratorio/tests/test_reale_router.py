"""Prova reale: il router di LM Studio manda all'agente le domande in ambito e rifiuta le altre.

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s
"""

from langchain_core.messages import AIMessage

import pytest

from assistente.ambito import carica_ambito
from assistente.grafo import esegui_turno
from tests.reale import ambiente_reale, posizione_log, righe_del_log

pytestmark = pytest.mark.lmstudio


@pytest.fixture(scope="module")
def ambiente():
    with ambiente_reale() as (grafo, fuso_utente, strumenti):
        yield grafo, fuso_utente


def _esegui(ambiente, domanda):
    grafo, fuso_utente = ambiente
    inizio = posizione_log()
    cronologia = esegui_turno(grafo, [], fuso_utente, domanda)
    log = righe_del_log(inizio)
    print(f"\n  domanda:  {domanda}\n  risposta: {cronologia[-1].text}\n  log:\n    " + "\n    ".join(log.splitlines()))
    return cronologia, log


def test_in_ambito_passa_all_agente(ambiente):
    cronologia, log = _esegui(ambiente, "che ore sono a Tokyo?")
    assert "nodo=router categoria=conversazione" in log and "esito=ok" in log
    assert "nodo=modello" in log and "nodo=rifiuto" not in log
    assert "tool=ora_corrente" in log
    assert isinstance(cronologia[-1], AIMessage) and cronologia[-1].text != carica_ambito().rifiuto


def test_fuori_ambito_rifiutato(ambiente):
    cronologia, log = _esegui(ambiente, "scrivimi una poesia sul mare")
    assert "nodo=router categoria=fuori_ambito" in log and "esito=ok" in log
    assert "nodo=rifiuto" in log and "nodo=modello" not in log
    assert cronologia[-1].text == carica_ambito().rifiuto
