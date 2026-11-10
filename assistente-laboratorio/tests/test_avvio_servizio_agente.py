"""Avvio del servizio dell'agente con il server MCP reale, modello e router finti, senza LM Studio."""

import logging
import socket

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import servizio_agente.__main__ as avvio
from assistente import agente
from assistente import avvio as preparazione
from assistente.router import DecisioneRouter
from tests.finti import ModelloFinto, chiamata


class RouterSempreInAmbito:
    def invoke(self, messaggi, config=None):
        return DecisioneRouter(categoria="conversazione", motivo="router finto")


def porta_diversa(*escluse: int) -> int:
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            scelta = s.getsockname()[1]
        if scelta not in escluse:
            return scelta


@pytest.fixture
def ambiente(monkeypatch, tmp_path, porta, popen_registrati):
    porta_agente = porta_diversa(porta)
    for nome, valore in {
        "LMSTUDIO_BASE_URL": "http://127.0.0.1:9/v1",  # nessun server: un accesso a LM Studio fallirebbe
        "LMSTUDIO_MODEL": "finto",
        "MCP_PORTA": str(porta),
        "VARIANTE_CALCOLATRICE": "mcp",
        "VARIANTE_SCADENZE": "mcp",
        "AGENTE_PORTA": str(porta_agente),
    }.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(avvio, "load_dotenv", lambda **k: None)
    monkeypatch.setattr(avvio, "verifica_server", lambda *a, **k: None)
    monkeypatch.setattr(avvio, "LOG_ASSISTENTE", tmp_path / "assistente.log")
    monkeypatch.setattr(preparazione, "LOG_SERVER", tmp_path / "server_mcp.log")
    monkeypatch.setattr(agente, "crea_router", lambda config: RouterSempreInAmbito())
    stato = {"risposte": [], "risultati": [], "uvicorn": None}
    monkeypatch.setattr(agente, "crea_modello", lambda config, strumenti: ModelloFinto(stato["risposte"]))

    def uvicorn_finto(app, host, port, **opzioni):
        """Al posto del server HTTP: interroga l'app mentre il server MCP è ancora acceso."""
        stato["uvicorn"] = {"host": host, "port": port}
        client = TestClient(app)
        stato["risultati"].append(client.get("/salute").json())
        stato["risultati"].append(client.post("/chat", json={"messaggio": "2,5 km in metri?"}).json())

    monkeypatch.setattr(avvio.uvicorn, "run", uvicorn_finto)
    logger = logging.getLogger("assistente")
    prima = list(logger.handlers)
    yield {"stato": stato, "porta_agente": porta_agente, "processi": popen_registrati, "log": tmp_path / "assistente.log"}
    for gestore in logger.handlers[len(prima):]:
        gestore.close()
        logger.removeHandler(gestore)
    logger.propagate = True


def test_avvio_con_server_mcp_reale(ambiente):
    stato = ambiente["stato"]
    stato["risposte"][:] = [chiamata("converti_unita", {"valore": 2.5, "da": "km", "a": "m"}), AIMessage("2500 m")]
    assert avvio.main() == 0
    assert stato["uvicorn"] == {"host": "127.0.0.1", "port": ambiente["porta_agente"]}
    salute, chat = stato["risultati"]
    assert salute["stato"] == "ok" and salute["strumenti"]["converti_unita"] == "mcp"
    assert chat["risposta"] == "2500 m"
    assert chat["strumenti"][0]["nome"] == "converti_unita"  # eseguito davvero dal server MCP
    assert ambiente["processi"] and all(p.poll() is not None for p in ambiente["processi"])
    log = ambiente["log"].read_text(encoding="utf-8")
    assert "avvio servizio agente" in log and "origine=mcp tool=converti_unita" in log and "arresto servizio agente" in log


def test_porta_agente_mancante(ambiente, monkeypatch, capsys):
    monkeypatch.delenv("AGENTE_PORTA")
    assert avvio.main() == 1
    assert "AGENTE_PORTA" in capsys.readouterr().err
    assert ambiente["processi"] == []


def test_porta_agente_occupata(ambiente, capsys):
    with socket.socket() as occupante:
        occupante.bind(("127.0.0.1", ambiente["porta_agente"]))
        occupante.listen()
        assert avvio.main() == 1
    assert "occupata" in capsys.readouterr().err
    assert ambiente["processi"] == []


def test_indirizzo_di_ascolto_da_agente_host(ambiente, monkeypatch):
    """In Docker Compose imposta AGENTE_HOST=0.0.0.0, altrimenti la porta pubblicata non arriva al servizio."""
    monkeypatch.setenv("AGENTE_HOST", "0.0.0.0")
    ambiente["stato"]["risposte"][:] = [AIMessage("ciao")]
    assert avvio.main() == 0
    assert ambiente["stato"]["uvicorn"]["host"] == "0.0.0.0"
