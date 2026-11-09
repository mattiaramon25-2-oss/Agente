"""Costruzione dell'agente: la stessa per la CLI, per il servizio HTTP e per le prove reali."""

from langchain_core.tools import BaseTool

from assistente.ambito import Ambito
from assistente.configurazione import Configurazione
from assistente.grafo import crea_grafo
from assistente.modello import crea_modello, crea_router


def crea_agente(config: Configurazione, strumenti: list[BaseTool], ambito: Ambito):
    """Grafo con router e rifiuto davanti all'agente, modello di LM Studio collegato agli strumenti."""
    return crea_grafo(crea_modello(config, strumenti), strumenti, crea_router(config), ambito)
