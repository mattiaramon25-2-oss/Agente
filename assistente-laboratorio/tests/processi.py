"""Esecuzione di un comando con un limite di tempo che vale davvero, anche su Windows.

subprocess.run(timeout=...) termina solo il processo diretto: se questo ha avviato altri processi
che tengono aperte le pipe (PowerShell → docker.exe), la lettura dell'uscita resta appesa senza
limite. Qui, alla scadenza, si termina l'intero albero dei processi.
"""

import os
import signal
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Esito:
    returncode: int | None
    stdout: str
    stderr: str
    scaduto: bool


def _termina_albero(processo: subprocess.Popen) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(processo.pid)], capture_output=True)
    else:
        try:
            os.killpg(processo.pid, signal.SIGKILL)
        except OSError:
            processo.kill()


def esegui_con_limite(comando: list[str], ingresso: str, limite: float, **opzioni) -> Esito:
    gruppo = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else {"start_new_session": True}
    processo = subprocess.Popen(
        comando,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **gruppo,
        **opzioni,
    )
    try:
        uscita, errori = processo.communicate(ingresso, timeout=limite)
        return Esito(processo.returncode, uscita, errori, scaduto=False)
    except subprocess.TimeoutExpired:
        _termina_albero(processo)
        try:
            uscita, errori = processo.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            uscita, errori = "", ""
        return Esito(processo.returncode, uscita or "", errori or "", scaduto=True)
