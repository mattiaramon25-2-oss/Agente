"""Avvio della chat nel browser: python -m avvio_chat (oppure doppio clic su avvia-chat.cmd).

Accende ciò che manca (Docker Desktop, il server di LM Studio, i container del database e della
pagina, il servizio dell'agente e il back-end), apre la chat nel browser e resta in attesa.
Scrivendo «esci», con Ctrl+C o a fine input spegne ciò che ha avviato; i container restano accesi.
"""

import argparse
import os
import sys
from typing import TextIO

from dotenv import load_dotenv

from assistente.configurazione import ErroreConfigurazione
from assistente.console import configura_flussi
from assistente.errori import ErroreAvvio
from assistente.modello import ErroreServer
from avvio_chat.passi import avvia_chat, carica_impostazioni
from avvio_chat.vita import lega_i_figli


def scrivi(testo: str) -> None:
    """Una riga nella finestra, subito visibile."""
    print(testo, flush=True)


def main(argomenti: list[str] | None = None, ingresso: TextIO | None = None) -> int:
    configura_flussi()
    parser = argparse.ArgumentParser(
        prog="python -m avvio_chat", description="Accende ciò che serve e apre la chat nel browser."
    )
    parser.add_argument("--senza-browser", action="store_true", help="fa tutto tranne aprire il browser")
    opzioni = parser.parse_args(argomenti)
    try:
        load_dotenv(override=False)  # le variabili già impostate hanno la precedenza
        impostazioni = carica_impostazioni(os.environ)
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
    # Chiudere la finestra uccide questo programma senza passare da «esci»: con questo legame
    # Windows chiude anche i processi che ha avviato. La maniglia resta viva fino alla fine.
    legame = lega_i_figli()
    sys.exit(main())
