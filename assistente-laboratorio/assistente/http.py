"""Pezzi HTTP comuni ai servizi FastAPI: JSON con charset e messaggio di validazione in italiano."""

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class RispostaJson(JSONResponse):
    """JSON con il charset dichiarato: Invoke-RestMethod di PowerShell 5.1 altrimenti legge in Latin-1."""

    media_type = "application/json; charset=utf-8"


def messaggio_validazione(eccezione: RequestValidationError) -> str:
    """«Richiesta non valida: campo: motivo; ...» senza mai riportare i valori ricevuti."""
    dettagli = []
    for errore in eccezione.errors():
        nome = ".".join(str(parte) for parte in errore.get("loc", ("?",))[1:]) or "corpo"
        dettagli.append(f"{nome}: mancante" if errore.get("type") == "missing" else f"{nome}: valore non valido")
    return "Richiesta non valida: " + "; ".join(dettagli)
