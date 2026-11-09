"""Avvio del server MCP: python -m server_mcp --porta 8765"""

import argparse
import logging
import signal
import sys
from pathlib import Path

from server_mcp.server import crea_server


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
    parser = argparse.ArgumentParser(description="Server MCP degli strumenti del laboratorio")
    parser.add_argument("--porta", type=int, required=True, help="porta locale su 127.0.0.1")
    parser.add_argument("--note", type=Path, default=None, help="file SQLite delle note (predefinito: archivio/note.sqlite3)")
    argomenti = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stderr
    )
    registro = logging.getLogger("server_mcp")
    registro.info("avvio server porta=%d", argomenti.porta)
    _installa_segnali_di_arresto()
    try:
        opzioni = {"percorso_note": argomenti.note} if argomenti.note else {}
        crea_server(**opzioni).run(
            transport="http",
            host="127.0.0.1",
            port=argomenti.porta,
            path="/mcp",
            show_banner=False,
            stateless_http=True,
            json_response=True,
            log_level="warning",
        )
    except KeyboardInterrupt:
        pass  # arresto richiesto: uscita con codice 0
    finally:
        registro.info("arresto server")


if __name__ == "__main__":
    main()
