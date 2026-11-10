"""Il servizio HTTP dell'agente in streaming (SSE) con modello e router finti."""

import threading

import httpx
import openai
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from assistente.grafo import crea_grafo
from assistente.router import DecisioneRouter
from assistente.sse import leggi_sse
from servizio_agente.app import crea_app
from tests.finti import RouterFinto, chiamata_orologio
from tests.test_servizio_agente import AMBITO, FUSO, ORIGINI, OROLOGIO, PARAMETRI, client, in_ambito, senza_id


def eventi_stream(c, corpo):
    with c.stream("POST", "/chat/stream", json=corpo) as risposta:
        assert risposta.status_code == 200
        assert risposta.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert risposta.headers["cache-control"] == "no-cache"
        return list(leggi_sse(risposta.iter_lines()))


def test_stream_stessa_risposta_e_cronologia_di_chat():
    risposte = [chiamata_orologio("Asia/Tokyo"), AIMessage("Sono le 19:00.")]
    corpo_chat = client(risposte).post("/chat", json={"messaggio": "che ore sono a Tokyo?"}).json()
    eventi = eventi_stream(client(risposte), {"messaggio": "che ore sono a Tokyo?"})
    nome, fine = eventi[-1]
    assert nome == "fine"
    assert fine["risposta"] == corpo_chat["risposta"]
    assert fine["strumenti"] == corpo_chat["strumenti"]
    assert senza_id(fine["cronologia"]) == senza_id(corpo_chat["cronologia"])


def test_stream_eventi_in_ordine():
    eventi = eventi_stream(client([chiamata_orologio("Asia/Tokyo"), AIMessage("Sono le 19:00.")]), {"messaggio": "ore?"})
    assert [e for e, _ in eventi] == ["strumento", "testo", "fine"]
    assert eventi[0][1] == {"nome": "ora_corrente", "origine": "mcp", "argomenti": {"fuso": "Asia/Tokyo"}}
    assert eventi[1][1] == {"pezzo": "Sono le 19:00."}


def test_stream_rifiuto_senza_pezzi():
    router = RouterFinto([DecisioneRouter(categoria="fuori_ambito", motivo="poesia")])
    eventi = eventi_stream(client([], router=router), {"messaggio": "poesia"})
    assert all(e != "testo" for e, _ in eventi)
    assert eventi[-1][0] == "fine" and eventi[-1][1]["risposta"] == AMBITO.rifiuto


def test_stream_errore_lm_studio():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:1234/v1"))
    ultimo = eventi_stream(client([errore]), {"messaggio": "ciao"})[-1]
    assert ultimo[0] == "errore" and ultimo[1]["stato"] == 503 and "LM Studio" in ultimo[1]["errore"]
    ultimo = eventi_stream(client([RuntimeError("guasto")]), {"messaggio": "ciao"})[-1]
    assert ultimo[0] == "errore" and ultimo[1]["stato"] == 500 and "guasto" in ultimo[1]["errore"]


def test_stream_400_prima_del_flusso():
    c = client([])
    for corpo in [{"messaggio": "  "}, {"messaggio": "x", "cronologia": [{"type": "boh"}]}]:
        risposta = c.post("/chat/stream", json=corpo)
        assert risposta.status_code == 400 and set(risposta.json()) == {"errore"}


def test_stream_409_se_occupato():
    avviato, sblocca = threading.Event(), threading.Event()

    class ModelloBloccato:
        def invoke(self, messaggi, config=None):
            avviato.set()
            sblocca.wait(5)
            return AIMessage("ok")

    app = crea_app(crea_grafo(ModelloBloccato(), [], in_ambito(), AMBITO), fuso=FUSO, modello="m", origini={}, parametri={})
    primo = threading.Thread(target=lambda: TestClient(app).post("/chat", json={"messaggio": "x"}))
    primo.start()
    try:
        assert avviato.wait(5)
        risposta = TestClient(app).post("/chat/stream", json={"messaggio": "y"})
        assert risposta.status_code == 409
        assert risposta.json() == {"errore": "L'agente sta già rispondendo a un'altra richiesta."}
    finally:
        sblocca.set()
        primo.join()
