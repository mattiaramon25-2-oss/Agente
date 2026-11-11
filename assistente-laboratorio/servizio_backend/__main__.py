"""Avvio del back-end delle chat: python -m servizio_backend

Legge il .env, si collega a PostgreSQL (crea le tabelle se mancano), controlla l'agente e serve
l'API HTTP su 127.0.0.1:BACKEND_PORTA. Ctrl+C, SIGTERM e SIGBREAK lo fermano in modo ordinato.
"""

import logging
import os
import signal
import sys

import uvicorn
from dotenv import load_dotenv

from assistente.avvio_server import porta_libera
from assistente.configurazione import ErroreConfigurazione
from assistente.console import configura_flussi
from assistente.errori import ErroreAvvio
from assistente.registro import LOG_BACKEND, configura_registro
from servizio_backend.app import crea_app
from servizio_backend.archivio import ArchivioPostgres, DatabaseNonRaggiungibile
from servizio_backend.client_agente import ClientAgente
from servizio_backend.configurazione import carica_configurazione_backend

registro = logging.getLogger("servizio_backend")


def _arresto_su_segnale(numero, frame):
    raise KeyboardInterrupt


def _installa_segnali_di_arresto() -> None:
    # SIGBREAK su Windows, SIGTERM in Docker/Linux, diventano un arresto ordinato.
    for nome in ("SIGBREAK", "SIGTERM"):
        if hasattr(signal, nome):
            signal.signal(getattr(signal, nome), _arresto_su_segnale)


def main() -> int:
    configura_flussi()
    try:
        load_dotenv(override=False)
        config = carica_configurazione_backend(os.environ)
        configura_registro(LOG_BACKEND, nome="servizio_backend")
        if not porta_libera(config.porta):
            raise ErroreAvvio(f"La porta {config.porta} (BACKEND_PORTA) è occupata: scegli un'altra porta nel file .env.")
        archivio = ArchivioPostgres(config.dsn)
        try:
            archivio.controlla()
            archivio.prepara()
        except DatabaseNonRaggiungibile as errore:
            registro.error("avvio fallito: database non raggiungibile: %s", errore)
            raise ErroreAvvio(
                f"Il database PostgreSQL non risponde su 127.0.0.1:{config.porta_postgres} ({errore}): "
                "avvialo con docker compose up -d database; se è acceso, "
                "controlla POSTGRES_USER, POSTGRES_PASSWORD e POSTGRES_DB nel file .env."
            ) from errore
        agente = ClientAgente(config.url_agente)
        if not agente.salute():
            print(
                f"Attenzione: l'agente non risponde su {config.url_agente}. "
                "Avvialo con python -m servizio_agente; il back-end intanto parte."
            )
        _installa_segnali_di_arresto()
        app = crea_app(archivio, agente)
        registro.info("avvio servizio backend porta=%d", config.porta)
        print(f"Back-end delle chat in ascolto su http://127.0.0.1:{config.porta} (documentazione su /docs). Ctrl+C per fermarlo.")
        try:
            uvicorn.run(app, host="127.0.0.1", port=config.porta, log_level="warning", access_log=False)
        except KeyboardInterrupt:
            pass
        finally:
            registro.info("arresto servizio backend")
    except (ErroreConfigurazione, ErroreAvvio) as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
