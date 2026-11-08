"""Avvio del server MCP: python -m server_mcp --porta 8765"""

import argparse
import logging
import sys
from pathlib import Path

from server_mcp.server import crea_server


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
    finally:
        registro.info("arresto server")


if __name__ == "__main__":
    main()
