"""Applicazione FastAPI: espone `calcola_scadenza` come GET /scadenza.

La logica è quella di `logica.scadenze`, la stessa del server MCP. FastAPI genera da qui
la descrizione OpenAPI (/openapi.json) e la pagina interattiva (/docs). Gli errori sono
sempre `400` con {"errore": "..."} in italiano: anche quelli di validazione, che FastAPI
darebbe come `422` in inglese.
"""

import json
import logging

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from logica.errori import ErroreStrumento
from logica.scadenze import SCHEMA_DATA_INIZIO, SCHEMA_GIORNI, SCHEMA_LAVORATIVI, calcola_scadenza

TITOLO = "Servizio scadenze"
ENDPOINT = "/scadenza"
NOME_STRUMENTO = "calcola_scadenza"

registro = logging.getLogger("servizio_api")


def _json(valore: object) -> str:
    return json.dumps(valore, ensure_ascii=False, separators=(",", ":"))


def _errore(argomenti: dict, messaggio: str) -> JSONResponse:
    registro.info("richiesta endpoint=%s argomenti=%s esito=errore messaggio=%s", ENDPOINT, _json(argomenti), messaggio)
    return JSONResponse(status_code=400, content={"errore": messaggio})


def crea_app() -> FastAPI:
    app = FastAPI(title=TITOLO, description="Variante FastAPI dello strumento calcola_scadenza.")

    @app.exception_handler(RequestValidationError)
    async def validazione_in_italiano(richiesta: Request, eccezione: RequestValidationError) -> JSONResponse:
        dettagli = []
        for errore in eccezione.errors():
            nome = errore.get("loc", ("?",))[-1]
            dettagli.append(f"{nome}: mancante" if errore.get("type") == "missing" else f"{nome}: valore non valido")
        messaggio = f"Argomenti non validi per {NOME_STRUMENTO}: " + "; ".join(dettagli)
        return _errore(dict(richiesta.query_params), messaggio)

    @app.get(ENDPOINT, summary="Calcola una data di scadenza")
    def scadenza(
        data_inizio: str = Query(description=SCHEMA_DATA_INIZIO["description"]),
        giorni: int = Query(description=SCHEMA_GIORNI["description"]),
        lavorativi: bool = Query(description=SCHEMA_LAVORATIVI["description"]),
    ):
        argomenti = {"data_inizio": data_inizio, "giorni": giorni, "lavorativi": lavorativi}
        try:
            risultato = calcola_scadenza(data_inizio, giorni, lavorativi)
        except ErroreStrumento as errore:
            return _errore(argomenti, str(errore))
        registro.info(
            "richiesta endpoint=%s argomenti=%s esito=ok risultato=%s", ENDPOINT, _json(argomenti), _json(risultato)
        )
        return risultato

    return app
