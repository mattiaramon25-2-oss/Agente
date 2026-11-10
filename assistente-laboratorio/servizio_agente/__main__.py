"""Avvio del servizio dell'agente: python -m servizio_agente

Stesso percorso di `python -m assistente` (configurazione, LM Studio, server MCP, router), ma al posto
del terminale c'è un server HTTP su AGENTE_HOST:AGENTE_PORTA (predefinito 127.0.0.1). Ctrl+C ferma il servizio e i processi avviati.
"""

import logging
import os
import signal
import sys

import uvicorn
from dotenv import load_dotenv

from assistente.agente import crea_agente
from assistente.ambito import carica_ambito
from assistente.avvio import prepara_strumenti
from assistente.avvio_server import porta_libera
from assistente.configurazione import (
    ErroreConfigurazione,
    carica_configurazione,
    leggi_host_agente,
    leggi_porta_agente,
)
from assistente.console import configura_flussi
from assistente.errori import ErroreAvvio
from assistente.fuso import rileva_fuso
from assistente.modello import ErroreServer, verifica_server
from assistente.registro import LOG_ASSISTENTE, configura_registro
from assistente.varianti import origini, parametri
from servizio_agente.app import crea_app

registro = logging.getLogger("assistente.servizio")


def _arresto_su_segnale(numero, frame):
    raise KeyboardInterrupt


def _installa_segnali_di_arresto() -> None:
    # Come per servizio_api: SIGBREAK su Windows, SIGTERM in Docker/Linux, diventano un arresto ordinato.
    for nome in ("SIGBREAK", "SIGTERM"):
        if hasattr(signal, nome):
            signal.signal(getattr(signal, nome), _arresto_su_segnale)


def main() -> int:
    configura_flussi()
    try:
        load_dotenv(override=False)
        config = carica_configurazione(os.environ)
        porta = leggi_porta_agente(os.environ, config)
        host = leggi_host_agente(os.environ)
        configura_registro(LOG_ASSISTENTE)
        ambito = carica_ambito()
        if not porta_libera(porta):
            raise ErroreAvvio(f"La porta {porta} (AGENTE_PORTA) è occupata: scegli un'altra porta nel file .env.")
        verifica_server(config.base_url, config.modello)
        fuso = rileva_fuso(os.environ)
        _installa_segnali_di_arresto()
        with prepara_strumenti(config) as strumenti:
            grafo = crea_agente(config, strumenti, ambito)
            app = crea_app(
                grafo, fuso=fuso.fuso, modello=config.modello, origini=origini(strumenti), parametri=parametri(strumenti)
            )
            registro.info("avvio servizio agente host=%s porta=%d fuso=%s", host, porta, fuso.fuso)
            print(f"Servizio dell'agente in ascolto su {host}:{porta} (dall'host: http://127.0.0.1:{porta}, documentazione su /docs). Ctrl+C per fermarlo.")
            try:
                uvicorn.run(app, host=host, port=porta, log_level="warning", access_log=False)
            except KeyboardInterrupt:
                pass
            finally:
                registro.info("arresto servizio agente")
    except (ErroreConfigurazione, ErroreServer, ErroreAvvio) as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
