"""Avvio, attesa e arresto del servizio FastAPI reale, senza modello."""

import json
import socket
import sys

import pytest

from assistente.avvio_server import avvia_servizio_api, url_servizio
from assistente.errori import ErroreAvvio
from assistente.registro import CARTELLA_LOG, LOG_API
from assistente.wrapper_scadenze import crea_wrapper_scadenze

ESEMPIO = {"data_inizio": "2026-12-23", "giorni": 3, "lavorativi": True}


def test_costanti():
    assert url_servizio(8766) == "http://127.0.0.1:8766"
    assert LOG_API == CARTELLA_LOG / "servizio_api.log"


def test_ciclo_completo_servizio(porta, tmp_path):
    log = tmp_path / "servizio_api.log"
    with avvia_servizio_api(porta, log) as avviato:
        assert avviato.url == f"http://127.0.0.1:{porta}"
        wrapper = crea_wrapper_scadenze(avviato.url)
        assert json.loads(wrapper.invoke(ESEMPIO))["scadenza"] == "2026-12-29"
        errore = json.loads(wrapper.invoke({**ESEMPIO, "data_inizio": "2026-02-30"}))  # errore controllato
        assert errore["tipo"] == "strumento" and "Data non valida" in errore["errore"]
    assert avviato.processo.poll() is not None  # nessun processo orfano
    testo = log.read_text(encoding="utf-8")
    assert "endpoint=/scadenza" in testo and "esito=ok" in testo and "esito=errore" in testo
    dopo = json.loads(crea_wrapper_scadenze(avviato.url, timeout=1).invoke(ESEMPIO))  # servizio caduto
    assert dopo["tipo"] == "collegamento"


def test_nessun_output_nel_terminale_servizio(porta, tmp_path, capfd):
    with avvia_servizio_api(porta, tmp_path / "s.log") as avviato:
        crea_wrapper_scadenze(avviato.url).invoke(ESEMPIO)
    assert capfd.readouterr() == ("", "")


def test_porta_occupata_servizio(porta, tmp_path):
    with socket.socket() as occupante:
        occupante.bind(("127.0.0.1", porta))
        occupante.listen()
        with pytest.raises(ErroreAvvio) as errore:
            with avvia_servizio_api(porta, tmp_path / "s.log"):
                pass
    assert f"Porta {porta} già in uso" in str(errore.value) and "API_PORTA" in str(errore.value)


def test_servizio_che_non_risponde_viene_spento(porta, tmp_path, popen_registrati):
    comando = [sys.executable, "-c", "import time; time.sleep(60)"]
    with pytest.raises(ErroreAvvio, match="Il servizio FastAPI non è partito"):
        with avvia_servizio_api(porta, tmp_path / "s.log", attesa=1, comando=comando):
            pass
    assert popen_registrati[0].poll() is not None
