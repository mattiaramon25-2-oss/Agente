"""Prova reale dello step 7: LM Studio, agente vero, back-end e PostgreSQL di prova.

Si attiva solo con: python -m pytest --lmstudio --docker tests/test_reale_backend.py -v -s

L'agente è quello di `python -m assistente` (come in test_reale_servizio_agente.py), servito da uvicorn;
il back-end usa `ArchivioPostgres` sul database del progetto Compose di prova, mai quello dell'utente.
"""

import re
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from assistente.ambito import carica_ambito
from assistente.sse import leggi_sse
from assistente.varianti import origini, parametri
from servizio_agente.app import crea_app as crea_app_agente
from servizio_backend.app import crea_app as crea_app_backend
from servizio_backend.archivio import ArchivioPostgres
from servizio_backend.client_agente import ClientAgente
from tests.postgres_prova import database_di_prova
from tests.reale import ambiente_reale

pytestmark = [pytest.mark.lmstudio, pytest.mark.docker]


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _servi(app) -> tuple[uvicorn.Server, threading.Thread, int]:
    porta = _porta_libera()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning"))
    filo = threading.Thread(target=server.run, daemon=True)
    filo.start()
    fine = time.monotonic() + 30
    while not server.started and time.monotonic() < fine:
        time.sleep(0.05)
    assert server.started, "il server non è partito"
    return server, filo, porta


@pytest.fixture(scope="module")
def backend():
    with ambiente_reale() as (grafo, fuso_utente, strumenti), database_di_prova() as db:
        app_agente = crea_app_agente(grafo, fuso=fuso_utente, modello="reale", origini=origini(strumenti), parametri=parametri(strumenti))
        server_agente, filo_agente, porta_agente = _servi(app_agente)
        archivio = ArchivioPostgres(db.dsn)
        archivio.prepara()
        app_backend = crea_app_backend(archivio, ClientAgente(f"http://127.0.0.1:{porta_agente}"))
        server_backend, filo_backend, porta_backend = _servi(app_backend)
        try:
            yield f"http://127.0.0.1:{porta_backend}"
        finally:
            for server, filo in ((server_backend, filo_backend), (server_agente, filo_agente)):
                server.should_exit = True
                filo.join(timeout=10)


def _turno(url: str, chat_id: int, messaggio: str) -> tuple[list[tuple[str, dict]], dict]:
    with httpx.Client(timeout=300) as client:
        with client.stream("POST", f"{url}/chat/{chat_id}/messaggi", json={"messaggio": messaggio}) as r:
            assert r.status_code == 200
            eventi = list(leggi_sse(r.iter_lines()))
    assert eventi[-1][0] == "fine", eventi[-1]
    return eventi, eventi[-1][1]


@pytest.fixture(scope="module")
def conversazione(backend):
    """Un progetto con istruzioni in inglese e una chat con il primo turno (il calcolo) già fatto."""
    progetto = httpx.post(f"{backend}/progetti", json={"nome": "Prova inglese", "istruzioni": "Rispondi sempre in inglese."}, timeout=10).json()
    chat = httpx.post(f"{backend}/chat", json={"progetto_id": progetto["id"]}, timeout=10).json()
    eventi, fine = _turno(backend, chat["id"], "Quanto fa (3+4)*2?")
    print(f"\n  eventi: {[n for n, _ in eventi]}\n  risposta: {fine['risposta']!r}\n  strumenti: {fine['strumenti']}")
    return chat["id"], eventi, fine


def test_turno_in_streaming_con_calcolo(conversazione):
    _, eventi, fine = conversazione
    assert len([n for n, _ in eventi if n == "testo"]) > 1
    assert "14" in fine["risposta"]
    assert "calcola" in [s["nome"] for s in fine["strumenti"]]


def test_risposta_in_inglese_per_le_istruzioni_del_progetto(conversazione):
    risposta = conversazione[2]["risposta"]
    assert re.search(r"\b(the|is|equals|result)\b", risposta.lower()), f"non in inglese: {risposta!r}"


def test_ricerca_trova_il_messaggio_dell_assistente(backend, conversazione):
    trovati = httpx.get(f"{backend}/ricerca", params={"q": "14"}, timeout=10).json()
    print(f"  ricerca: {trovati}")
    assert any(t["ruolo"] == "assistente" and t["chat_id"] == conversazione[0] for t in trovati)


def test_rifiuto_fuori_ambito(backend, conversazione):
    _, rifiuto = _turno(backend, conversazione[0], "scrivimi una poesia sul mare")
    print(f"  rifiuto: {rifiuto['risposta']!r}")
    assert rifiuto["risposta"] == carica_ambito().rifiuto
