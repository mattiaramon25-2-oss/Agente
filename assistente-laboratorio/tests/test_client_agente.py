"""Il client HTTP dell'agente: flusso SSE, agente spento, occupato o interrotto."""

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from assistente.grafo import crea_grafo
from assistente.sse import formatta_sse
from servizio_agente.app import crea_app
from servizio_backend.client_agente import AgenteInterrotto, AgenteNonDisponibile, ClientAgente
from tests.finti import ModelloFinto
from tests.test_servizio_agente import AMBITO, FUSO, ORIGINI, OROLOGIO, PARAMETRI, in_ambito


pytestmark = pytest.mark.filterwarnings("ignore:You should not use the .timeout. argument with the TestClient")


def app_agente(modello):
    grafo = crea_grafo(modello, [OROLOGIO], in_ambito(), AMBITO)
    return crea_app(grafo, fuso=FUSO, modello="m", origini=ORIGINI, parametri=PARAMETRI)


def con_trasporto(gestore):
    return ClientAgente("http://agente", client=httpx.Client(transport=httpx.MockTransport(gestore)))


def test_turno_completo():
    agente = ClientAgente("http://testserver", client=TestClient(app_agente(ModelloFinto([AIMessage("Ciao!")]))))
    assert agente.salute() is True
    eventi = list(agente.apri_turno("ciao", [], "").eventi())
    assert eventi[-1][0] == "fine"
    assert eventi[-1][1]["risposta"] == "Ciao!"


def test_istruzioni_inoltrate():
    modello = ModelloFinto([AIMessage("ok")])
    agente = ClientAgente("http://testserver", client=TestClient(app_agente(modello)))
    list(agente.apri_turno("ciao", [], "Sii breve.").eventi())
    assert any("Sii breve." in str(m.content) for m in modello.chiamate[0])


def test_agente_spento():
    agente = ClientAgente("http://127.0.0.1:9")
    with pytest.raises(AgenteNonDisponibile, match="python -m servizio_agente"):
        agente.apri_turno("ciao", [], "")
    assert agente.salute() is False


def test_agente_occupato():
    agente = con_trasporto(lambda r: httpx.Response(409, json={"errore": "occupato"}))
    with pytest.raises(AgenteNonDisponibile) as e:
        agente.apri_turno("ciao", [], "")
    assert str(e.value) == "L'agente sta già rispondendo a un'altra chat: riprova tra poco."


def test_altri_stati_usano_il_campo_errore():
    agente = con_trasporto(lambda r: httpx.Response(400, json={"errore": "Messaggio vuoto."}))
    with pytest.raises(AgenteNonDisponibile, match="Messaggio vuoto."):
        agente.apri_turno(" ", [], "")
    agente = con_trasporto(lambda r: httpx.Response(502, text="<html>"))
    with pytest.raises(AgenteNonDisponibile, match="502"):
        agente.apri_turno("x", [], "")


def test_flusso_interrotto():
    def corpo():
        yield formatta_sse("testo", {"pezzo": "Ci"}).encode()
        raise httpx.ReadError("connessione persa")

    agente = con_trasporto(lambda r: httpx.Response(200, content=corpo()))
    eventi = agente.apri_turno("ciao", [], "").eventi()
    assert next(eventi) == ("testo", {"pezzo": "Ci"})
    with pytest.raises(AgenteInterrotto):
        next(eventi)


def test_chiudi_e_idempotente_anche_con_consumo_parziale():
    agente = con_trasporto(lambda r: httpx.Response(200, content=formatta_sse("testo", {"pezzo": "a"}).encode()))
    turno = agente.apri_turno("ciao", [], "")
    eventi = turno.eventi()
    next(eventi)
    eventi.close()
    turno.chiudi()
    turno.chiudi()


def test_evento_malformato_e_un_flusso_interrotto():
    def gestore(richiesta):
        return httpx.Response(200, content=b"event: fine\ndata: {rotto\n\n")

    turno = con_trasporto(gestore).apri_turno("ciao", [], "")
    with pytest.raises(AgenteInterrotto):
        list(turno.eventi())
