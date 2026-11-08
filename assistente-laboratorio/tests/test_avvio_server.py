"""Avvio, attesa e arresto del server MCP reale, senza modello."""

import json
import socket
import sys
from pathlib import Path

import pytest

from assistente import avvio_server
from assistente.avvio_server import avvia_server_mcp, processo_in_attesa
from assistente.errori import ErroreAvvio
from logica.conversioni import UNITA_AMMESSE


def per_nome(strumenti, nome):
    return next(s for s in strumenti if s.name == nome)


def test_ciclo_completo(porta, tmp_path):
    log = tmp_path / "server_mcp.log"
    with avvia_server_mcp(porta, log) as avviato:
        assert avviato.url == f"http://127.0.0.1:{porta}/mcp"
        convertitore = per_nome(avviato.strumenti, "converti_unita")
        assert convertitore.args_schema["properties"]["da"]["enum"] == list(UNITA_AMMESSE)
        assert json.loads(convertitore.invoke({"valore": 2.5, "da": "km", "a": "m"}))["risultato"] == 2500
        errore = json.loads(convertitore.invoke({"valore": 1, "da": "Mars", "a": "m"}))  # errore controllato, slide 23
        assert errore["tipo"] == "strumento" and "Unità sconosciuta" in errore["errore"] and "risultato" not in errore
        ora = json.loads(per_nome(avviato.strumenti, "ora_corrente").invoke({"fuso": "Asia/Tokyo"}))
        assert ora["fuso"] == "Asia/Tokyo"
    assert avviato.processo.poll() is not None  # nessun processo orfano
    dopo = json.loads(convertitore.invoke({"valore": 1, "da": "km", "a": "m"}))
    assert dopo["tipo"] == "collegamento"


def test_log_del_server_in_utf8(porta, tmp_path):
    log = tmp_path / "server_mcp.log"
    with avvia_server_mcp(porta, log) as avviato:
        per_nome(avviato.strumenti, "converti_unita").invoke({"valore": -300, "da": "°C", "a": "°F"})
    testo = log.read_text(encoding="utf-8")
    assert "tool=converti_unita" in testo and "°C" in testo and "zero assoluto" in testo


def test_nessun_output_nel_terminale(porta, tmp_path, capfd):
    with avvia_server_mcp(porta, tmp_path / "s.log") as avviato:
        per_nome(avviato.strumenti, "converti_unita").invoke({"valore": 1, "da": "km", "a": "m"})
    assert capfd.readouterr() == ("", "")


def test_porta_occupata(porta, tmp_path):
    with socket.socket() as occupante:
        occupante.bind(("127.0.0.1", porta))
        occupante.listen()
        with pytest.raises(ErroreAvvio) as errore:
            with avvia_server_mcp(porta, tmp_path / "s.log"):
                pass
    assert f"Porta {porta} già in uso" in str(errore.value) and "MCP_PORTA" in str(errore.value)


def test_server_che_non_parte(porta, tmp_path):
    comando = [sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(1)"]
    with pytest.raises(ErroreAvvio) as errore:
        with avvia_server_mcp(porta, tmp_path / "s.log", comando=comando):
            pass
    assert "Il server MCP non è partito" in str(errore.value) and "boom" in str(errore.value)


def test_server_che_non_risponde_viene_spento(porta, tmp_path, popen_registrati):
    comando = [sys.executable, "-c", "import time; time.sleep(60)"]
    with pytest.raises(ErroreAvvio, match="non è partito"):
        with avvia_server_mcp(porta, tmp_path / "s.log", attesa=1, comando=comando):
            pass
    assert popen_registrati[0].poll() is not None


def test_catalogo_vuoto(porta, tmp_path, popen_registrati):
    comando = [sys.executable, str(Path(__file__).parent / "server_vuoto.py"), "--porta", str(porta)]
    with pytest.raises(ErroreAvvio, match="non espone nessuno strumento"):
        with avvia_server_mcp(porta, tmp_path / "s.log", comando=comando):
            pass
    assert popen_registrati[0].poll() is not None


def test_ctrl_c_durante_l_avvio_spegne_il_server(porta, tmp_path, popen_registrati, monkeypatch):
    def interrompi(*argomenti, **opzioni):
        raise KeyboardInterrupt

    monkeypatch.setattr(avvio_server, "scopri_strumenti", interrompi)
    with pytest.raises(KeyboardInterrupt):
        with avvia_server_mcp(porta, tmp_path / "s.log"):
            pass
    assert popen_registrati[0].poll() is not None


def mai_pronto(tempo_massimo):
    raise ConnectionError("non pronto")


def test_processo_in_attesa_messaggi_parametrizzati(porta, tmp_path):
    comando = [sys.executable, "-c", "import sys; sys.exit(3)"]
    with pytest.raises(ErroreAvvio, match="Il servizio prova non è partito"):
        with processo_in_attesa(
            comando, porta, tmp_path / "p.log", mai_pronto, descrizione="servizio prova", variabile_porta="PROVA_PORTA"
        ):
            pass


def test_processo_in_attesa_porta_occupata_parametrizzata(porta, tmp_path):
    with socket.socket() as occupante:
        occupante.bind(("127.0.0.1", porta))
        occupante.listen()
        with pytest.raises(ErroreAvvio, match="PROVA_PORTA"):
            with processo_in_attesa(
                [sys.executable, "-c", "pass"], porta, tmp_path / "p.log", mai_pronto,
                descrizione="servizio prova", variabile_porta="PROVA_PORTA",
            ):
                pass


def test_persistenza_dopo_riavvio(porta, tmp_path):
    archivio = tmp_path / "note.sqlite3"
    comando = [sys.executable, "-m", "server_mcp", "--porta", str(porta), "--note", str(archivio)]
    with avvia_server_mcp(porta, tmp_path / "s.log", comando=comando) as avviato:
        creata = json.loads(per_nome(avviato.strumenti, "add_note").invoke({"text": "resta dopo il riavvio"}))
    assert creata["id"] == 1 and avviato.processo.poll() is not None
    with avvia_server_mcp(porta, tmp_path / "s.log", comando=comando) as avviato:
        elenco = json.loads(per_nome(avviato.strumenti, "list_notes").invoke({}))
    assert [n["testo"] for n in elenco["note"]] == ["resta dopo il riavvio"]


def test_arresto_ordinato_registrato(porta, tmp_path):
    """L'arresto richiesto scrive «arresto server» e il processo esce con codice 0, non 3."""
    log = tmp_path / "server_mcp.log"
    with avvia_server_mcp(porta, log) as avviato:
        pass
    assert avviato.processo.returncode == 0
    assert "arresto server" in log.read_text(encoding="utf-8")
