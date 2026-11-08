"""Strumenti che il modello può chiedere di eseguire: per ora solo l'orologio.

La logica sta in `logica.orologio`; questo modulo sparisce quando l'orologio passa al server MCP.
"""

import json
from datetime import datetime
from typing import Callable

from langchain_core.tools import BaseTool, StructuredTool

from logica.errori import ErroreStrumento
from logica.orologio import ora_corrente as _ora_corrente
from logica.orologio import ora_utc, è_fuso_valido  # noqa: F401 (riesportato per i test esistenti)

NOME_OROLOGIO = "ora_corrente"

DESCRIZIONE_OROLOGIO = (
    "Restituisce data e ora attuali nel fuso orario indicato. "
    '`fuso`: nome IANA, per esempio "Europe/Rome" o "Asia/Tokyo".'
)


def crea_strumento_orologio(adesso: Callable[[], datetime] = ora_utc) -> BaseTool:
    """Crea lo strumento `ora_corrente`; `adesso` fornisce l'istante (iniettabile nei test)."""

    def ora_corrente(fuso: str) -> str:
        try:
            risultato = _ora_corrente(fuso, adesso())
        except ErroreStrumento as errore:
            return json.dumps({"errore": str(errore)}, ensure_ascii=False)
        return json.dumps(risultato, ensure_ascii=False)

    return StructuredTool.from_function(
        func=ora_corrente, name=NOME_OROLOGIO, description=DESCRIZIONE_OROLOGIO
    )
