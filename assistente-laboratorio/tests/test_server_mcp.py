import asyncio
import json
import logging
from datetime import datetime, timezone

from fastmcp import Client

from logica.conversioni import UNITA_AMMESSE
from server_mcp.server import NOME_CONVERTITORE, NOME_OROLOGIO, NOME_SERVER, crea_server


def con_client(funzione, **opzioni):
    """Esegue `funzione(client)` con un client MCP in memoria, senza rete."""

    async def corpo():
        async with Client(crea_server(**opzioni)) as client:
            return await funzione(client)

    return asyncio.run(corpo())


def test_nome_del_server():
    assert crea_server().name == NOME_SERVER == "Strumenti laboratorio"


def test_catalogo():
    strumenti = con_client(lambda c: c.list_tools())
    assert {s.name for s in strumenti} == {NOME_CONVERTITORE, NOME_OROLOGIO}
    (convertitore,) = [s for s in strumenti if s.name == NOME_CONVERTITORE]
    schema = convertitore.inputSchema
    assert schema["required"] == ["valore", "da", "a"]
    assert schema["properties"]["valore"]["type"] == "number"
    assert schema["properties"]["da"]["enum"] == list(UNITA_AMMESSE) == schema["properties"]["a"]["enum"]
    assert "Celsius" in convertitore.description


def test_chiamata_riuscita(caplog):
    caplog.set_level(logging.INFO, logger="server_mcp")
    r = con_client(lambda c: c.call_tool(NOME_CONVERTITORE, {"valore": 2.5, "da": "km", "a": "m"}))
    assert not r.is_error and r.structured_content["risultato"] == 2500
    assert json.loads(r.content[0].text)["grandezza"] == "lunghezza"
    assert "tool=converti_unita" in caplog.text and "esito=ok" in caplog.text


def test_errore_come_errore_mcp(caplog):
    caplog.set_level(logging.INFO, logger="server_mcp")
    r = con_client(lambda c: c.call_tool(NOME_CONVERTITORE, {"valore": 1, "da": "C", "a": "m"}, raise_on_error=False))
    assert r.is_error and "Unità sconosciuta" in r.content[0].text and r.structured_content is None
    assert "esito=errore" in caplog.text


def test_orologio_nel_catalogo():
    (orologio,) = [s for s in con_client(lambda c: c.list_tools()) if s.name == NOME_OROLOGIO]
    assert orologio.inputSchema["required"] == ["fuso"] and "IANA" in orologio.description


def test_orologio_risultato():
    istante = datetime(2026, 11, 2, 14, 4, 5, tzinfo=timezone.utc)
    r = con_client(lambda c: c.call_tool(NOME_OROLOGIO, {"fuso": "Asia/Tokyo"}), adesso=lambda: istante)
    assert r.structured_content == {
        "fuso": "Asia/Tokyo",
        "data_ora": "2026-11-02T23:04:05+09:00",
        "scarto_utc": "+09:00",
        "giorno_settimana": "lunedì",
    }


def test_orologio_fuso_sconosciuto(caplog):
    caplog.set_level(logging.INFO, logger="server_mcp")
    r = con_client(lambda c: c.call_tool(NOME_OROLOGIO, {"fuso": "Mars/Olympus"}, raise_on_error=False))
    assert r.is_error and "Fuso orario sconosciuto: 'Mars/Olympus'" in r.content[0].text
    assert "tool=ora_corrente" in caplog.text and "esito=errore" in caplog.text
