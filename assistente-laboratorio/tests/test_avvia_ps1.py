"""avvia.ps1 con un docker finto: l'avviso sulle note condivise compare solo con l'agente della chat acceso."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="avvia.ps1 gira con PowerShell su Windows")

PROGETTO = Path(__file__).resolve().parent.parent

# Il docker finto annota i suoi argomenti; a «compose ps» risponde con l'elenco dei servizi accesi
# (SERVIZI_FINTI) o fallisce come con Docker spento (PS_FALLISCE); «compose run» esce con CODICE_RUN.
DOCKER_FINTO = r"""@echo off
echo %*>>"%~dp0argomenti.txt"
if "%2"=="ps" goto ps
if defined CODICE_RUN exit /b %CODICE_RUN%
exit /b 0
:ps
if defined PS_FALLISCE (
  echo error during connect: Docker spento 1>&2
  exit /b 1
)
if defined SERVIZI_FINTI echo %SERVIZI_FINTI%
exit /b 0
"""


def avvia(tmp_path: Path, ingresso: str = "", *opzioni: str, **variabili: str) -> tuple[subprocess.CompletedProcess, str]:
    shutil.copy(PROGETTO / "avvia.ps1", tmp_path / "avvia.ps1")
    (tmp_path / "docker.cmd").write_text(DOCKER_FINTO, encoding="ascii")
    ambiente = {k: v for k, v in os.environ.items() if k not in ("SERVIZI_FINTI", "PS_FALLISCE", "CODICE_RUN")}
    ambiente["PATH"] = f"{tmp_path}{os.pathsep}{ambiente.get('PATH', '')}"
    ambiente.update(variabili)
    risultato = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(tmp_path / "avvia.ps1"), *opzioni],
        input=ingresso,
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=60,
    )
    file_argomenti = tmp_path / "argomenti.txt"
    argomenti = file_argomenti.read_text(encoding="mbcs") if file_argomenti.exists() else ""
    return risultato, argomenti


def test_agente_acceso_avvisa_e_rispetta_il_no(tmp_path):
    r, argomenti = avvia(tmp_path, "N\n", SERVIZI_FINTI="agente")
    assert "note" in r.stdout and "archivio" in r.stdout
    assert "(S/N)" in r.stdout
    assert "ps --status running --services" in argomenti
    assert " run " not in f" {argomenti} "
    assert r.returncode == 0, r.stderr


def test_agente_acceso_e_si_apre_la_cli(tmp_path):
    r, argomenti = avvia(tmp_path, "S\n", SERVIZI_FINTI="agente")
    assert "archivio" in r.stdout
    assert "run --rm" in argomenti
    assert r.returncode == 0, r.stderr


def test_risposta_minuscola_apre_la_cli(tmp_path):
    r, argomenti = avvia(tmp_path, "s\n", SERVIZI_FINTI="agente")
    assert "run --rm" in argomenti


def test_risposta_vuota_vale_no(tmp_path):
    r, argomenti = avvia(tmp_path, "\n", SERVIZI_FINTI="agente")
    assert "run --rm" not in argomenti
    assert r.returncode == 0, r.stderr


def test_agente_spento_nessuna_domanda(tmp_path):
    r, argomenti = avvia(tmp_path, "")
    assert "archivio" not in r.stdout and "(S/N)" not in r.stdout
    assert "run --rm" in argomenti


def test_altri_servizi_accesi_nessuna_domanda(tmp_path):
    r, argomenti = avvia(tmp_path, "", SERVIZI_FINTI="database")
    assert "(S/N)" not in r.stdout
    assert "run --rm" in argomenti


def test_senza_tty_non_chiede(tmp_path):
    r, argomenti = avvia(tmp_path, "", "-SenzaTty", SERVIZI_FINTI="agente")
    assert "(S/N)" not in r.stdout
    assert "run --rm -T" in argomenti


def test_docker_spento_prosegue_con_la_cli(tmp_path):
    r, argomenti = avvia(tmp_path, "", PS_FALLISCE="1", SERVIZI_FINTI="agente")
    assert "(S/N)" not in r.stdout
    assert "run --rm" in argomenti


def test_codice_di_uscita_resta_quello_di_docker(tmp_path):
    r, argomenti = avvia(tmp_path, "S\n", SERVIZI_FINTI="agente", CODICE_RUN="3")
    assert "run --rm" in argomenti
    assert r.returncode == 3
