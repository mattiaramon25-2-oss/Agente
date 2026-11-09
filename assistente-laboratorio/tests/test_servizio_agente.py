"""Servizio HTTP dell'agente con modello e router finti: stessa risposta della CLI."""

import logging
import threading
import time
from datetime import datetime, timezone

import httpx
import openai
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, messages_to_dict

from assistente.ambito import Ambito
from assistente.grafo import crea_grafo, esegui_turno
from assistente.router import DecisioneRouter
from servizio_agente.app import crea_app
from tests.finti import ModelloFinto, RouterFinto, chiamata, chiamata_orologio, orologio_finto, strumento_finto

FUSO = "Europe/Rome"
OROLOGIO = orologio_finto(datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc))
AMBITO = Ambito(("data e ora",), ("poesie",), "Prova un altro provider.")
ORIGINI = {"ora_corrente": "mcp", "converti_unita": "mcp"}
PARAMETRI = {"converti_unita": ["valore", "da", "a"]}


def senza_id(serializzati):
    return [{**m, "data": {k: v for k, v in m["data"].items() if k != "id"}} for m in serializzati]


def in_ambito(n=5):
    return RouterFinto([DecisioneRouter(categoria="conversazione", motivo="ok") for _ in range(n)])


def client(risposte, router=None, strumenti=None):
    grafo = crea_grafo(
        ModelloFinto(list(risposte)), strumenti or [OROLOGIO], router or in_ambito(), AMBITO
    )
    app = crea_app(grafo, fuso=FUSO, modello="google/gemma-4-e2b", origini=ORIGINI, parametri=PARAMETRI)
    return TestClient(app)


def test_salute():
    risposta = client([]).get("/salute")
    assert risposta.status_code == 200
    assert risposta.json() == {"stato": "ok", "modello": "google/gemma-4-e2b", "fuso": FUSO, "strumenti": ORIGINI}


def test_stessa_risposta_e_cronologia_della_cli():
    risposte = [chiamata_orologio("Asia/Tokyo"), AIMessage("Sono le 19:00.")]
    cli = esegui_turno(crea_grafo(ModelloFinto(list(risposte)), [OROLOGIO], in_ambito(), AMBITO), [], FUSO, "che ore sono a Tokyo?")
    api = client(risposte).post("/chat", json={"messaggio": "che ore sono a Tokyo?"})
    assert api.status_code == 200
    corpo = api.json()
    assert corpo["risposta"] == cli[-1].text == "Sono le 19:00."
    assert senza_id(corpo["cronologia"]) == senza_id(messages_to_dict(cli))  # gli id sono casuali
    assert corpo["strumenti"] == [{"nome": "ora_corrente", "origine": "mcp", "argomenti": {"fuso": "Asia/Tokyo"}}]


def test_la_cronologia_restituita_continua_la_conversazione():
    modello = ModelloFinto([AIMessage("Ciao!"), AIMessage("Bene.")])
    app = crea_app(crea_grafo(modello, [OROLOGIO], in_ambito(), AMBITO), fuso=FUSO, modello="m", origini={}, parametri={})
    c = TestClient(app)
    primo = c.post("/chat", json={"messaggio": "ciao"}).json()
    secondo = c.post("/chat", json={"messaggio": "come va?", "cronologia": primo["cronologia"]}).json()
    assert secondo["risposta"] == "Bene."
    assert [m.content for m in modello.chiamate[1][1:]] == ["ciao", "Ciao!", "come va?"]
    assert len(secondo["cronologia"]) == 4


def test_argomenti_nell_ordine_dello_schema():
    strumento = strumento_finto('{"risultato": 2500}')
    risposte = [chiamata("converti_unita", {"a": "m", "da": "km", "valore": 2.5}), AIMessage("2500 m")]
    corpo = client(risposte, strumenti=[strumento]).post("/chat", json={"messaggio": "2,5 km in m?"}).json()
    assert list(corpo["strumenti"][0]["argomenti"]) == ["valore", "da", "a"]


def test_rifiuto_via_http(caplog):
    router = RouterFinto([DecisioneRouter(categoria="fuori_ambito", motivo="poesia")])
    with caplog.at_level(logging.INFO, logger="assistente"):
        corpo = client([], router=router).post("/chat", json={"messaggio": "poesia"}).json()
    assert corpo["risposta"] == "Prova un altro provider." and corpo["strumenti"] == []
    assert "nodo=rifiuto" in caplog.text and "nodo=modello" not in caplog.text
    assert "richiesta endpoint=/chat esito=ok" in caplog.text


def test_richieste_non_valide_in_italiano():
    c = client([])
    for corpo in [{}, {"messaggio": "   "}, {"messaggio": 3}, {"messaggio": "x", "cronologia": "no"},
                  {"messaggio": "x", "cronologia": [{"type": "boh"}]}]:
        risposta = c.post("/chat", json=corpo)
        assert risposta.status_code == 400, corpo
        assert set(risposta.json()) == {"errore"}
    assert "vuoto" in c.post("/chat", json={"messaggio": " "}).json()["errore"]


def test_lm_studio_non_raggiungibile_503(caplog):
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:1234/v1"))
    with caplog.at_level(logging.INFO, logger="assistente"):
        risposta = client([errore]).post("/chat", json={"messaggio": "ciao"})
    assert risposta.status_code == 503
    assert "LM Studio" in risposta.json()["errore"]
    assert "esito=errore" in caplog.text


def test_altro_errore_500():
    risposta = client([RuntimeError("guasto")]).post("/chat", json={"messaggio": "ciao"})
    assert risposta.status_code == 500 and "guasto" in risposta.json()["errore"]


def test_un_turno_alla_volta():
    attivi, massimo = [0], [0]

    class ModelloLento:
        def invoke(self, messaggi, config=None):
            attivi[0] += 1
            massimo[0] = max(massimo[0], attivi[0])
            time.sleep(0.2)
            attivi[0] -= 1
            return AIMessage("ok")

    app = crea_app(crea_grafo(ModelloLento(), [], in_ambito(), AMBITO), fuso=FUSO, modello="m", origini={}, parametri={})
    esiti = []
    fili = [threading.Thread(target=lambda: esiti.append(TestClient(app).post("/chat", json={"messaggio": "x"}).status_code)) for _ in range(3)]
    for f in fili:
        f.start()
    for f in fili:
        f.join()
    assert esiti == [200, 200, 200] and massimo[0] == 1
