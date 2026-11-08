import asyncio
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import httpx
import pytest
from fastmcp import Client

from logica.conversioni import UNITA_AMMESSE
from server_mcp.server import (
    DESCRIZIONE_CALCOLATRICE,
    DESCRIZIONE_SCADENZE,
    NOME_CALCOLATRICE,
    NOME_AGGIUNGI_NOTA,
    NOME_CONVERTITORE,
    NOME_DETTAGLIO,
    NOME_ELENCA_NOTE,
    NOME_ELIMINA_NOTA,
    NOME_METEO,
    NOME_OROLOGIO,
    NOME_RICERCA,
    NOME_SCADENZE,
    NOME_SERVER,
    crea_server,
)


def http_senza_rete() -> httpx.Client:
    """Client HTTP per i test: qualsiasi richiesta fallisce, quindi nessun test usa la rete."""

    def vietato(richiesta):
        raise AssertionError(f"richiesta di rete nei test: {richiesta.url}")

    return httpx.Client(transport=httpx.MockTransport(vietato))


def con_client(funzione, **opzioni):
    """Esegue `funzione(client)` con un client MCP in memoria, senza rete.

    Se non viene indicato, l'archivio delle note è una cartella temporanea nuova:
    nessun test scrive nell'archivio reale.
    """
    opzioni.setdefault("percorso_note", Path(tempfile.mkdtemp()) / "note.sqlite3")
    opzioni.setdefault("http", http_senza_rete())

    async def corpo():
        async with Client(crea_server(**opzioni)) as client:
            return await funzione(client)

    return asyncio.run(corpo())


def test_nome_del_server():
    assert crea_server().name == NOME_SERVER == "Strumenti laboratorio"


def test_catalogo():
    strumenti = con_client(lambda c: c.list_tools())
    assert {s.name for s in strumenti} == {
        NOME_CONVERTITORE, NOME_OROLOGIO, NOME_CALCOLATRICE, NOME_SCADENZE, NOME_RICERCA, NOME_DETTAGLIO,
        NOME_AGGIUNGI_NOTA, NOME_ELENCA_NOTE, NOME_ELIMINA_NOTA, NOME_METEO,
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


def test_note_nel_catalogo():
    assert (NOME_AGGIUNGI_NOTA, NOME_ELENCA_NOTE, NOME_ELIMINA_NOTA) == ("add_note", "list_notes", "delete_note")
    aggiungi, elenca, elimina = (strumento_mcp(n) for n in ("add_note", "list_notes", "delete_note"))
    assert aggiungi.inputSchema["required"] == ["text"]
    assert elenca.inputSchema.get("required", []) == []
    assert elenca.inputSchema["properties"]["limit"]["default"] == 10
    assert elimina.inputSchema["required"] == ["note_id"] and "ID esatto" in elimina.description


def test_effetti_delle_note_via_mcp(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="server_mcp")
    archivio = tmp_path / "note.sqlite3"

    async def sequenza(c):
        creata = await c.call_tool("add_note", {"text": "consegnare il report"})
        elenco = await c.call_tool("list_notes", {})
        fallita = await c.call_tool("delete_note", {"note_id": 99}, raise_on_error=False)
        dopo_fallita = await c.call_tool("list_notes", {})
        eliminata = await c.call_tool("delete_note", {"note_id": 1})
        return creata, elenco, fallita, dopo_fallita, eliminata

    creata, elenco, fallita, dopo_fallita, eliminata = con_client(sequenza, percorso_note=archivio)
    assert creata.structured_content["id"] == 1
    assert [n["testo"] for n in elenco.structured_content["note"]] == ["consegnare il report"]
    assert fallita.is_error and "Nessuna nota con ID 99" in fallita.content[0].text
    assert dopo_fallita.structured_content["totale_archivio"] == 1
    assert eliminata.structured_content == {"id": 1, "testo": "consegnare il report", "esito": "nota eliminata"}
    assert "modifica note operazione=aggiunta id=1" in caplog.text
    assert caplog.text.count("operazione=eliminazione") == 1 and "operazione=eliminazione id=1" in caplog.text


def test_server_usa_il_percorso_indicato(tmp_path):
    from logica.note import PERCORSO_NOTE

    esisteva = PERCORSO_NOTE.exists()
    archivio = tmp_path / "note.sqlite3"
    con_client(lambda c: c.call_tool("add_note", {"text": "x"}), percorso_note=archivio)
    assert archivio.exists() and PERCORSO_NOTE.exists() == esisteva


def test_errore_imprevisto_registrato_e_in_italiano(caplog):
    """Rete di sicurezza: un'eccezione inattesa diventa un errore MCP in italiano e una riga di log."""
    from fastmcp.exceptions import ToolError

    from server_mcp.server import esegui_registrato

    caplog.set_level(logging.INFO, logger="server_mcp")

    def guasto():
        raise OverflowError("numero troppo grande")

    with pytest.raises(ToolError, match="Errore interno dello strumento prova: OverflowError"):
        esegui_registrato("prova", {"x": 1}, guasto)
    assert "tool=prova" in caplog.text and "esito=errore" in caplog.text


def test_id_enorme_via_mcp():
    r = con_client(lambda c: c.call_tool("delete_note", {"note_id": "99999999999999999999"}, raise_on_error=False))
    assert r.is_error and "niente è stato eliminato" in r.content[0].text


def test_regola_di_conferma_prima_di_eliminare():
    elimina = strumento_mcp("delete_note")
    assert "chiedi conferma" in elimina.description


def http_meteo(geo, forecast):
    """HTTP simulato per Open-Meteo: dict → JSON 200, eccezione → sollevata."""

    def gestore(richiesta):
        valore = geo if richiesta.url.host == "geocoding-api.open-meteo.com" else forecast
        if isinstance(valore, Exception):
            raise valore
        return httpx.Response(200, json=valore)

    return httpx.Client(transport=httpx.MockTransport(gestore))


UDINE = {"name": "Udine", "admin1": "Friuli Venezia Giulia", "country": "Italia", "latitude": 46.06, "longitude": 13.24}
CORRENTE = {"utc_offset_seconds": 3600, "current": {"time": "2026-11-08T10:15", "temperature_2m": 8.4,
                                                    "weather_code": 2, "wind_speed_10m": 12.0}}


def test_meteo_nel_catalogo():
    assert NOME_METEO == "get_weather"
    meteo = strumento_mcp("get_weather")
    assert meteo.inputSchema["required"] == ["city"] and "Open-Meteo" in meteo.description


def test_meteo_via_mcp():
    r = con_client(lambda c: c.call_tool("get_weather", {"city": "Udine"}),
                   http=http_meteo({"results": [UDINE]}, CORRENTE))
    assert r.structured_content["citta"]["nome"] == "Udine" and r.structured_content["temperatura"]["valore"] == 8.4


@pytest.mark.parametrize("geo, frammento", [
    ({"generationtime_ms": 0.1}, "Città non trovata"),
    (httpx.ConnectError("no rete"), "non disponibile"),
])
def test_meteo_errori_via_mcp(caplog, geo, frammento):
    caplog.set_level(logging.INFO, logger="server_mcp")
    r = con_client(lambda c: c.call_tool("get_weather", {"city": "Udine"}, raise_on_error=False),
                   http=http_meteo(geo, CORRENTE))
    assert r.is_error and frammento in r.content[0].text
    assert "tool=get_weather" in caplog.text and "esito=errore" in caplog.text
