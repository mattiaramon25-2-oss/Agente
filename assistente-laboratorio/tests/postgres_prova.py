"""Database PostgreSQL di prova: un progetto Compose a parte, con volume, porta e password di prova.

Il container e il volume dell'utente (progetto Compose predefinito) non vengono mai toccati:
ogni comando usa `-p PROGETTO_PROVA`, e alla fine `down -v` cancella solo quel progetto.
"""
import os
import socket
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg.conninfo import make_conninfo

PROGETTO_PROVA = "assistente-laboratorio-prova"
CARTELLA = Path(__file__).resolve().parent.parent
# Valori finti per le variabili `:?` degli altri servizi: Compose controlla tutto il file.
ENV_FINTO = {
    "MCP_PORTA": "8765",
    "VARIANTE_CALCOLATRICE": "mcp",
    "VARIANTE_SCADENZE": "mcp",
    "AGENTE_PORTA": "8767",
    "LMSTUDIO_BASE_URL_DOCKER": "http://host.docker.internal:1234/v1",
    "LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1",
    "LMSTUDIO_MODEL": "prova",
}
LIMITE_COMPOSE = 300


@dataclass(frozen=True)
class DatabaseProva:
    """`dsn` per collegarsi; `env` per `ferma(env)` e `riavvia(env)`."""

    dsn: str
    env: dict


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _compose(env: dict, *argomenti: str, controlla: bool = True) -> subprocess.CompletedProcess:
    risultato = subprocess.run(
        ["docker", "compose", "-p", PROGETTO_PROVA, *argomenti],
        cwd=CARTELLA, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=LIMITE_COMPOSE,
    )
    if controlla and risultato.returncode != 0:
        raise RuntimeError(f"docker compose {' '.join(argomenti)} -> {risultato.returncode}\n{risultato.stdout}{risultato.stderr}")
    return risultato


def ferma(env: dict) -> None:
    """Ferma il container del database di prova (il volume resta)."""
    _compose(env, "stop", "database")


def riavvia(env: dict) -> None:
    """Riavvia il container del database di prova e aspetta che sia sano."""
    _compose(env, "up", "-d", "--wait", "database")


@contextmanager
def database_di_prova() -> Iterator[DatabaseProva]:
    porta = _porta_libera()
    env = {
        **ENV_FINTO,
        **os.environ,
        "POSTGRES_USER": "prova",
        "POSTGRES_PASSWORD": "prova",
        "POSTGRES_DB": "prova",
        "POSTGRES_PORTA": str(porta),
    }
    try:
        riavvia(env)
        dsn = make_conninfo(host="127.0.0.1", port=porta, user="prova", password="prova", dbname="prova", connect_timeout=5)
        yield DatabaseProva(dsn=dsn, env=env)
    finally:
        pulizia = _compose(env, "down", "-v", controlla=False)
        if pulizia.returncode != 0:
            print(
                f"\nATTENZIONE: la pulizia del progetto Compose {PROGETTO_PROVA} è fallita "
                f"(codice {pulizia.returncode}): controlla container e volume a mano.\n{pulizia.stderr}"
            )


def svuota(dsn: str) -> None:
    with psycopg.connect(dsn) as connessione:
        connessione.execute("TRUNCATE messaggi, chat, progetti RESTART IDENTITY CASCADE")
