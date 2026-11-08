"""Variante locale della calcolatrice: una funzione Python registrata con @tool (slide 19).

Il contratto (nome, descrizione, schema) nasce dalla firma e dalla docstring; la logica è
quella di `logica.calcolatrice`, la stessa che usa il server MCP. Nessun processo in più:
la chiamata resta nel processo dell'agente e compare solo in logs/assistente.log.
"""

import json

from langchain_core.tools import BaseTool, tool

from assistente.client_mcp import TIPO_STRUMENTO
from logica.calcolatrice import calcola as calcola_logica
from logica.errori import ErroreStrumento

ORIGINE_LOCALE = "locale"


def crea_calcolatrice_locale() -> BaseTool:
    @tool
    def calcola(espressione: str) -> str:
        """Calcola un'espressione aritmetica con numeri decimali (punto come separatore), + - * / % ** e parentesi. Esempio: espressione="(3 + 4) * 2"."""  # noqa: E501
        try:
            return json.dumps(calcola_logica(espressione), ensure_ascii=False)
        except ErroreStrumento as errore:
            return json.dumps({"errore": str(errore), "tipo": TIPO_STRUMENTO}, ensure_ascii=False)

    calcola.metadata = {"origine": ORIGINE_LOCALE}
    return calcola
