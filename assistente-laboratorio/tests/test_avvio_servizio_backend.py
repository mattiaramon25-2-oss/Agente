"""Avvio del servizio back-end con archivio in memoria e senza Docker."""

import logging
import socket

import pytest
from fastapi.testclient import TestClient

import servizio_backend.__main__ as avvio
from tests.finti_backend import ArchivioInMemoria


def porta_diversa(*escluse: int) -> int:
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            scelta = s.getsockname()[1]
        if scelta not in escluse:
            return scelta


@pytest.fixture
def ambiente(monkeypatch, tmp_path):
    porta_backend = porta_diversa()
    porta_agente = porta_diversa(porta_backend)
    for nome, valore in {
        "BACKEND_PORTA": str(porta_backend),
        "AGENTE_PORTA": str(porta_agente),  # nessun agente in ascolto
        "POSTGRES_USER": "u",
        "POSTGRES_PASSWORD": "p",
        "POSTGRES_DB": "d",
        "POSTGRES_PORTA": "55432",
    }.items():
        monkeypatch.setenv(nome, valore)
    archivio = ArchivioInMemoria()
    monkeypatch.setattr(avvio, "load_dotenv", lambda **k: None)
    monkeypatch.setattr(avvio, "LOG_BACKEND", tmp_path / "servizio_backend.log")
    monkeypatch.setattr(avvio, "ArchivioPostgres", lambda dsn: archivio)
    stato = {"uvicorn": None, "risultati": []}

    def uvicorn_finto(app, host, port, **opzioni):
        stato["uvicorn"] = {"host": host, "port": port}
        stato["risultati"].append(TestClient(app).get("/salute").json())

    monkeypatch.setattr(avvio.uvicorn, "run", uvicorn_finto)
    logger = logging.getLogger("servizio_backend")
    prima = list(logger.handlers)
    yield {"stato": stato, "archivio": archivio, "porta": porta_backend, "log": tmp_path / "servizio_backend.log"}
    for gestore in logger.handlers[len(prima):]:
        gestore.close()
        logger.removeHandler(gestore)
    logger.propagate = True


def test_avvio_regolare_con_agente_spento(ambiente, capsys):
    assert avvio.main() == 0
    assert ambiente["stato"]["uvicorn"] == {"host": "127.0.0.1", "port": ambiente["porta"]}
    assert "l'agente non risponde" in capsys.readouterr().out
    assert ambiente["stato"]["risultati"]
    log = ambiente["log"].read_text(encoding="utf-8")
    assert f"avvio servizio backend porta={ambiente['porta']}" in log and "arresto servizio backend" in log


def test_agente_acceso_nessun_avviso(ambiente, monkeypatch, capsys):
    monkeypatch.setattr(avvio.ClientAgente, "salute", lambda self: True)
    assert avvio.main() == 0
    assert "Attenzione" not in capsys.readouterr().out


def test_configurazione_mancante(ambiente, monkeypatch, capsys):
    monkeypatch.delenv("POSTGRES_PASSWORD")
    assert avvio.main() == 1
    assert "POSTGRES_PASSWORD" in capsys.readouterr().err
    assert ambiente["stato"]["uvicorn"] is None


def test_database_spento(ambiente, capsys):
    ambiente["archivio"].spento = True
    assert avvio.main() == 1
    err = capsys.readouterr().err
    assert "docker compose up -d database" in err and "127.0.0.1:55432" in err
    assert ambiente["stato"]["uvicorn"] is None


def test_porta_occupata(ambiente, capsys):
    with socket.socket() as occupante:
        occupante.bind(("127.0.0.1", ambiente["porta"]))
        occupante.listen()
        assert avvio.main() == 1
    assert "BACKEND_PORTA" in capsys.readouterr().err
    assert ambiente["stato"]["uvicorn"] is None
