"""Preparazione degli strumenti per una sessione: processi da avviare e selezione delle varianti.

Usato sia da `python -m assistente` sia dalle prove reali, così il percorso è lo stesso.
"""

import logging
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Iterator

from langchain_core.tools import BaseTool

from assistente.avvio_server import avvia_server_mcp, avvia_servizio_api
from assistente.configurazione import Configurazione
from assistente.registro import LOG_API, LOG_SERVER
from assistente.varianti import crea_sostituti, seleziona_strumenti

registro = logging.getLogger("assistente.avvio")


@contextmanager
def prepara_strumenti(
    config: Configurazione, log_server: Path | None = None, log_api: Path | None = None
) -> Iterator[list[BaseTool]]:
    """Avvia i processi necessari, seleziona gli strumenti e spegne tutto all'uscita.

    Se un processo non parte, l'ExitStack spegne anche quelli già avviati.
    """
    with ExitStack() as pila:
        server = pila.enter_context(avvia_server_mcp(config.porta_mcp, log_server or LOG_SERVER))
        url_api = None
        if config.variante_scadenze == "fastapi":
            servizio = pila.enter_context(avvia_servizio_api(config.porta_api, log_api or LOG_API))
            url_api = servizio.url
        registro.info(
            "varianti calcolatrice=%s scadenze=%s", config.variante_calcolatrice, config.variante_scadenze
        )
        strumenti = seleziona_strumenti(server.strumenti, crea_sostituti(config, url_api=url_api))
        registro.info("strumenti al modello=%s", [s.name for s in strumenti])
        yield strumenti
