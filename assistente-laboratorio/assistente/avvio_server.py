"""Avvio, attesa e arresto dei processi di servizio (server MCP, e in seguito servizio FastAPI).

Il ciclo è sempre lo stesso: porta libera → avvio con l'output nel file di log → attesa
che il processo risponda davvero (non basta che sia acceso) → arresto garantito all'uscita.
"""

import logging
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, TypeVar

import httpx
from langchain_core.tools import BaseTool

from assistente.client_mcp import scopri_strumenti
from assistente.errori import ErroreAvvio

ATTESA_AVVIO = 10.0
ATTESA_ARRESTO = 5.0
PAUSA_TRA_PROVE = 0.25
CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent

registro = logging.getLogger("assistente.avvio")

T = TypeVar("T")


def porta_libera(porta: int) -> bool:
    with socket.socket() as prova:
        try:
            prova.bind(("127.0.0.1", porta))  # senza SO_REUSEADDR: una porta in uso risulta occupata
        except OSError:
            return False
    return True


def ultime_righe(percorso: Path, quante: int = 10) -> str:
    try:
        righe = percorso.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(log non leggibile)"
    return "\n".join(righe[-quante:]) or "(log vuoto)"


def ferma(processo: subprocess.Popen, attesa: float = ATTESA_ARRESTO) -> None:
    """Chiede al processo di chiudersi; se non lo fa entro `attesa`, lo termina."""
    if processo.poll() is None:
        try:
            if sys.platform == "win32":
                processo.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                processo.terminate()
        except OSError:
            pass
    try:
        processo.wait(attesa)
    except subprocess.TimeoutExpired:
        processo.kill()
        processo.wait()


def _opzioni_processo() -> dict:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


@contextmanager
def processo_in_attesa(
    comando: list[str],
    porta: int,
    percorso_log: Path,
    prova: Callable[[float], T],
    *,
    descrizione: str,
    variabile_porta: str,
    attesa: float = ATTESA_AVVIO,
) -> Iterator[tuple[subprocess.Popen, T]]:
    """Avvia `comando` e attende che `prova(tempo_massimo)` riesca; all'uscita spegne sempre il processo."""
    if not porta_libera(porta):
        raise ErroreAvvio(
            f"Porta {porta} già in uso: chiudi il programma che la usa o cambia {variabile_porta} nel .env."
        )
    percorso_log.parent.mkdir(parents=True, exist_ok=True)
    log = open(percorso_log, "a", encoding="utf-8")
    processo = None
    try:
        processo = subprocess.Popen(
            comando,
            cwd=CARTELLA_PROGETTO,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUTF8": "1"},
            **_opzioni_processo(),
        )
        registro.info("avviato %s porta=%d pid=%d", descrizione, porta, processo.pid)
        scadenza = time.monotonic() + attesa
        valore = None
        pronto = False
        while processo.poll() is None:
            rimasto = scadenza - time.monotonic()
            if rimasto <= 0:
                break
            try:
                valore = prova(min(2.0, rimasto))
                pronto = True
                break
            except Exception:
                time.sleep(PAUSA_TRA_PROVE)
        if not pronto:
            log.flush()
            raise ErroreAvvio(
                f"Il {descrizione} non è partito (porta {porta}). "
                f"Ultime righe di {percorso_log}:\n{ultime_righe(percorso_log)}"
            )
        yield processo, valore
    finally:
        if processo is not None:
            ferma(processo)
            registro.info("spento %s codice=%s", descrizione, processo.returncode)
        log.close()


def url_server(porta: int) -> str:
    return f"http://127.0.0.1:{porta}/mcp"


@dataclass(frozen=True)
class ServerAvviato:
    processo: subprocess.Popen
    url: str
    strumenti: list[BaseTool]


@contextmanager
def avvia_server_mcp(
    porta: int, percorso_log: Path, attesa: float = ATTESA_AVVIO, comando: list[str] | None = None
) -> Iterator[ServerAvviato]:
    """Avvia il server MCP, attende una discovery riuscita (non un semplice HTTP 200) e lo spegne all'uscita."""
    url = url_server(porta)
    comando = comando or [sys.executable, "-m", "server_mcp", "--porta", str(porta)]

    def discovery(tempo_massimo: float) -> list[BaseTool]:
        return scopri_strumenti(url, timeout_scoperta=tempo_massimo)

    with processo_in_attesa(
        comando, porta, percorso_log, discovery, descrizione="server MCP", variabile_porta="MCP_PORTA", attesa=attesa
    ) as (processo, strumenti):
        if not strumenti:
            raise ErroreAvvio("Il server MCP non espone nessuno strumento.")
        registro.info("catalogo strumenti=%s", [s.name for s in strumenti])
        yield ServerAvviato(processo, url, strumenti)


def url_servizio(porta: int) -> str:
    return f"http://127.0.0.1:{porta}"


@dataclass(frozen=True)
class ServizioAvviato:
    processo: subprocess.Popen
    url: str


@contextmanager
def avvia_servizio_api(
    porta: int, percorso_log: Path, attesa: float = ATTESA_AVVIO, comando: list[str] | None = None
) -> Iterator[ServizioAvviato]:
    """Avvia il servizio FastAPI delle scadenze; è pronto quando /openapi.json descrive /scadenza."""
    url = url_servizio(porta)
    comando = comando or [sys.executable, "-m", "servizio_api", "--porta", str(porta)]

    def contratto_presente(tempo_massimo: float) -> None:
        risposta = httpx.get(f"{url}/openapi.json", timeout=tempo_massimo)
        if "/scadenza" not in risposta.json().get("paths", {}):
            raise ValueError("il servizio non descrive /scadenza")

    with processo_in_attesa(
        comando,
        porta,
        percorso_log,
        contratto_presente,
        descrizione="servizio FastAPI",
        variabile_porta="API_PORTA",
        attesa=attesa,
    ) as (processo, _):
        yield ServizioAvviato(processo, url)
