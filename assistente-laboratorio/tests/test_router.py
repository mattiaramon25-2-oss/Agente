import logging

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.ambito import Ambito
from assistente.router import MAX_MESSAGGI_ROUTER, DecisioneRouter, decidi, messaggi_router, prompt_router
from tests.finti import RouterFinto

AMBITO = Ambito(in_ambito=("meteo", "calcoli"), fuori_ambito=("poesie",), rifiuto="No.")


def test_prompt_costruito_dal_file():
    testo = prompt_router(AMBITO).content
    assert "meteo" in testo and "calcoli" in testo and "poesie" in testo
    assert "conversazione" in testo and "fuori_ambito" in testo
    assert "e a Roma?" in testo  # i seguiti brevi contano come conversazione
    assert "strumenti" in testo  # il router non valuta gli strumenti


def test_messaggi_visti_dal_router():
    cronologia = [HumanMessage(f"d{i}") if i % 2 == 0 else AIMessage(f"r{i}") for i in range(10)]
    cronologia.insert(5, ToolMessage("{}", tool_call_id="c1"))
    cronologia.insert(5, AIMessage("", tool_calls=[{"name": "x", "args": {}, "id": "c1", "type": "tool_call"}]))
    cronologia.append(HumanMessage("e a Roma?"))
    visti = messaggi_router(AMBITO, cronologia)
    assert isinstance(visti[0], SystemMessage)
    assert [m.content for m in visti[1:]] == ["r5", "d6", "r7", "d8", "r9", "e a Roma?"]
    assert len(visti) - 1 == MAX_MESSAGGI_ROUTER


@pytest.mark.parametrize("categoria", ["conversazione", "fuori_ambito"])
def test_decisione_registrata(caplog, categoria):
    router = RouterFinto([DecisioneRouter(categoria=categoria, motivo="perché sì")])
    with caplog.at_level(logging.INFO, logger="assistente"):
        assert decidi(router, AMBITO, [HumanMessage("ciao")]) == categoria
    assert f"nodo=router categoria={categoria} motivo=perché sì esito=ok" in caplog.text
    assert isinstance(router.chiamate[0][0], SystemMessage)


@pytest.mark.parametrize(
    "difetto", [ValueError("json non valido"), None, {"categoria": "boh"}, openai.BadRequestError(
        "response_format", response=httpx.Response(400, request=httpx.Request("POST", "http://x")), body=None)]
)
def test_router_difettoso_passa_all_agente(caplog, difetto):
    router = RouterFinto([difetto])
    with caplog.at_level(logging.INFO, logger="assistente"):
        assert decidi(router, AMBITO, [HumanMessage("ciao")]) == "conversazione"
    assert "nodo=router categoria=conversazione" in caplog.text and "esito=errore" in caplog.text


def test_errore_di_collegamento_propagato():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:1234/v1"))
    with pytest.raises(openai.APIConnectionError):
        decidi(RouterFinto([errore]), AMBITO, [HumanMessage("ciao")])


def test_decisione_accetta_anche_un_dizionario():
    router = RouterFinto([{"categoria": "fuori_ambito", "motivo": "poesia"}])
    assert decidi(router, AMBITO, [HumanMessage("poesia")]) == "fuori_ambito"


def test_il_router_non_va_in_streaming():
    """Con il tag `nostream` LangGraph non registra la risposta del router (niente avvisi di pydantic)."""
    router = RouterFinto([DecisioneRouter(categoria="conversazione", motivo="saluto")])
    decidi(router, AMBITO, [HumanMessage("ciao")])
    assert "nostream" in router.configurazioni[0]["tags"]
