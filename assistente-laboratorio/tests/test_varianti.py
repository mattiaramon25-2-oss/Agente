import pytest
from langchain_core.tools import StructuredTool

from assistente.errori import ErroreAvvio
from assistente.varianti import origini, seleziona_strumenti


def tool(nome, origine=None):
    metadati = {"origine": origine} if origine else None
    return StructuredTool.from_function(lambda: "", name=nome, description="d", metadata=metadati)


def test_senza_sostituti():
    remoti = [tool("ora_corrente", "mcp"), tool("converti_unita", "mcp")]
    assert seleziona_strumenti(remoti) == remoti


def test_sostituto_prende_il_posto_della_versione_mcp():
    scelti = seleziona_strumenti([tool("calcola", "mcp"), tool("ora_corrente", "mcp")], [tool("calcola", "locale")])
    assert origini(scelti) == {"ora_corrente": "mcp", "calcola": "locale"} and len(scelti) == 2


def test_nomi_duplicati():
    with pytest.raises(ErroreAvvio, match="ora_corrente"):
        seleziona_strumenti([tool("ora_corrente", "mcp"), tool("ora_corrente", "mcp")])


def test_origine_mancante_vale_locale():
    assert origini([tool("x")]) == {"x": "locale"}
