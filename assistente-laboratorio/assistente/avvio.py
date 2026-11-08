"""Preparazione degli strumenti per una sessione: processi da avviare e selezione delle varianti.

Usato sia da `python -m assistente` sia dalle prove reali, così il percorso è lo stesso.
"""

import logging
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Iterator

from langchain_core.tools import BaseTool

from assistente.avvio_server import avvia_server_mcp
from assistente.configurazione import Configurazione
from assistente.registro import LOG_SERVER
from assistente.varianti import crea_sostituti, seleziona_strumenti

registro = logging.getLogger("assistente.avvio")


@contextmanager
def prepara_strumenti(config: Configurazione, log_server: Path | None = None) -> Iterator[list[BaseTool]]:
    """Avvia i processi necessari, seleziona gli strumenti e spegne tutto all'uscita."""
    with ExitStack() as pila:
        server = pila.enter_context(avvia_server_mcp(config.porta_mcp, log_server or LOG_SERVER))
        registro.info("varianti calcolatrice=%s", config.variante_calcolatrice)
        strumenti = seleziona_strumenti(server.strumenti, crea_sostituti(config))
        registro.info("strumenti al modello=%s", [s.name for s in strumenti])
        yield strumenti
