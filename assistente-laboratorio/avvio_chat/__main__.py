"""Avvio della chat nel browser: python -m avvio_chat (oppure doppio clic su avvia-chat.cmd).

Accende ciò che manca (Docker Desktop, il server di LM Studio, i container del database e della
pagina, il servizio dell'agente e il back-end), apre la chat nel browser e resta in attesa.
Scrivendo «esci», con Ctrl+C o a fine input spegne ciò che ha avviato; i container restano accesi.

Se la finestra viene chiusa senza «esci», Windows avvisa i processi attaccati alla console e li
chiude: l'agente e il back-end lo sono, perché li avvia questo programma nella stessa finestra.
Il browser, Docker Desktop e LM Studio no, e restano accesi.
"""

import argparse
import os
import sys
from typing import TextIO

from dotenv import dotenv_values

from assistente.avvio_server import CARTELLA_PROGETTO
from assistente.configurazione import ErroreConfigurazione
from assistente.console import configura_flussi
from assistente.errori import ErroreAvvio
from assistente.modello import ErroreServer
from avvio_chat.passi import avvia_chat, carica_impostazioni


def scrivi(testo: str) -> None:
    """Una riga nella finestra, subito visibile."""
    print(testo, flush=True)


def leggi_ambiente() -> dict[str, str]:
    """Le variabili del .env, con la precedenza a quelle già impostate nell'ambiente.

    Il .env si legge senza copiarlo in os.environ: così la password del database non passa ai
    programmi che questo avvia e che restano accesi (Docker Desktop, LM Studio, il browser).
    L'agente, il back-end e Docker Compose il .env lo leggono da soli.
    """
    dal_file = {nome: valore for nome, valore in dotenv_values(CARTELLA_PROGETTO / ".env").items() if valore is not None}
    return {**dal_file, **os.environ}


def main(argomenti: list[str] | None = None, ingresso: TextIO | None = None) -> int:
    configura_flussi()
    parser = argparse.ArgumentParser(
        prog="python -m avvio_chat", description="Accende ciò che serve e apre la chat nel browser."
    )
    parser.add_argument("--senza-browser", action="store_true", help="fa tutto tranne aprire il browser")
    opzioni = parser.parse_args(argomenti)
    try:
        impostazioni = carica_impostazioni(leggi_ambiente())
        return avvia_chat(
            impostazioni, ingresso if ingresso is not None else sys.stdin, scrivi, senza_browser=opzioni.senza_browser
        )
    except (ErroreConfigurazione, ErroreServer, ErroreAvvio) as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrotto.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
