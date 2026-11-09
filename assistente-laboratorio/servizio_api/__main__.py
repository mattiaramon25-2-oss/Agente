"""Avvio del servizio FastAPI: python -m servizio_api --porta 8766"""

import argparse
import logging
import signal
import sys

import uvicorn

from servizio_api.app import crea_app


def _arresto_su_segnale(numero, frame):
    """Uvicorn chiude in modo ordinato e poi rilancia il segnale ricevuto: qui diventa un'uscita normale."""
    raise KeyboardInterrupt


def _installa_segnali_di_arresto() -> None:
    # SIGBREAK: CTRL_BREAK_EVENT inviato dall'assistente su Windows; SIGTERM: arresto in Docker/Linux.
    # Senza questo gestore il processo uscirebbe con codice 3 senza eseguire il blocco finally.
    for nome in ("SIGBREAK", "SIGTERM"):
        if hasattr(signal, nome):
            signal.signal(getattr(signal, nome), _arresto_su_segnale)


def main() -> None:
    parser = argparse.ArgumentParser(description="Servizio FastAPI delle scadenze")
    parser.add_argument("--porta", type=int, required=True, help="porta locale su 127.0.0.1")
    argomenti = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stderr
    )
    registro = logging.getLogger("servizio_api")
    registro.info("avvio servizio porta=%d", argomenti.porta)
    _installa_segnali_di_arresto()
    try:
        uvicorn.run(crea_app(), host="127.0.0.1", port=argomenti.porta, log_level="warning", access_log=False)
    except KeyboardInterrupt:
        pass  # arresto richiesto: uscita con codice 0
    finally:
        registro.info("arresto servizio")


if __name__ == "__main__":
    main()
