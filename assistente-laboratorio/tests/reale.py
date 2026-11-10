"""Ambiente comune alle prove reali: stesso percorso di `python -m assistente`, senza terminale."""

import os
import sys
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping

from dotenv import load_dotenv

from assistente.agente import crea_agente
from assistente.ambito import carica_ambito
from assistente.avvio import prepara_strumenti
from assistente.configurazione import carica_configurazione
from assistente.fuso import rileva_fuso
from assistente.modello import verifica_server
from assistente.registro import LOG_ASSISTENTE, configura_registro


def archivio_per_prove(archivio_note: Path | None) -> Path:
    """L'archivio delle note per una prova reale: mai quello dell'utente."""
    return archivio_note or Path(tempfile.mkdtemp(prefix="note_prova_")) / "note.sqlite3"


def rimuovi_archivio_temporaneo(percorso: Path) -> None:
    """Elimina la cartella temporanea creata da archivio_per_prove (solo quella, mai altro)."""
    if percorso.parent.name.startswith("note_prova_"):
        shutil.rmtree(percorso.parent, ignore_errors=True)


@contextmanager
def ambiente_reale(
    variabili: Mapping[str, str] | None = None, archivio_note: Path | None = None
) -> Iterator[tuple]:
    """Restituisce (grafo, fuso_utente, strumenti) con LM Studio e i server reali; `variabili` vince sul .env.

    Il server MCP usa sempre un archivio delle note temporaneo (o `archivio_note`), mai quello reale:
    il modello potrebbe chiamare add_note o delete_note anche nelle prove di altri strumenti.
    """
    precedenti = {nome: os.environ.get(nome) for nome in (variabili or {})}
    os.environ.update(variabili or {})
    try:
        load_dotenv(override=False)
        config = carica_configurazione(os.environ)
        configura_registro(LOG_ASSISTENTE)
        verifica_server(config.base_url, config.modello)
        fuso_utente = rileva_fuso(os.environ).fuso
        archivio = archivio_per_prove(archivio_note)
        temporaneo = archivio_note is None
        comando = [sys.executable, "-m", "server_mcp", "--porta", str(config.porta_mcp), "--note", str(archivio)]
        with prepara_strumenti(config, comando_server=comando) as strumenti:
            grafo = crea_agente(config, strumenti, carica_ambito())
            print(f"\nmodello: {config.modello} · fuso utente: {fuso_utente} · strumenti: {[s.name for s in strumenti]}")
            yield grafo, fuso_utente, strumenti
    finally:
        if "temporaneo" in locals() and temporaneo:
            rimuovi_archivio_temporaneo(archivio)
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
