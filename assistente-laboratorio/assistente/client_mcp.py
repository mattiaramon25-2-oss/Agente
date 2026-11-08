"""Client MCP: discovery del catalogo e ponte sincrono verso i tool (unico punto asincrono).

I tool di langchain-mcp-adapters sono solo asincroni; il grafo è sincrono. Ogni tool scoperto
viene avvolto in un tool sincrono con lo stesso nome, descrizione e schema, che non solleva
mai eccezioni verso il grafo: restituisce sempre una stringa (risultato o errore JSON).
"""

import asyncio
import json
import logging

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient

NOME_CONNESSIONE = "laboratorio"
TIMEOUT_CHIAMATA = 10.0
TIPO_STRUMENTO = "strumento"
TIPO_COLLEGAMENTO = "collegamento"
ORIGINE_MCP = "mcp"

# Le librerie client non devono scrivere nel terminale della chat.
for _nome in ("mcp", "httpx", "httpcore"):
    logging.getLogger(_nome).setLevel(logging.ERROR)


def _errore(testo: str, tipo: str) -> str:
    return json.dumps({"errore": testo, "tipo": tipo}, ensure_ascii=False)


def _prima_causa(eccezione: BaseException) -> BaseException:
    while isinstance(eccezione, BaseExceptionGroup) and eccezione.exceptions:
        eccezione = eccezione.exceptions[0]
    return eccezione


def _descrivi(eccezione: BaseException) -> str:
    messaggio = str(eccezione)
    tipo = type(eccezione).__name__
    return f"{tipo}: {messaggio}" if messaggio else tipo


def _testo(contenuto: object) -> str:
    """Concatena i blocchi di testo restituiti dall'adattatore."""
    if isinstance(contenuto, str):
        return contenuto
    if isinstance(contenuto, tuple):  # (contenuto, artefatto)
        return _testo(contenuto[0])
    parti = []
    for blocco in contenuto or []:
        if isinstance(blocco, str):
            parti.append(blocco)
        elif isinstance(blocco, dict) and blocco.get("type") == "text":
            parti.append(blocco.get("text", ""))
    return "".join(parti)


def avvolgi(strumento: BaseTool, timeout: float = TIMEOUT_CHIAMATA) -> BaseTool:
    """Tool sincrono equivalente a `strumento` (asincrono), con `metadata={"origine": "mcp"}`."""

    def esegui(**argomenti) -> str:
        try:
            contenuto = asyncio.run(asyncio.wait_for(strumento.ainvoke(argomenti), timeout))
        except ToolException as errore:
            return _errore(str(errore), TIPO_STRUMENTO)
        except TimeoutError:
            return _errore(f"Server MCP: nessuna risposta entro {timeout:g} secondi.", TIPO_COLLEGAMENTO)
        except Exception as errore:  # anche ExceptionGroup del trasporto
            return _errore(f"Server MCP non raggiungibile: {_descrivi(_prima_causa(errore))}", TIPO_COLLEGAMENTO)
        return _testo(contenuto)

    return StructuredTool(
        name=strumento.name,
        description=strumento.description,
        args_schema=strumento.args_schema,
        func=esegui,
        metadata={"origine": ORIGINE_MCP},
    )


def scopri_strumenti(url: str, timeout_scoperta: float = TIMEOUT_CHIAMATA) -> list[BaseTool]:
    """Discovery (tools/list) sul server all'indirizzo `url`; le eccezioni le gestisce il chiamante."""
    client = MultiServerMCPClient(
        {NOME_CONNESSIONE: {"transport": "streamable_http", "url": url, "timeout": TIMEOUT_CHIAMATA}},
        handle_tool_errors=False,
    )
    strumenti = asyncio.run(asyncio.wait_for(client.get_tools(), timeout_scoperta))
    return [avvolgi(strumento) for strumento in strumenti]
