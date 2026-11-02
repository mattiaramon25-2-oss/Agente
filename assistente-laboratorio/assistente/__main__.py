"""Punto di avvio: python -m assistente"""

import os
import sys

from dotenv import load_dotenv

from assistente.configurazione import ErroreConfigurazione, carica_configurazione
from assistente.fuso import rileva_fuso
from assistente.grafo import crea_grafo
from assistente.modello import ErroreServer, crea_modello, verifica_server
from assistente.strumenti import crea_strumento_orologio
from assistente.terminale import esegui_sessione


def main() -> int:
    try:
        load_dotenv(override=False)  # le variabili già impostate hanno la precedenza
        config = carica_configurazione(os.environ)
        verifica_server(config.base_url, config.modello)
        fuso = rileva_fuso(os.environ)
        strumenti = [crea_strumento_orologio()]
        grafo = crea_grafo(crea_modello(config, strumenti), strumenti)
        esegui_sessione(grafo, fuso)
    except (ErroreConfigurazione, ErroreServer) as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nArrivederci.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
