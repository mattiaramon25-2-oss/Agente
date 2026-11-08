"""Prova reale con Docker: collegamento a LM Studio dal container e fuso dell'utente corretto.

Si attiva solo con: python -m pytest --docker -m docker -v -s
Richiede Docker Desktop e LM Studio accesi, e il file .env.
"""

import subprocess
from pathlib import Path

import pytest
from tzlocal.windows_tz import win_tz

pytestmark = pytest.mark.docker

CARTELLA = Path(__file__).resolve().parent.parent
INGRESSO = "Che ore sono?\nesci\n"
TIMEOUT = 300


def esegui(comando: list[str], ingresso: str = INGRESSO) -> subprocess.CompletedProcess:
    risultato = subprocess.run(
        comando,
        cwd=CARTELLA,
        input=ingresso,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT,
    )
    print(f"\n$ {' '.join(comando)}\n{risultato.stdout}\n{risultato.stderr}")
    return risultato


@pytest.fixture(scope="module", autouse=True)
def immagine():
    subprocess.run(["docker", "compose", "build"], cwd=CARTELLA, check=True, timeout=900)


def fuso_di_windows() -> str:
    uscita = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "(Get-TimeZone).Id"],
        capture_output=True, text=True, check=True,
    )
    return uscita.stdout.strip()


def test_avvio_con_lo_script():
    atteso = win_tz[fuso_di_windows()]
    r = esegui(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "avvia.ps1", "-SenzaTty"])
    assert r.returncode == 0
    assert f"Fuso orario: {atteso} (host Windows)" in r.stdout
    assert "[ora_corrente · mcp:" in r.stdout
    assert "Arrivederci." in r.stdout
    assert "ripiego" not in r.stdout


def test_avvio_senza_lo_script_usa_fuso_orario():
    r = esegui(["docker", "compose", "run", "--rm", "-T", "assistente"])
    assert r.returncode == 0
    assert "(FUSO_ORARIO)" in r.stdout
    assert "Arrivederci." in r.stdout


def test_convertitore_in_docker():
    log_assistente = CARTELLA / "logs" / "assistente.log"
    log_server = CARTELLA / "logs" / "server_mcp.log"
    prima = {p: (p.stat().st_size if p.exists() else 0) for p in (log_assistente, log_server)}
    r = esegui(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "avvia.ps1", "-SenzaTty"],
        ingresso="Quanti metri sono 2,5 km?\nesci\n",
    )
    assert r.returncode == 0
    assert "converti_unita (mcp)" in r.stdout and "[converti_unita · mcp:" in r.stdout
    for percorso, inizio in prima.items():
        with open(percorso, "rb") as file:
            file.seek(inizio)
            assert "tool=converti_unita" in file.read().decode("utf-8", errors="replace"), percorso
