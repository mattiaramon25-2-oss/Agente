"""Wrapper HTTP delle scadenze: contratto scritto a mano ma identico al catalogo MCP, errori tradotti."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente.wrapper_scadenze import ORIGINE_FASTAPI, TIMEOUT_HTTP, crea_wrapper_scadenze
from servizio_api.app import crea_app
from tests.test_server_mcp import con_client

URL = "http://servizio.test"


def wrapper_finto(gestore):
    return crea_wrapper_scadenze(URL, http=httpx.Client(transport=httpx.MockTransport(gestore)))


def solleva(eccezione):
    def gestore(richiesta):
        raise eccezione
    return gestore


def test_contratto_identico_al_catalogo_mcp():
    (mcp,) = [s for s in con_client(lambda c: c.list_tools()) if s.name == "calcola_scadenza"]
    wrapper = convert_to_openai_tool(crea_wrapper_scadenze(URL))["function"]
    assert wrapper["name"] == mcp.name and wrapper["description"] == mcp.description
    assert wrapper["parameters"]["required"] == mcp.inputSchema["required"]
    assert wrapper["parameters"]["properties"] == mcp.inputSchema["properties"]


def test_origine_e_costanti():
    assert crea_wrapper_scadenze(URL).metadata == {"origine": "fastapi"} and ORIGINE_FASTAPI == "fastapi"
    assert TIMEOUT_HTTP == 5.0


# Il wrapper passa sempre `timeout`; il TestClient di Starlette lo accetta ma avvisa che lo ignora.
@pytest.mark.filterwarnings("ignore:You should not use the 'timeout' argument with the TestClient")
@pytest.mark.parametrize("data_inizio, giorni, lavorativi", [
    ("2026-12-23", 3, True), ("2026-12-23", 3, False), ("2026-02-30", 1, True), ("2028-12-29", 5, True),
    ("9999-12-31", 1, False),
])
def test_parita_con_la_variante_mcp(data_inizio, giorni, lavorativi):
    argomenti = {"data_inizio": data_inizio, "giorni": giorni, "lavorativi": lavorativi}
    wrapper = crea_wrapper_scadenze("http://testserver", http=TestClient(crea_app()))
    da_wrapper = json.loads(wrapper.invoke(argomenti))
    r = con_client(lambda c: c.call_tool("calcola_scadenza", argomenti, raise_on_error=False))
    if r.is_error:
        assert da_wrapper == {"errore": r.content[0].text, "tipo": "strumento"}
    else:
        assert da_wrapper == r.structured_content


def test_parametri_inviati():
    ricevute = []

    def gestore(richiesta):
        ricevute.append(richiesta)
        return httpx.Response(200, json={"scadenza": "2026-12-29"})

    wrapper_finto(gestore).invoke({"data_inizio": "2026-12-23", "giorni": 3, "lavorativi": True})
    (richiesta,) = ricevute
    assert richiesta.method == "GET" and richiesta.url.path == "/scadenza"
    assert dict(richiesta.url.params) == {"data_inizio": "2026-12-23", "giorni": "3", "lavorativi": "true"}


@pytest.mark.parametrize("gestore, tipo, frammento", [
    (lambda r: httpx.Response(400, json={"errore": "Data non valida: 'x'"}), "strumento", "Data non valida"),
    (lambda r: httpx.Response(503, text="giù"), "collegamento", "Servizio scadenze non raggiungibile"),
    (lambda r: httpx.Response(200, text="non json"), "collegamento", "Servizio scadenze non raggiungibile"),
    (lambda r: httpx.Response(400, text="non json"), "collegamento", "Servizio scadenze non raggiungibile"),
    (solleva(httpx.ConnectError("rifiutata")), "collegamento", "ConnectError: rifiutata"),
    (solleva(httpx.ReadTimeout("lento")), "collegamento", "nessuna risposta entro 5 secondi"),
])
def test_errori(gestore, tipo, frammento):
    risultato = json.loads(wrapper_finto(gestore).invoke({"data_inizio": "2026-12-23", "giorni": 3, "lavorativi": True}))
    assert risultato["tipo"] == tipo and frammento in risultato["errore"] and "scadenza" not in risultato


def test_servizio_spento_senza_eccezioni():
    risultato = json.loads(
        crea_wrapper_scadenze("http://127.0.0.1:9", timeout=0.5).invoke(
            {"data_inizio": "2026-12-23", "giorni": 3, "lavorativi": True}
        )
    )
    assert risultato["tipo"] == "collegamento"


def test_errore_interno_del_servizio_e_dello_strumento():
    errore = {"errore": "Errore interno dello strumento calcola_scadenza: RuntimeError."}
    risultato = json.loads(wrapper_finto(lambda r: httpx.Response(500, json=errore)).invoke(
        {"data_inizio": "2026-12-23", "giorni": 3, "lavorativi": True}))
    assert risultato == {**errore, "tipo": "strumento"}


@pytest.mark.parametrize("data_inizio", ["2026-12-23" + "x" * 70000, "2026-12-23\ud800"])
def test_argomenti_impossibili_da_inviare(data_inizio):
    risultato = json.loads(wrapper_finto(lambda r: httpx.Response(200, json={})).invoke(
        {"data_inizio": data_inizio, "giorni": 3, "lavorativi": True}))
    assert risultato["tipo"] == "strumento" and risultato["errore"].startswith("Argomenti non validi per calcola_scadenza")
