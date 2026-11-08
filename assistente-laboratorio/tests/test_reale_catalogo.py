"""Prova reale: il modello sceglie tra search_catalog e get_item e non inventa corsi.

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s
Ogni caso parte da una sessione nuova; si stampa quale strumento è stato scelto (slide 28).
"""

import json
import re

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistente.grafo import esegui_turno
from logica.catalogo import carica_catalogo
from tests.reale import ambiente_reale

pytestmark = pytest.mark.lmstudio

CODICI = {c["codice"] for c in carica_catalogo()}


@pytest.fixture(scope="module")
def ambiente():
    with ambiente_reale() as (grafo, fuso_utente, strumenti):
        yield grafo, fuso_utente, strumenti


def turno(ambiente, domanda):
    grafo, fuso_utente, _ = ambiente
    cronologia = esegui_turno(grafo, [], fuso_utente, domanda)
    chiamate = [c for m in cronologia if isinstance(m, AIMessage) for c in m.tool_calls]
    risultati = {m.tool_call_id: m for m in cronologia if isinstance(m, ToolMessage)}
    risposta = cronologia[-1]
    print(f"\n  domanda:   {domanda}")
    for c in chiamate:
        r = risultati.get(c["id"])
        print(f"  chiamata:  {c['name']} {c['args']} -> {r.status if r else '?'} {r.content if r else ''}")
    print(f"  risposta:  {risposta.text if isinstance(risposta, AIMessage) else risposta!r}")
    assert isinstance(risposta, AIMessage)
    return chiamate, risultati, risposta.text


def riusciti(chiamate, risultati, nome):
    return [json.loads(risultati[c["id"]].content) for c in chiamate
            if c["name"] == nome and c["id"] in risultati and risultati[c["id"]].status == "success"]


def test_ricerca_con_risultati(ambiente):
    chiamate, risultati, risposta = turno(ambiente, "Quali corsi di Python ci sono nel catalogo?")
    ricerche = [c for c in chiamate if c["name"] == "search_catalog"]
    assert ricerche and "python" in str(ricerche[-1]["args"].get("query", "")).casefold()
    trovati = riusciti(chiamate, risultati, "search_catalog")
    assert trovati and trovati[-1]["totale"] >= 2
    titoli = [r["titolo"] for r in trovati[-1]["risultati"]]
    assert any(t.casefold() in risposta.casefold() for t in titoli) or any(
        r["codice"] in risposta for r in trovati[-1]["risultati"]
    )


def test_ricerca_senza_risultati(ambiente):
    chiamate, risultati, risposta = turno(ambiente, "C'è un corso di astrofisica?")
    trovati = riusciti(chiamate, risultati, "search_catalog")
    assert trovati and trovati[-1]["totale"] == 0
    citati = set(re.findall(r"\b[A-Z]{2,4}-\d{2}\b", risposta))
    assert citati <= CODICI, f"codici inventati: {citati - CODICI}"


def test_ricerca_poi_dettaglio(ambiente):
    chiamate, risultati, risposta = turno(ambiente, "Quante ore dura il corso di Deep Learning e LLM?")
    nomi = [c["name"] for c in chiamate]
    assert "search_catalog" in nomi and "get_item" in nomi
    assert nomi.index("search_catalog") < len(nomi) - 1 - nomi[::-1].index("get_item")
    dettagli = riusciti(chiamate, risultati, "get_item")
    assert dettagli and dettagli[-1]["codice"] == "DLL-01"
    assert "120" in risposta


def test_errore_controllato_catalogo(ambiente):
    """Slide 23: invocazione diretta, senza modello, con un codice inesistente."""
    _, _, strumenti = ambiente
    errore = json.loads(next(s for s in strumenti if s.name == "get_item").invoke({"code": "XX-99"}))
    print(f"\n  errore controllato: {errore}")
    assert errore["tipo"] == "strumento" and "Usa prima search_catalog" in errore["errore"]
