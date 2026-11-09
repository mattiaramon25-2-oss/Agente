"""Router nel grafo: i due percorsi con risposte del router simulate."""

import logging
from datetime import datetime, timezone

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage

from assistente.ambito import Ambito
from assistente.grafo import crea_grafo, esegui_turno, instrada_dopo_router
from assistente.router import DecisioneRouter
from tests.finti import ModelloFinto, RouterFinto, chiamata_orologio, orologio_finto

FUSO = "Europe/Rome"
AMBITO = Ambito(in_ambito=("data e ora",), fuori_ambito=("poesie",), rifiuto="Fuori dal mio ambito.")


def prepara(decisioni, risposte):
    modello, router = ModelloFinto(risposte), RouterFinto(decisioni)
    grafo = crea_grafo(modello, [orologio_finto(datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc))], router, AMBITO)
    return modello, router, grafo


def test_instradamento():
    assert instrada_dopo_router({"categoria": "conversazione"}) == "modello"
    assert instrada_dopo_router({"categoria": "fuori_ambito"}) == "rifiuto"


def test_nodi_del_grafo():
    _, _, grafo = prepara([], [])
    assert {"router", "modello", "strumenti", "limite", "rifiuto"} <= set(grafo.get_graph().nodes)


def test_in_ambito_passa_all_agente(caplog):
    modello, router, grafo = prepara(
        [DecisioneRouter(categoria="conversazione", motivo="chiede l'ora")],
        [chiamata_orologio("Asia/Tokyo"), AIMessage("Sono le 19:00.")],
    )
    with caplog.at_level(logging.INFO, logger="assistente"):
        cronologia = esegui_turno(grafo, [], FUSO, "che ore sono a Tokyo?")
    assert cronologia[-1].content == "Sono le 19:00."
    assert len(modello.chiamate) == 2 and len(router.chiamate) == 1
    righe = caplog.text
    assert "nodo=router categoria=conversazione motivo=chiede l'ora esito=ok" in righe
    assert righe.count("nodo=modello") == 2
    assert righe.index("nodo=router") < righe.index("nodo=modello")
    assert "nodo=rifiuto" not in righe


def test_fuori_ambito_rifiutato_senza_agente(caplog):
    modello, router, grafo = prepara([DecisioneRouter(categoria="fuori_ambito", motivo="testo creativo")], [])
    with caplog.at_level(logging.INFO, logger="assistente"):
        cronologia = esegui_turno(grafo, [], FUSO, "scrivimi una poesia sul mare")
    assert [type(m).__name__ for m in cronologia] == ["HumanMessage", "AIMessage"]
    assert cronologia[1].content == "Fuori dal mio ambito."  # testo fisso, senza il motivo
    assert "testo creativo" not in cronologia[1].content
    assert modello.chiamate == []
    assert "nodo=router categoria=fuori_ambito motivo=testo creativo esito=ok" in caplog.text
    assert "nodo=rifiuto" in caplog.text and "nodo=modello" not in caplog.text


def test_domanda_e_rifiuto_restano_nella_cronologia():
    modello, router, grafo = prepara(
        [DecisioneRouter(categoria="fuori_ambito", motivo="sport"), DecisioneRouter(categoria="conversazione", motivo="saluto")],
        [AIMessage("Ciao!")],
    )
    primo = esegui_turno(grafo, [], FUSO, "chi ha vinto ieri?")
    secondo = esegui_turno(grafo, primo, FUSO, "ciao")
    assert [m.content for m in secondo] == ["chi ha vinto ieri?", "Fuori dal mio ambito.", "ciao", "Ciao!"]
    assert [m.content for m in router.chiamate[1][1:]] == ["chi ha vinto ieri?", "Fuori dal mio ambito.", "ciao"]


def test_router_difettoso_non_blocca(caplog):
    modello, _, grafo = prepara([ValueError("output non valido")], [AIMessage("Ciao!")])
    with caplog.at_level(logging.INFO, logger="assistente"):
        cronologia = esegui_turno(grafo, [], FUSO, "ciao")
    assert cronologia[-1].content == "Ciao!"
    assert "esito=errore" in caplog.text and "nodo=modello" in caplog.text


def test_errore_di_collegamento_come_oggi():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:1234/v1"))
    modello, _, grafo = prepara([errore], [])
    with pytest.raises(openai.APIConnectionError):
        esegui_turno(grafo, [], FUSO, "ciao")
    assert modello.chiamate == []


def test_senza_router_il_grafo_resta_quello_della_lezione_5():
    grafo = crea_grafo(ModelloFinto([AIMessage("Ciao!")]), [])
    assert "router" not in grafo.get_graph().nodes
    assert esegui_turno(grafo, [], FUSO, "ciao")[-1].content == "Ciao!"


def test_router_e_ambito_vanno_insieme():
    with pytest.raises(ValueError):
        crea_grafo(ModelloFinto([]), [], RouterFinto([]), None)
