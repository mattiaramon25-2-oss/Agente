"""Prova reale con Docker del servizio dell'agente: container `agente`, porta su 127.0.0.1, arresto ordinato.

Si attiva solo con: python -m pytest --docker -m docker -v -s
Richiede Docker Desktop e LM Studio accesi, e il file .env. Come le altre prove Docker, sposta da parte
logs/ e archivio/ dell'utente e li ripristina.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from tzlocal.windows_tz import win_tz

from assistente.ambito import carica_ambito
from assistente.avvio_server import porta_libera
from tests.cartelle_da_parte import cartelle_da_parte

pytestmark = pytest.mark.docker

CARTELLA = Path(__file__).resolve().parent.parent
# Valori di un .env normale, per l'interpolazione di compose.yaml se il .env non li ha; l'ambiente vince.
ENV_COME_DA_DOTENV = {"MCP_PORTA": "8765", "VARIANTE_CALCOLATRICE": "mcp", "VARIANTE_SCADENZE": "mcp", "AGENTE_PORTA": "8767"}
ATTESA_AVVIO = 180
LIMITE_TURNO = 300


def fuso_di_windows() -> str:
    uscita = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "(Get-TimeZone).Id"], capture_output=True, text=True, check=True
    )
    return uscita.stdout.strip()


def compose(*argomenti: str, env: dict, limite: float = 120) -> subprocess.CompletedProcess:
    risultato = subprocess.run(
        ["docker", "compose", *argomenti], cwd=CARTELLA, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=limite,
    )
    print(f"\n$ docker compose {' '.join(argomenti)} -> {risultato.returncode}\n{risultato.stdout}{risultato.stderr}")
    return risultato


def leggi_log(nome: str) -> str:
    percorso = CARTELLA / "logs" / nome
    return percorso.read_text(encoding="utf-8", errors="replace") if percorso.exists() else ""


@pytest.fixture(scope="module")
def immagine():
    subprocess.run(["docker", "compose", "build", "agente"], cwd=CARTELLA, check=True, timeout=900)


def test_servizio_agente_in_docker(immagine):
    fuso = fuso_di_windows()
    env = {**ENV_COME_DA_DOTENV, **os.environ, "FUSO_HOST_WINDOWS": fuso}
    porta = int(env["AGENTE_PORTA"])
    assert porta_libera(porta), f"la porta {porta} è già in uso sull'host: ferma l'altro servizio e riprova"
    url = f"http://127.0.0.1:{porta}"

    with cartelle_da_parte(CARTELLA, ("logs", "archivio")):
        try:
            assert compose("up", "-d", "agente", env=env).returncode == 0

            # Il container controlla LM Studio e avvia il server MCP prima di aprire la porta.
            salute, inizio = None, time.monotonic()
            while time.monotonic() - inizio < ATTESA_AVVIO:
                try:
                    salute = httpx.get(f"{url}/salute", timeout=2).json()
                    break
                except httpx.HTTPError:
                    time.sleep(1)
            assert salute, f"il servizio non risponde su {url} entro {ATTESA_AVVIO} s"
            print(f"  salute: {salute}")
            assert salute["stato"] == "ok" and salute["fuso"] == win_tz[fuso]
            assert salute["strumenti"]["converti_unita"] == "mcp"

            conversione = httpx.post(f"{url}/chat", json={"messaggio": "Quanti metri sono 2,5 km?"}, timeout=LIMITE_TURNO).json()
            print(f"  conversione: {conversione['risposta']!r} {conversione['strumenti']}")
            assert [s["nome"] for s in conversione["strumenti"]] == ["converti_unita"]
            assert "2500" in conversione["risposta"].replace(".", "").replace(" ", "")

            rifiuto = httpx.post(f"{url}/chat", json={"messaggio": "scrivimi una poesia sul mare"}, timeout=LIMITE_TURNO).json()
            print(f"  rifiuto: {rifiuto['risposta']!r}")
            assert rifiuto["risposta"] == carica_ambito().rifiuto

            # Arresto: Docker manda SIGTERM, il servizio deve chiudersi da solo e spegnere il server MCP.
            assert compose("stop", "-t", "30", "agente", env=env).returncode == 0
            stato = compose("ps", "-a", "--format", "json", "agente", env=env).stdout.strip().splitlines()
            uscita = json.loads(stato[0])["ExitCode"] if stato else None
            log = leggi_log("assistente.log")
            assert "avvio servizio agente host=0.0.0.0" in log
            assert "richiesta endpoint=/chat esito=ok" in log and "tool=converti_unita" in log
            assert "nodo=rifiuto" in log
            assert "arresto servizio agente" in log and "spento server MCP codice=0" in log
            assert uscita == 0, f"codice di uscita del container: {uscita}"
        finally:
            compose("rm", "-f", "-s", "agente", env=env)
