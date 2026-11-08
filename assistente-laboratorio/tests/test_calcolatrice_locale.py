"""Variante locale della calcolatrice: stesso contratto e stessi esiti della variante MCP."""

import json

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente.calcolatrice_locale import crea_calcolatrice_locale
from tests.test_server_mcp import con_client


def test_contratto_identico():
    (mcp,) = [s for s in con_client(lambda c: c.list_tools()) if s.name == "calcola"]
    locale = crea_calcolatrice_locale()
    schema = locale.tool_call_schema.model_json_schema()
    assert locale.name == mcp.name and locale.description == mcp.description
    assert schema["required"] == mcp.inputSchema["required"] == ["espressione"]
    assert schema["properties"]["espressione"]["type"] == mcp.inputSchema["properties"]["espressione"]["type"] == "string"


@pytest.mark.parametrize("espressione", ["(3 + 4) * 2", "0.1 + 0.2", "1 / 0", "__import__('os')", "2,5"])
def test_stesso_esito_delle_due_varianti(espressione):
    locale = json.loads(crea_calcolatrice_locale().invoke({"espressione": espressione}))
    r = con_client(lambda c: c.call_tool("calcola", {"espressione": espressione}, raise_on_error=False))
    if r.is_error:
        assert locale == {"errore": r.content[0].text, "tipo": "strumento"}
    else:
        assert locale == r.structured_content


def test_origine_locale():
    assert crea_calcolatrice_locale().metadata == {"origine": "locale"}


def test_schema_identico_a_quello_mcp():
    """Il modello deve ricevere lo stesso contratto: nome, descrizione e schema di ogni argomento."""
    (mcp,) = [s for s in con_client(lambda c: c.list_tools()) if s.name == "calcola"]
    locale = convert_to_openai_tool(crea_calcolatrice_locale())["function"]
    assert locale["name"] == mcp.name and locale["description"] == mcp.description
    assert locale["parameters"]["required"] == mcp.inputSchema["required"]
    assert locale["parameters"]["properties"] == mcp.inputSchema["properties"]


@pytest.mark.parametrize("espressione", [14, None, ["1+1"]])
def test_tipo_sbagliato_stesso_errore_italiano(espressione):
    locale = json.loads(crea_calcolatrice_locale().invoke({"espressione": espressione}))
    r = con_client(lambda c: c.call_tool("calcola", {"espressione": espressione}, raise_on_error=False))
    assert r.is_error and locale == {"errore": r.content[0].text, "tipo": "strumento"}
    assert "testo" in locale["errore"]
