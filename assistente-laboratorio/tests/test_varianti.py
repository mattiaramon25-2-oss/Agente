import pytest
from langchain_core.tools import StructuredTool

from assistente.errori import ErroreAvvio
from assistente.configurazione import Configurazione
from assistente.varianti import crea_sostituti, origini, parametri, seleziona_strumenti


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


def test_parametri_nell_ordine_dello_schema():
    schema = {"type": "object", "properties": {"valore": {}, "da": {}, "a": {}}, "required": ["valore", "da", "a"]}
    mcp = StructuredTool(name="converti_unita", description="d", args_schema=schema, func=lambda **k: "")
    assert parametri([mcp, tool("x")]) == {"converti_unita": ["valore", "da", "a"], "x": []}


def test_sostituti_della_calcolatrice():
    assert crea_sostituti(Configurazione("u", "m", 8765, variante_calcolatrice="mcp")) == []
    (locale,) = crea_sostituti(Configurazione("u", "m", 8765, variante_calcolatrice="locale"))
    assert origini([locale]) == {"calcola": "locale"}
