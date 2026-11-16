"""Avvio della chat nel browser: python -m avvio_chat (oppure doppio clic su avvia-chat.cmd).

Accende ciò che manca (Docker Desktop, il server di LM Studio, i quattro container: database,
agente, back-end e pagina), aspetta che la chat risponda attraverso nginx, apre il browser e resta
in attesa. Scrivendo «esci», con Ctrl+C, a fine input o chiudendo la finestra ferma con
`docker compose stop` solo l'agente e il back-end che ha acceso lui; database e pagina restano accesi.
Il browser, Docker Desktop e LM Studio restano accesi.

Usa solo la libreria standard e python-dotenv: niente psycopg, langchain o httpx, che su Windows
Smart App Control può bloccare. Con --ricostruisci le immagini si ricostruiscono (dopo un aggiornamento).
"""

import argparse
import os
import sys
from typing import TextIO

from dotenv import dotenv_values

from assistente.configurazione import ErroreConfigurazione
from assistente.console import configura_flussi
from assistente.errori import ErroreAvvio
from assistente.lmstudio import ErroreServer
from avvio_chat.passi import CARTELLA_PROGETTO, avvia_chat, carica_impostazioni


def scrivi(testo: str) -> None:
    """Una riga nella finestra, subito visibile."""
    print(testo, flush=True)


def leggi_ambiente() -> dict[str, str]:
    """Le variabili del .env, con la precedenza a quelle già impostate nell'ambiente.

    Il .env si legge senza copiarlo in os.environ: così la password del database non passa ai
    programmi che questo avvia e che restano accesi (Docker Desktop, LM Studio, il browser).
    Docker Compose il .env lo legge da solo e lo passa ai container.
    """
    dal_file = {nome: valore for nome, valore in dotenv_values(CARTELLA_PROGETTO / ".env").items() if valore is not None}
    return {**dal_file, **os.environ}


def main(argomenti: list[str] | None = None, ingresso: TextIO | None = None) -> int:
    configura_flussi()
    parser = argparse.ArgumentParser(
        prog="python -m avvio_chat", description="Accende ciò che serve e apre la chat nel browser."
    )
    parser.add_argument("--senza-browser", action="store_true", help="fa tutto tranne aprire il browser")
    parser.add_argument(
        "--ricostruisci", action="store_true", help="ricostruisce le immagini dei container (dopo un aggiornamento del codice)"
    )
    opzioni = parser.parse_args(argomenti)
    try:
        impostazioni = carica_impostazioni(leggi_ambiente())
        return avvia_chat(
            impostazioni,
            ingresso if ingresso is not None else sys.stdin,
            scrivi,
            senza_browser=opzioni.senza_browser,
            ricostruisci=opzioni.ricostruisci,
        )
    except (ErroreConfigurazione, ErroreServer, ErroreAvvio) as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrotto.")
        return 0
    except Exception as errore:  # niente traceback nella finestra: una riga che dice che cosa è successo
        print(f"Errore inatteso: {errore}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
