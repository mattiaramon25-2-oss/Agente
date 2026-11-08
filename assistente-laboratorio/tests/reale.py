"""Ambiente comune alle prove reali: stesso percorso di `python -m assistente`, senza terminale."""

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping

from dotenv import load_dotenv

from assistente.avvio import prepara_strumenti
from assistente.configurazione import carica_configurazione
from assistente.fuso import rileva_fuso
from assistente.grafo import crea_grafo
from assistente.modello import crea_modello, verifica_server
from assistente.registro import LOG_ASSISTENTE, configura_registro


@contextmanager
def ambiente_reale(
    variabili: Mapping[str, str] | None = None, archivio_note: Path | None = None
) -> Iterator[tuple]:
    """Restituisce (grafo, fuso_utente, strumenti) con LM Studio e i server reali; `variabili` vince sul .env.

    Con `archivio_note` il server MCP usa quel file per le note invece dell'archivio reale.
    """
    precedenti = {nome: os.environ.get(nome) for nome in (variabili or {})}
    os.environ.update(variabili or {})
    try:
        load_dotenv(override=False)
        config = carica_configurazione(os.environ)
        configura_registro(LOG_ASSISTENTE)
        verifica_server(config.base_url, config.modello)
        fuso_utente = rileva_fuso(os.environ).fuso
        comando = None
        if archivio_note is not None:
            comando = [sys.executable, "-m", "server_mcp", "--porta", str(config.porta_mcp), "--note", str(archivio_note)]
        with prepara_strumenti(config, comando_server=comando) as strumenti:
            grafo = crea_grafo(crea_modello(config, strumenti), strumenti)
            print(f"\nmodello: {config.modello} · fuso utente: {fuso_utente} · strumenti: {[s.name for s in strumenti]}")
            yield grafo, fuso_utente, strumenti
    finally:
        for nome, valore in precedenti.items():
            if valore is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valore


def righe_del_log(dopo: int) -> str:
    """Il testo aggiunto a logs/assistente.log dopo la posizione `dopo` (in byte)."""
    with open(LOG_ASSISTENTE, "rb") as file:
        file.seek(dopo)
        return file.read().decode("utf-8", errors="replace")


def posizione_log() -> int:
    return LOG_ASSISTENTE.stat().st_size if LOG_ASSISTENTE.exists() else 0
