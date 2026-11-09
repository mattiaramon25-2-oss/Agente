"""Prova reale dello step 6: la stessa domanda alla CLI e all'API HTTP, con LM Studio.

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s

L'API è servita da uvicorn su una porta vera, in un thread; agente e archivio delle note
(temporaneo) sono quelli di `ambiente_reale`, cioè lo stesso percorso di `python -m assistente`.
"""

import socket
import threading
import time

import httpx
import pytest
import uvicorn

from assistente.ambito import carica_ambito
from assistente.fuso import RisultatoFuso
from assistente.terminale import esegui_sessione
from assistente.varianti import origini, parametri
from servizio_agente.app import crea_app
from tests.reale import ambiente_reale, posizione_log, righe_del_log

pytestmark = pytest.mark.lmstudio


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def ambiente():
    with ambiente_reale() as (grafo, fuso_utente, strumenti):
        app = crea_app(grafo, fuso=fuso_utente, modello="reale", origini=origini(strumenti), parametri=parametri(strumenti))
        porta = _porta_libera()
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning"))
        filo = threading.Thread(target=server.run, daemon=True)
        filo.start()
        while not server.started:
            time.sleep(0.05)
        try:
            yield grafo, fuso_utente, strumenti, f"http://127.0.0.1:{porta}"
        finally:
            server.should_exit = True
            filo.join(timeout=10)


def _cli(ambiente, domanda):
    grafo, fuso_utente, strumenti, _ = ambiente
    righe = [domanda, "esci"]
    stampate = []
    inizio = posizione_log()
    esegui_sessione(
        grafo, RisultatoFuso(fuso_utente, "prova", None), leggi=lambda p: righe.pop(0), scrivi=stampate.append,
        origini=origini(strumenti), parametri=parametri(strumenti),
    )
    risposta = next(r for r in stampate if r.startswith("Assistente: "))[len("Assistente: "):]
    return risposta, [r for r in stampate if r.startswith("[")], righe_del_log(inizio)


def _api(ambiente, domanda):
    url = ambiente[3]
    inizio = posizione_log()
    corpo = httpx.post(f"{url}/chat", json={"messaggio": domanda}, timeout=300).json()
    return corpo, righe_del_log(inizio)


def _stampa(domanda, cli, api):
    print(f"\n  domanda: {domanda}\n  CLI: {cli[0]!r} {cli[1]}\n  API: {api[0]['risposta']!r} {api[0]['strumenti']}")


def test_salute(ambiente):
    corpo = httpx.get(f"{ambiente[3]}/salute", timeout=10).json()
    assert corpo["stato"] == "ok" and corpo["strumenti"]["calcola"] in ("mcp", "locale")


def test_rifiuto_identico(ambiente):
    domanda = "scrivimi una poesia sul mare"
    cli, api = _cli(ambiente, domanda), _api(ambiente, domanda)
    _stampa(domanda, cli, api)
    assert cli[0] == api[0]["risposta"] == carica_ambito().rifiuto
    for log in (cli[2], api[1]):
        assert "categoria=fuori_ambito" in log and "nodo=rifiuto" in log and "nodo=modello" not in log


def test_calcolo_stesso_risultato(ambiente):
    domanda = "Quanto fa (3+4)*2?"
    cli, api = _cli(ambiente, domanda), _api(ambiente, domanda)
    _stampa(domanda, cli, api)
    assert "14" in cli[0] and "14" in api[0]["risposta"]
    assert any(r.startswith("[calcola · ") for r in cli[1])
    assert [s["nome"] for s in api[0]["strumenti"]] == ["calcola"]
    for log in (cli[2], api[1]):
        assert "categoria=conversazione" in log and "tool=calcola" in log
    assert "richiesta endpoint=/chat esito=ok" in api[1]
