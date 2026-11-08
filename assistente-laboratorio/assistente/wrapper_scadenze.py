"""Variante FastAPI delle scadenze: wrapper HTTP registrato con @tool (slide 19).

Nome, descrizione e schema sono scritti qui, a mano: non c'è discovery. Se l'endpoint cambia,
il wrapper va aggiornato in ogni applicazione che lo usa. Il wrapper resta sottile: traduce
gli argomenti in parametri di query e la risposta HTTP (o il suo errore) in un risultato
per il grafo, senza mai sollevare eccezioni.
"""

import json
from typing import Annotated, Any

import httpx
from langchain_core.tools import BaseTool, tool
from pydantic import WithJsonSchema

from assistente.client_mcp import TIPO_COLLEGAMENTO, TIPO_STRUMENTO
from logica.scadenze import SCHEMA_DATA_INIZIO, SCHEMA_GIORNI, SCHEMA_LAVORATIVI

TIMEOUT_HTTP = 5.0
ORIGINE_FASTAPI = "fastapi"
PERCORSO = "/scadenza"


def _errore(testo: str, tipo: str) -> str:
    return json.dumps({"errore": testo, "tipo": tipo}, ensure_ascii=False)


def _parametro(valore: object) -> str:
    """Valore per la query: booleani come true/false, il resto come testo (lo valida il servizio)."""
    if isinstance(valore, bool):
        return "true" if valore else "false"
    return str(valore)


def crea_wrapper_scadenze(url_base: str, http: httpx.Client | None = None, timeout: float = TIMEOUT_HTTP) -> BaseTool:
    """Tool `calcola_scadenza` che chiama GET {url_base}/scadenza; `http` è iniettabile nei test."""

    def chiama(params: dict) -> httpx.Response:
        if http is not None:
            return http.get(url_base + PERCORSO, params=params, timeout=timeout)
        with httpx.Client() as client:
            return client.get(url_base + PERCORSO, params=params, timeout=timeout)

    # Schema degli argomenti uguale a quello del server MCP (stesse costanti di logica.scadenze).
    @tool
    def calcola_scadenza(
        data_inizio: Annotated[Any, WithJsonSchema(SCHEMA_DATA_INIZIO)],
        giorni: Annotated[Any, WithJsonSchema(SCHEMA_GIORNI)],
        lavorativi: Annotated[Any, WithJsonSchema(SCHEMA_LAVORATIVI)],
    ) -> str:
        """Calcola la data di scadenza aggiungendo un numero di giorni a una data ISO (AAAA-MM-GG). Con lavorativi=true conta solo i giorni dal lunedì al venerdì esclusi i festivi nazionali italiani. Risultato indicativo, senza valore legale."""  # noqa: E501
        params = {"data_inizio": _parametro(data_inizio), "giorni": _parametro(giorni), "lavorativi": _parametro(lavorativi)}
        try:
            risposta = chiama(params)
        except httpx.TimeoutException:
            return _errore(f"Servizio scadenze: nessuna risposta entro {timeout:g} secondi.", TIPO_COLLEGAMENTO)
        except httpx.HTTPError as errore:
            dettaglio = f"{type(errore).__name__}: {errore}" if str(errore) else type(errore).__name__
            return _errore(f"Servizio scadenze non raggiungibile: {dettaglio}", TIPO_COLLEGAMENTO)
        try:
            dati = risposta.json()
        except ValueError:
            dati = None
        if risposta.status_code == 200 and isinstance(dati, dict):
            return json.dumps(dati, ensure_ascii=False, separators=(",", ":"))
        if risposta.status_code == 400 and isinstance(dati, dict) and isinstance(dati.get("errore"), str):
            return _errore(dati["errore"], TIPO_STRUMENTO)
        return _errore(
            f"Servizio scadenze non raggiungibile: risposta non valida (HTTP {risposta.status_code}).", TIPO_COLLEGAMENTO
        )

    calcola_scadenza.metadata = {"origine": ORIGINE_FASTAPI}
    return calcola_scadenza
