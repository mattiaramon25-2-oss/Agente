import asyncio
import json
import logging
from datetime import datetime, timezone

from fastmcp import Client

from logica.conversioni import UNITA_AMMESSE
from server_mcp.server import (
    DESCRIZIONE_CALCOLATRICE,
    DESCRIZIONE_SCADENZE,
    NOME_CALCOLATRICE,
    NOME_CONVERTITORE,
    NOME_DETTAGLIO,
    NOME_OROLOGIO,
    NOME_RICERCA,
    NOME_SCADENZE,
    NOME_SERVER,
    crea_server,
)


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
    assert {s.name for s in strumenti} == {
        NOME_CONVERTITORE, NOME_OROLOGIO, NOME_CALCOLATRICE, NOME_SCADENZE, NOME_RICERCA, NOME_DETTAGLIO
    }
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


def test_calcola_nel_catalogo():
    (calcolatrice,) = [s for s in con_client(lambda c: c.list_tools()) if s.name == "calcola"]
    assert NOME_CALCOLATRICE == "calcola"
    assert calcolatrice.description == DESCRIZIONE_CALCOLATRICE == (
        "Calcola un'espressione aritmetica con numeri decimali (punto come separatore), + - * / % ** "
        'e parentesi. Esempio: espressione="(3 + 4) * 2".'
    )
    assert calcolatrice.inputSchema["required"] == ["espressione"]
    assert calcolatrice.inputSchema["properties"]["espressione"]["type"] == "string"


def test_calcola_via_mcp():
    r = con_client(lambda c: c.call_tool("calcola", {"espressione": "(3 + 4) * 2"}))
    assert r.structured_content == {"espressione": "(3 + 4) * 2", "risultato": 14}


def test_calcola_rifiuto_via_mcp():
    r = con_client(lambda c: c.call_tool("calcola", {"espressione": "__import__('os')"}, raise_on_error=False))
    assert r.is_error and "non consentit" in r.content[0].text


def test_scadenze_nel_catalogo():
    (scadenze,) = [s for s in con_client(lambda c: c.list_tools()) if s.name == "calcola_scadenza"]
    assert NOME_SCADENZE == "calcola_scadenza"
    assert scadenze.description == DESCRIZIONE_SCADENZE == (
        "Calcola la data di scadenza aggiungendo un numero di giorni a una data ISO (AAAA-MM-GG). "
        "Con lavorativi=true conta solo i giorni dal lunedì al venerdì esclusi i festivi nazionali italiani. "
        "Risultato indicativo, senza valore legale."
    )
    schema = scadenze.inputSchema
    assert schema["required"] == ["data_inizio", "giorni", "lavorativi"]
    assert [schema["properties"][n]["type"] for n in schema["required"]] == ["string", "integer", "boolean"]


def test_scadenza_via_mcp():
    r = con_client(lambda c: c.call_tool("calcola_scadenza", {"data_inizio": "2026-12-23", "giorni": 3, "lavorativi": True}))
    assert r.structured_content["scadenza"] == "2026-12-29"


def test_scadenza_errore_via_mcp():
    r = con_client(lambda c: c.call_tool(
        "calcola_scadenza", {"data_inizio": "2026-02-30", "giorni": 1, "lavorativi": True}, raise_on_error=False))
    assert r.is_error and "Data non valida" in r.content[0].text


def strumento_mcp(nome):
    return next(s for s in con_client(lambda c: c.list_tools()) if s.name == nome)


def test_catalogo_nel_catalogo_mcp():
    assert (NOME_RICERCA, NOME_DETTAGLIO) == ("search_catalog", "get_item")
    ricerca, dettaglio = strumento_mcp("search_catalog"), strumento_mcp("get_item")
    assert ricerca.inputSchema["required"] == ["query"]
    assert ricerca.inputSchema["properties"]["max_results"]["type"] == "integer"
    assert ricerca.inputSchema["properties"]["max_results"]["default"] == 5
    assert dettaglio.inputSchema["required"] == ["code"]
    assert ricerca.description != dettaglio.description
    assert "Cerca" in ricerca.description and "dettagli" in dettaglio.description


def test_ricerca_via_mcp():
    r = con_client(lambda c: c.call_tool("search_catalog", {"query": "python"}))
    assert r.structured_content["totale"] >= 2


def test_ricerca_con_max_results_via_mcp():
    r = con_client(lambda c: c.call_tool("search_catalog", {"query": "o", "max_results": 2}))
    assert len(r.structured_content["risultati"]) == 2


def test_dettaglio_inesistente_via_mcp():
    r = con_client(lambda c: c.call_tool("get_item", {"code": "XX-99"}, raise_on_error=False))
    assert r.is_error and "Usa prima search_catalog" in r.content[0].text
