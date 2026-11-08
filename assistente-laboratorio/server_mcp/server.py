"""Registrazione MCP degli strumenti: la logica sta in `logica/`, qui solo contratto e log."""

import json
import logging
from datetime import datetime
from typing import Annotated, Any, Callable

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import WithJsonSchema

from logica.calcolatrice import SCHEMA_ESPRESSIONE, calcola
from logica.catalogo import (
    RISULTATI_PREDEFINITI,
    SCHEMA_CODE,
    SCHEMA_MAX_RESULTS,
    SCHEMA_QUERY,
    carica_catalogo,
    cerca,
    dettaglio,
)
from logica.conversioni import UNITA_AMMESSE, converti
from logica.errori import ErroreStrumento
from logica.orologio import ora_corrente, ora_utc
from logica.scadenze import SCHEMA_DATA_INIZIO, SCHEMA_GIORNI, SCHEMA_LAVORATIVI, calcola_scadenza

NOME_SERVER = "Strumenti laboratorio"
NOME_CONVERTITORE = "converti_unita"
NOME_OROLOGIO = "ora_corrente"
NOME_CALCOLATRICE = "calcola"
NOME_SCADENZE = "calcola_scadenza"
NOME_RICERCA = "search_catalog"
NOME_DETTAGLIO = "get_item"

DESCRIZIONE_CONVERTITORE = (
    "Converte un valore tra unità metriche della stessa grandezza (lunghezza, massa, volume) "
    'o tra gradi Celsius e Fahrenheit. Esempio: valore=2.5, da="km", a="m".'
)
DESCRIZIONE_OROLOGIO = (
    "Restituisce data e ora attuali nel fuso orario indicato. "
    '`fuso`: nome IANA, per esempio "Europe/Rome" o "Asia/Tokyo".'
)
# Identica alla docstring della variante locale (assistente/calcolatrice_locale.py): lo verifica un test.
DESCRIZIONE_CALCOLATRICE = (
    "Calcola un'espressione aritmetica con numeri decimali (punto come separatore), + - * / % ** "
    'e parentesi. Esempio: espressione="(3 + 4) * 2".'
)
# Identica alla docstring del wrapper FastAPI (assistente/wrapper_scadenze.py): lo verifica un test.
DESCRIZIONE_SCADENZE = (
    "Calcola la data di scadenza aggiungendo un numero di giorni a una data ISO (AAAA-MM-GG). "
    "Con lavorativi=true conta solo i giorni dal lunedì al venerdì esclusi i festivi nazionali italiani. "
    "Risultato indicativo, senza valore legale."
)

# Due strumenti sugli stessi dati: le descrizioni devono distinguersi (slide 28).
DESCRIZIONE_RICERCA = (
    "Cerca corsi nel catalogo dell'ITS per parola (titolo, sede o codice). Restituisce un elenco breve "
    "senza dettagli; per durata e dettagli usa get_item con il codice."
)
DESCRIZIONE_DETTAGLIO = (
    "Restituisce tutti i dettagli (titolo, sede, durata in ore) di un corso del catalogo dato il suo "
    "codice esatto, per esempio DLL-01."
)

registro = logging.getLogger("server_mcp")


def _json(valore: object) -> str:
    return json.dumps(valore, ensure_ascii=False, separators=(",", ":"))


def esegui_registrato(nome: str, argomenti: dict, calcolo: Callable[[], dict]) -> dict:
    """Esegue lo strumento, scrive una riga di log e trasforma ErroreStrumento in un errore MCP."""
    try:
        risultato = calcolo()
    except ErroreStrumento as errore:
        registro.info("chiamata tool=%s argomenti=%s esito=errore messaggio=%s", nome, _json(argomenti), errore)
        raise ToolError(str(errore)) from None
    registro.info("chiamata tool=%s argomenti=%s esito=ok risultato=%s", nome, _json(argomenti), _json(risultato))
    return risultato


def _unita(descrizione: str) -> Any:
    return Annotated[Any, WithJsonSchema({"type": "string", "enum": list(UNITA_AMMESSE), "description": descrizione})]


def crea_server(*, adesso: Callable[[], datetime] = ora_utc) -> FastMCP:
    """Crea il server MCP con tutti gli strumenti; `adesso` è iniettabile nei test."""
    server = FastMCP(NOME_SERVER)
    catalogo = carica_catalogo()

    @server.tool(name=NOME_CONVERTITORE, description=DESCRIZIONE_CONVERTITORE)
    def converti_unita(
        valore: Annotated[
            Any, WithJsonSchema({"type": "number", "description": "Numero da convertire, con il punto decimale (es. 2.5)"})
        ],
        da: _unita("Unità di partenza"),
        a: _unita("Unità di arrivo"),
    ) -> dict:
        return esegui_registrato(
            NOME_CONVERTITORE, {"valore": valore, "da": da, "a": a}, lambda: converti(valore, da, a)
        )

    @server.tool(name=NOME_OROLOGIO, description=DESCRIZIONE_OROLOGIO)
    def ora_corrente_mcp(
        fuso: Annotated[
            Any, WithJsonSchema({"type": "string", "description": "Nome IANA del fuso, per esempio Europe/Rome o Asia/Tokyo"})
        ],
    ) -> dict:
        return esegui_registrato(NOME_OROLOGIO, {"fuso": fuso}, lambda: ora_corrente(fuso, adesso()))

    @server.tool(name=NOME_CALCOLATRICE, description=DESCRIZIONE_CALCOLATRICE)
    def calcola_mcp(
        espressione: Annotated[Any, WithJsonSchema(SCHEMA_ESPRESSIONE)],
    ) -> dict:
        return esegui_registrato(NOME_CALCOLATRICE, {"espressione": espressione}, lambda: calcola(espressione))

    @server.tool(name=NOME_SCADENZE, description=DESCRIZIONE_SCADENZE)
    def calcola_scadenza_mcp(
        data_inizio: Annotated[Any, WithJsonSchema(SCHEMA_DATA_INIZIO)],
        giorni: Annotated[Any, WithJsonSchema(SCHEMA_GIORNI)],
        lavorativi: Annotated[Any, WithJsonSchema(SCHEMA_LAVORATIVI)],
    ) -> dict:
        argomenti = {"data_inizio": data_inizio, "giorni": giorni, "lavorativi": lavorativi}
        return esegui_registrato(NOME_SCADENZE, argomenti, lambda: calcola_scadenza(data_inizio, giorni, lavorativi))

    @server.tool(name=NOME_RICERCA, description=DESCRIZIONE_RICERCA)
    def search_catalog(
        query: Annotated[Any, WithJsonSchema(SCHEMA_QUERY)],
        max_results: Annotated[Any, WithJsonSchema(SCHEMA_MAX_RESULTS)] = RISULTATI_PREDEFINITI,
    ) -> dict:
        argomenti = {"query": query, "max_results": max_results}
        return esegui_registrato(NOME_RICERCA, argomenti, lambda: cerca(catalogo, query, max_results))

    @server.tool(name=NOME_DETTAGLIO, description=DESCRIZIONE_DETTAGLIO)
    def get_item(code: Annotated[Any, WithJsonSchema(SCHEMA_CODE)]) -> dict:
        return esegui_registrato(NOME_DETTAGLIO, {"code": code}, lambda: dettaglio(catalogo, code))

    return server
