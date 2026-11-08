"""Avvio unico con il server MCP reale e un modello finto, senza LM Studio."""

import logging
import socket

import pytest
from langchain_core.messages import AIMessage

import assistente.__main__ as avvio
from assistente import avvio as preparazione
from assistente import registro
from tests.finti import ModelloFinto, chiamata


@pytest.fixture
def ambiente(monkeypatch, tmp_path, porta, popen_registrati):
    """Prepara `main()`: niente .env reale né LM Studio, log in tmp_path, ingresso e uscita simulati."""
    log_assistente = tmp_path / "assistente.log"
    log_server = tmp_path / "server_mcp.log"
    for nome, valore in {
        "LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
        "LMSTUDIO_MODEL": "finto",
        "MCP_PORTA": str(porta),
    }.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(avvio, "load_dotenv", lambda **k: None)
    monkeypatch.setattr(avvio, "verifica_server", lambda *a, **k: None)
    monkeypatch.setattr(avvio, "LOG_ASSISTENTE", log_assistente)
    monkeypatch.setattr(preparazione, "LOG_SERVER", log_server)

    stato = {"righe": ["ciao", "esci"], "risposte": [AIMessage("ciao")], "stampate": [], "strumenti": None}

    def crea_modello_finto(config, strumenti):
        stato["strumenti"] = strumenti
        return ModelloFinto(stato["risposte"])

    originale = avvio.esegui_sessione

    def sessione(grafo, fuso, **opzioni):
        righe = list(stato["righe"])
        return originale(grafo, fuso, leggi=lambda p: righe.pop(0), scrivi=stato["stampate"].append, **opzioni)

    monkeypatch.setattr(avvio, "crea_modello", crea_modello_finto)
    monkeypatch.setattr(avvio, "esegui_sessione", sessione)

    logger = logging.getLogger("assistente")
    prima = list(logger.handlers)
    yield {**stato, "log_assistente": log_assistente, "log_server": log_server, "processi": popen_registrati,
           "porta": porta, "_stato": stato}
    for gestore in logger.handlers[len(prima):]:
        gestore.close()
        logger.removeHandler(gestore)
    logger.propagate = True


def test_avvio_completo(ambiente):
    assert avvio.main() == 0
    stampate = ambiente["_stato"]["stampate"]
    riga = next(r for r in stampate if r.startswith("Strumenti: "))
    assert "ora_corrente (mcp)" in riga and "converti_unita (mcp)" in riga
    assert ambiente["processi"] and all(p.poll() is not None for p in ambiente["processi"])
    assert ambiente["log_server"].exists()
    testo = ambiente["log_assistente"].read_text(encoding="utf-8")
    assert "catalogo" in testo and "spento server MCP" in testo


def test_chiamata_reale_attraverso_il_server(ambiente):
    stato = ambiente["_stato"]
    stato["righe"][:] = ["2,5 km in metri?", "esci"]
    stato["risposte"][:] = [chiamata("converti_unita", {"valore": 2.5, "da": "km", "a": "m"}), AIMessage("2500 m")]
    assert avvio.main() == 0
    assert "[converti_unita · mcp: 2.5, km, m]" in stato["stampate"]
    assert "origine=mcp tool=converti_unita" in ambiente["log_assistente"].read_text(encoding="utf-8")
    assert "tool=converti_unita" in ambiente["log_server"].read_text(encoding="utf-8")


def test_porta_occupata_esce_con_errore(ambiente, capsys):
    with socket.socket() as occupante:
        occupante.bind(("127.0.0.1", ambiente["porta"]))
        occupante.listen()
        assert avvio.main() == 1
    errore = capsys.readouterr().err
    assert "Errore: Porta" in errore and "Traceback" not in errore


def test_porta_mancante(ambiente, monkeypatch, capsys):
    monkeypatch.delenv("MCP_PORTA")
    assert avvio.main() == 1
    assert "MCP_PORTA" in capsys.readouterr().err
