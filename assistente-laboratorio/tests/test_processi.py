"""Esecuzione con limite di tempo che termina anche i processi nipoti (su Windows subprocess.run non lo fa)."""

import subprocess
import sys
import time

from tests.processi import esegui_con_limite

# Il figlio avvia un nipote che eredita le pipe e dorme a lungo: subprocess.run(timeout=...) resterebbe appeso.
NIPOTE_APPESO = (
    "import subprocess, sys, time; "
    "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
    "time.sleep(60)"
)


def test_termina_entro_il_limite_anche_con_un_nipote():
    inizio = time.monotonic()
    risultato = esegui_con_limite([sys.executable, "-c", NIPOTE_APPESO], ingresso="", limite=2)
    assert risultato.scaduto and time.monotonic() - inizio < 20


def test_comando_normale():
    risultato = esegui_con_limite([sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"], ingresso="ciao", limite=30)
    assert not risultato.scaduto and risultato.returncode == 0 and risultato.stdout.strip() == "CIAO"
