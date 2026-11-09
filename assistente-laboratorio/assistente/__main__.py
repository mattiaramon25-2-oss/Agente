"""Punto di avvio: python -m assistente"""

import os
import sys

from dotenv import load_dotenv

from assistente.ambito import carica_ambito
from assistente.avvio import prepara_strumenti
from assistente.configurazione import ErroreConfigurazione, carica_configurazione
from assistente.console import configura_flussi
from assistente.errori import ErroreAvvio
from assistente.fuso import rileva_fuso
from assistente.grafo import crea_grafo
from assistente.modello import ErroreServer, crea_modello, crea_router, verifica_server
from assistente.registro import LOG_ASSISTENTE, configura_registro
from assistente.terminale import esegui_sessione
from assistente.varianti import origini, parametri


def scrivi_pezzo(testo: str) -> None:
    """Un pezzo della risposta in streaming: subito a schermo, senza andare a capo."""
    sys.stdout.write(testo)
    sys.stdout.flush()


def main() -> int:
    configura_flussi()  # pipe e file in UTF-8 (su Windows sarebbero cp1252)
    try:
        load_dotenv(override=False)  # le variabili già impostate hanno la precedenza
        config = carica_configurazione(os.environ)
        configura_registro(LOG_ASSISTENTE)
        ambito = carica_ambito()
        verifica_server(config.base_url, config.modello)
        fuso = rileva_fuso(os.environ)
        with prepara_strumenti(config) as strumenti:
            grafo = crea_grafo(crea_modello(config, strumenti), strumenti, crea_router(config), ambito)
            esegui_sessione(
                grafo, fuso, origini=origini(strumenti), parametri=parametri(strumenti), scrivi_pezzo=scrivi_pezzo
            )
    except (ErroreConfigurazione, ErroreServer, ErroreAvvio) as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nArrivederci.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
