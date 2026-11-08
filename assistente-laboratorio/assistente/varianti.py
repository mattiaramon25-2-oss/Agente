"""Selezione degli strumenti passati al modello: una sola versione per nome.

Il server MCP espone sempre tutto; l'agente, come host, sceglie le capacità consentite
(slide 11). Un sostituto (variante locale o FastAPI) prende il posto della versione MCP.
"""

from typing import Sequence

from langchain_core.tools import BaseTool

from assistente.calcolatrice_locale import crea_calcolatrice_locale
from assistente.configurazione import Configurazione
from assistente.errori import ErroreAvvio


def crea_sostituti(config: Configurazione) -> list[BaseTool]:
    """Versioni non MCP richieste dal .env; ciascuna prende il posto dello strumento MCP omonimo."""
    sostituti: list[BaseTool] = []
    if config.variante_calcolatrice == "locale":
        sostituti.append(crea_calcolatrice_locale())
    return sostituti


def seleziona_strumenti(remoti: list[BaseTool], sostituti: Sequence[BaseTool] = ()) -> list[BaseTool]:
    nomi_sostituti = {s.name for s in sostituti}
    scelti = [s for s in remoti if s.name not in nomi_sostituti] + list(sostituti)
    visti: set[str] = set()
    for strumento in scelti:
        if strumento.name in visti:
            raise ErroreAvvio(
                f"Strumento '{strumento.name}' presente due volte: "
                "ogni strumento deve arrivare al modello da una sola variante."
            )
        visti.add(strumento.name)
    return scelti


def parametri(strumenti: Sequence[BaseTool]) -> dict[str, list[str]]:
    """Da nome dello strumento ai nomi dei suoi argomenti, nell'ordine dello schema."""
    return {s.name: list(s.args) for s in strumenti}


def origini(strumenti: Sequence[BaseTool]) -> dict[str, str]:
    """Da nome dello strumento a origine (`mcp`, `locale`, `fastapi`); `locale` se manca."""
    return {s.name: (s.metadata or {}).get("origine", "locale") for s in strumenti}
