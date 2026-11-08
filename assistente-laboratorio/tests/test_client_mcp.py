import asyncio
import json

import pytest
from langchain_core.tools import StructuredTool, ToolException

from assistente.client_mcp import avvolgi

SCHEMA = {"type": "object", "properties": {"valore": {"type": "number"}}, "required": ["valore"]}


def finto(corpo, nome="converti_unita"):
    """Tool asincrono come quelli dell'adattatore MCP: niente invoke sincrono."""
    return StructuredTool(
        name=nome, description="desc", args_schema=SCHEMA, coroutine=corpo, response_format="content_and_artifact"
    )


def test_successo_e_contratto():
    async def ok(**argomenti):
        return [{"type": "text", "text": '{"risultato": 2500}'}], None

    ponte = avvolgi(finto(ok))
    assert (ponte.name, ponte.description, ponte.args_schema, ponte.metadata) == (
        "converti_unita", "desc", SCHEMA, {"origine": "mcp"}
    )
    assert json.loads(ponte.invoke({"valore": 2.5})) == {"risultato": 2500}


@pytest.mark.parametrize(
    "eccezione, tipo, frammento",
    [
        (ToolException("Unità sconosciuta: 'C'"), "strumento", "Unità sconosciuta: 'C'"),
        (
            ExceptionGroup("g", [ConnectionRefusedError("rifiutata")]),
            "collegamento",
            "Server MCP non raggiungibile: ConnectionRefusedError: rifiutata",
        ),
        (ExceptionGroup("g", [ExceptionGroup("h", [OSError()])]), "collegamento", "Server MCP non raggiungibile: OSError"),
    ],
)
def test_errori(eccezione, tipo, frammento):
    async def fallisce(**argomenti):
        raise eccezione

    risultato = json.loads(avvolgi(finto(fallisce)).invoke({"valore": 1}))
    assert risultato["tipo"] == tipo and frammento in risultato["errore"] and "risultato" not in risultato


def test_timeout():
    async def lento(**argomenti):
        await asyncio.sleep(5)

    risultato = json.loads(avvolgi(finto(lento), timeout=0.1).invoke({"valore": 1}))
    assert risultato == {"errore": "Server MCP: nessuna risposta entro 0.1 secondi.", "tipo": "collegamento"}
