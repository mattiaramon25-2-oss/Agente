"""Collegamento al modello servito da LM Studio (API compatibile con OpenAI)."""

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistente.configurazione import Configurazione
from assistente.lmstudio import ErroreServer, _controlla_indirizzo, _leggi_json_http, verifica_server  # noqa: F401

# LM Studio non controlla la chiave, ma la libreria ne esige una: è un segnaposto, non una credenziale.
CHIAVE_SEGNAPOSTO = "lm-studio"


def crea_modello(config: Configurazione, strumenti: list[BaseTool]):
    chat = ChatOpenAI(
        model=config.modello,
        base_url=config.base_url,
        api_key=CHIAVE_SEGNAPOSTO,
        timeout=120,
        max_retries=1,
    )
    return chat.bind_tools(strumenti)


def crea_router(config: Configurazione):
    """Lo stesso modello, senza strumenti, con output strutturato (categoria e motivo)."""
    from assistente.router import DecisioneRouter

    chat = ChatOpenAI(
        model=config.modello,
        base_url=config.base_url,
        api_key=CHIAVE_SEGNAPOSTO,
        timeout=120,
        max_retries=1,
        disable_streaming=True,  # anche quando il grafo è in streaming: la risposta è JSON per il programma
    )
    return chat.with_structured_output(DecisioneRouter, method="json_schema")
