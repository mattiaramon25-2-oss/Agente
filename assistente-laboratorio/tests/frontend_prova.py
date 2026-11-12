"""Container `frontend` di prova: un progetto Compose a parte, mai quello dell'utente.

Ogni comando usa `-p PROGETTO_FRONTEND_PROVA`, e alla fine `down` toglie solo quel progetto.
"""
import os
import subprocess
import threading
import time
import urllib.request
from contextlib import contextmanager
from typing import Iterator

import uvicorn

from tests.postgres_prova import CARTELLA, ENV_FINTO, LIMITE_COMPOSE, _porta_libera

PROGETTO_FRONTEND_PROVA = "assistente-laboratorio-prova-frontend"
ATTESA_PRONTO = 60


class Servito:
    """Un'app servita da uvicorn in un thread su una porta fissa: si può fermare e riavviare sulla stessa porta."""

    def __init__(self, app):
        self.app = app
        self.porta = _porta_libera()
        self.server: uvicorn.Server | None = None
        self.filo: threading.Thread | None = None

    def avvia(self) -> None:
        self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", port=self.porta, log_level="warning"))
        self.filo = threading.Thread(target=self.server.run, daemon=True)
        self.filo.start()
        fine = time.monotonic() + 30
        while not self.server.started and time.monotonic() < fine:
            time.sleep(0.05)
        assert self.server.started, "il server non è partito"

    def ferma(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
            self.filo.join(timeout=15)
            self.server = None


def _compose(env: dict, *argomenti: str, controlla: bool = True) -> subprocess.CompletedProcess:
    risultato = subprocess.run(
        ["docker", "compose", "-p", PROGETTO_FRONTEND_PROVA, *argomenti],
        cwd=CARTELLA, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=LIMITE_COMPOSE,
    )
    if controlla and risultato.returncode != 0:
        raise RuntimeError(f"docker compose {' '.join(argomenti)} -> {risultato.returncode}\n{risultato.stdout}{risultato.stderr}")
    return risultato


def _risponde(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as risposta:
            return risposta.status == 200
    except OSError:
        return False


@contextmanager
def frontend_di_prova(porta_backend: int) -> Iterator[str]:
    """Avvia il container `frontend` verso il back-end di prova e restituisce l'URL della chat."""
    porta = _porta_libera()
    env = {**ENV_FINTO, **os.environ, "BACKEND_PORTA": str(porta_backend), "FRONTEND_PORTA": str(porta)}
    url = f"http://127.0.0.1:{porta}"
    try:
        _compose(env, "up", "-d", "--build", "frontend")
        fine = time.monotonic() + ATTESA_PRONTO
        while not _risponde(f"{url}/"):
            if time.monotonic() > fine:
                raise RuntimeError(f"il frontend non risponde su {url} entro {ATTESA_PRONTO} s")
            time.sleep(0.5)
        yield url
    finally:
        pulizia = _compose(env, "down", controlla=False)
        if pulizia.returncode != 0:
            print(
                f"\nATTENZIONE: la pulizia del progetto Compose {PROGETTO_FRONTEND_PROVA} è fallita "
                f"(codice {pulizia.returncode}): controlla il container a mano.\n{pulizia.stderr}"
            )
