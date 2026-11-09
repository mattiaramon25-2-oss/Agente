"""Avvio unico con il server MCP reale e un modello finto, senza LM Studio."""

import logging
import socket

import pytest
from langchain_core.messages import AIMessage

import assistente.__main__ as avvio
from assistente import avvio as preparazione
from assistente import registro
from tests.finti import ModelloFinto, chiamata
from assistente.router import DecisioneRouter


class RouterSempreInAmbito:
    def invoke(self, messaggi, config=None):
        return DecisioneRouter(categoria="conversazione", motivo="router finto")


@pytest.fixture
def ambiente(monkeypatch, tmp_path, porta, popen_registrati):
    """Prepara `main()`: niente .env reale né LM Studio, log in tmp_path, ingresso e uscita simulati."""
    log_assistente = tmp_path / "assistente.log"
    log_server = tmp_path / "server_mcp.log"
    log_api = tmp_path / "servizio_api.log"
    for nome, valore in {
        "LMSTUDIO_BASE_URL": "http://127.0.0.1:9/v1",  # nessun server: un accesso a LM Studio fallirebbe
        "LMSTUDIO_MODEL": "finto",
        "MCP_PORTA": str(porta),
        "VARIANTE_CALCOLATRICE": "mcp",
        "VARIANTE_SCADENZE": "mcp",
    }.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(avvio, "load_dotenv", lambda **k: None)
    monkeypatch.setattr(avvio, "verifica_server", lambda *a, **k: None)
    monkeypatch.setattr(avvio, "LOG_ASSISTENTE", log_assistente)
    monkeypatch.setattr(preparazione, "LOG_SERVER", log_server)
    monkeypatch.setattr(preparazione, "LOG_API", log_api)

    stato = {"righe": ["ciao", "esci"], "risposte": [AIMessage("ciao")], "stampate": [], "strumenti": None}

    def crea_modello_finto(config, strumenti):
        stato["strumenti"] = strumenti
        return ModelloFinto(stato["risposte"])

    originale = avvio.esegui_sessione

    def sessione(grafo, fuso, **opzioni):
        righe = list(stato["righe"])
        return originale(grafo, fuso, leggi=lambda p: righe.pop(0), scrivi=stato["stampate"].append, **opzioni)

    monkeypatch.setattr(avvio, "crea_modello", crea_modello_finto)
    # Anche il router è finto: senza, la prova chiamerebbe LM Studio davvero.
    monkeypatch.setattr(avvio, "crea_router", lambda config: RouterSempreInAmbito())
    monkeypatch.setattr(avvio, "esegui_sessione", sessione)

    logger = logging.getLogger("assistente")
    prima = list(logger.handlers)
    yield {**stato, "log_assistente": log_assistente, "log_server": log_server, "log_api": log_api,
           "processi": popen_registrati,
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
    stato["risposte"][:] = [chiamata("converti_unita", {"a": "m", "da": "km", "valore": 2.5}), AIMessage("2500 m")]
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


def chiedi_calcolo(ambiente):
    stato = ambiente["_stato"]
    stato["righe"][:] = ["quanto fa (3+4)*2?", "esci"]
    stato["risposte"][:] = [chiamata("calcola", {"espressione": "(3 + 4) * 2"}), AIMessage("14")]
    assert avvio.main() == 0
    return stato["stampate"]


def test_variante_locale_non_tocca_il_server(ambiente, monkeypatch):
    monkeypatch.setenv("VARIANTE_CALCOLATRICE", "locale")
    stampate = chiedi_calcolo(ambiente)
    assert "calcola (locale)" in next(r for r in stampate if r.startswith("Strumenti: "))
    assert "[calcola · locale: (3 + 4) * 2]" in stampate
    log = ambiente["log_assistente"].read_text(encoding="utf-8")
    assert "origine=locale tool=calcola" in log and "varianti calcolatrice=locale" in log
    assert "tool=calcola" not in ambiente["log_server"].read_text(encoding="utf-8")


def test_variante_mcp(ambiente):
    stampate = chiedi_calcolo(ambiente)
    assert "calcola (mcp)" in next(r for r in stampate if r.startswith("Strumenti: "))
    assert "[calcola · mcp: (3 + 4) * 2]" in stampate
    assert "tool=calcola" in ambiente["log_server"].read_text(encoding="utf-8")


def porta_libera_diversa(da: int) -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        scelta = s.getsockname()[1]
    return scelta if scelta != da else porta_libera_diversa(da)


def test_variante_fastapi(ambiente, monkeypatch):
    monkeypatch.setenv("VARIANTE_SCADENZE", "fastapi")
    monkeypatch.setenv("API_PORTA", str(porta_libera_diversa(ambiente["porta"])))
    stato = ambiente["_stato"]
    stato["righe"][:] = ["quando scadono 3 giorni lavorativi dal 23 dicembre 2026?", "esci"]
    argomenti = {"data_inizio": "2026-12-23", "giorni": 3, "lavorativi": True}
    stato["risposte"][:] = [chiamata("calcola_scadenza", argomenti), AIMessage("Il 29 dicembre 2026.")]
    assert avvio.main() == 0
    assert "calcola_scadenza (fastapi)" in next(r for r in stato["stampate"] if r.startswith("Strumenti: "))
    assert "[calcola_scadenza · fastapi: 2026-12-23, 3, True]" in stato["stampate"]
    assert "endpoint=/scadenza" in ambiente["log_api"].read_text(encoding="utf-8")
    log = ambiente["log_assistente"].read_text(encoding="utf-8")
    assert "origine=fastapi tool=calcola_scadenza" in log and "scadenze=fastapi" in log
    assert "tool=calcola_scadenza" not in ambiente["log_server"].read_text(encoding="utf-8")
    assert len(ambiente["processi"]) == 2 and all(p.poll() is not None for p in ambiente["processi"])


def test_servizio_che_non_parte_spegne_tutto(ambiente, monkeypatch, capsys):
    porta_api = porta_libera_diversa(ambiente["porta"])
    monkeypatch.setenv("VARIANTE_SCADENZE", "fastapi")
    monkeypatch.setenv("API_PORTA", str(porta_api))
    with socket.socket() as occupante:
        occupante.bind(("127.0.0.1", porta_api))
        occupante.listen()
        assert avvio.main() == 1
    errore = capsys.readouterr().err
    assert "API_PORTA" in errore and "Traceback" not in errore
    assert ambiente["processi"] and all(p.poll() is not None for p in ambiente["processi"])  # server MCP spento
