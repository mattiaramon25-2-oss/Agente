"""Evidenza dello step 7: le chat restano dopo il riavvio del back-end e del database.

Si attiva solo con: python -m pytest --docker -m docker -v -s

Database: progetto Compose di prova (tests/postgres_prova.py), mai quello dell'utente. Agente: finto, via HTTP.
Back-end: processo vero (`python -m servizio_backend`), fermato con CTRL_BREAK come farebbe l'utente.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager

import httpx
import pytest
import uvicorn
from langchain_core.messages import AIMessage

from assistente.ambito import Ambito
from assistente.grafo import crea_grafo
from assistente.router import DecisioneRouter
from servizio_agente.app import crea_app
from tests.cartelle_da_parte import cartelle_da_parte
from tests.finti import ModelloFinto, RouterFinto
from tests.postgres_prova import CARTELLA, database_di_prova, ferma, riavvia
from tests.processi import _termina_albero

pytestmark = pytest.mark.docker

ATTESA_AVVIO = 30
ATTESA_ARRESTO = 30
LOG = CARTELLA / "logs" / "servizio_backend.log"


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def agente_finto():
    """L'app HTTP dell'agente con modello e router finti, servita da uvicorn in un thread."""
    router = RouterFinto([DecisioneRouter(categoria="conversazione", motivo="ok") for _ in range(3)])
    grafo = crea_grafo(
        ModelloFinto([AIMessage("Ciao! Sono l'assistente del laboratorio.")]),
        [],
        router,
        Ambito(("data e ora",), ("poesie",), "Prova un altro provider."),
    )
    app = crea_app(grafo, fuso="Europe/Rome", modello="finto", origini={}, parametri={})
    porta = _porta_libera()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning"))
    filo = threading.Thread(target=server.run, daemon=True)
    filo.start()
    fine = time.monotonic() + 15
    while not server.started and time.monotonic() < fine:
        time.sleep(0.05)
    assert server.started, "l'agente finto non è partito"
    try:
        yield porta
    finally:
        server.should_exit = True
        filo.join(timeout=10)


class Backend:
    """Il processo `python -m servizio_backend`, avviato e fermato come farebbe l'utente."""

    def __init__(self, env: dict, porta: int):
        self.env = env
        self.porta = porta
        self.url = f"http://127.0.0.1:{porta}"
        self.processo: subprocess.Popen | None = None

    def avvia(self) -> None:
        gruppo = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else {"start_new_session": True}
        self.processo = subprocess.Popen(
            [sys.executable, "-m", "servizio_backend"], cwd=CARTELLA, env=self.env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", **gruppo,
        )
        fine = time.monotonic() + ATTESA_AVVIO
        while time.monotonic() < fine:
            if self.processo.poll() is not None:
                raise AssertionError(f"il back-end è uscito ({self.processo.returncode}):\n{self.processo.stdout.read()}")
            try:
                if httpx.get(f"{self.url}/salute", timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.3)
        raise AssertionError("il back-end non è pronto entro il tempo limite")

    def ferma(self) -> int:
        segnale = signal.CTRL_BREAK_EVENT if sys.platform == "win32" else signal.SIGTERM
        self.processo.send_signal(segnale)
        codice = self.processo.wait(timeout=ATTESA_ARRESTO)
        self.processo.stdout.read()
        return codice

    def termina_se_vivo(self) -> None:
        if self.processo is not None and self.processo.poll() is None:
            _termina_albero(self.processo)
            self.processo.wait(timeout=15)


def _fotografia(url: str) -> dict:
    progetti = httpx.get(f"{url}/progetti", timeout=10).json()
    chat = httpx.get(f"{url}/chat", timeout=10).json()
    dettagli = [httpx.get(f"{url}/chat/{c['id']}", timeout=10).json() for c in chat]
    return {"progetti": progetti, "chat": chat, "dettagli": dettagli}


def _stampa(titolo: str, foto: dict) -> None:
    print(f"\n=== {titolo} ===")
    print("progetti:", json.dumps(foto["progetti"], ensure_ascii=False, indent=2))
    print("chat:", json.dumps(foto["chat"], ensure_ascii=False, indent=2))
    for dettaglio in foto["dettagli"]:
        print(f"messaggi della chat {dettaglio['id']}:", json.dumps(dettaglio["messaggi"], ensure_ascii=False, indent=2))


def test_chat_ancora_presenti_dopo_il_riavvio_di_back_end_e_database():
    with cartelle_da_parte(CARTELLA, ("logs",)), database_di_prova() as db, agente_finto() as porta_agente:
        porta = _porta_libera()
        env = {**os.environ, **db.env, "BACKEND_PORTA": str(porta), "AGENTE_PORTA": str(porta_agente)}
        backend = Backend(env, porta)
        try:
            backend.avvia()
            progetto = httpx.post(
                f"{backend.url}/progetti", json={"nome": "Laboratorio", "istruzioni": "Rispondi in modo breve."}, timeout=10
            ).json()
            chat = httpx.post(f"{backend.url}/chat", json={"progetto_id": progetto["id"]}, timeout=10).json()
            eventi = []
            with httpx.stream(
                "POST", f"{backend.url}/chat/{chat['id']}/messaggi", json={"messaggio": "Ciao!"}, timeout=60
            ) as risposta:
                assert risposta.status_code == 200
                eventi = [riga[len("event:"):].strip() for riga in risposta.iter_lines() if riga.startswith("event:")]
            assert eventi[-1] == "fine"
            prima = _fotografia(backend.url)
            _stampa("PRIMA del riavvio", prima)
            assert [m["ruolo"] for m in prima["dettagli"][0]["messaggi"]] == ["utente", "assistente"]

            assert backend.ferma() == 0
            assert "arresto servizio backend" in LOG.read_text(encoding="utf-8")
            ferma(db.env)
            riavvia(db.env)
            backend.avvia()

            dopo = _fotografia(backend.url)
            _stampa("DOPO il riavvio di back-end e database", dopo)
            assert dopo == prima
            assert len(dopo["dettagli"][0]["messaggi"]) == 2
            assert backend.ferma() == 0
        finally:
            backend.termina_se_vivo()
