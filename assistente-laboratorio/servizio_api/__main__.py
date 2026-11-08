"""Avvio del servizio FastAPI: python -m servizio_api --porta 8766"""

import argparse
import logging
import sys

import uvicorn

from servizio_api.app import crea_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Servizio FastAPI delle scadenze")
    parser.add_argument("--porta", type=int, required=True, help="porta locale su 127.0.0.1")
    argomenti = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stderr
    )
    registro = logging.getLogger("servizio_api")
    registro.info("avvio servizio porta=%d", argomenti.porta)
    try:
        uvicorn.run(crea_app(), host="127.0.0.1", port=argomenti.porta, log_level="warning", access_log=False)
    finally:
        registro.info("arresto servizio")


if __name__ == "__main__":
    main()
