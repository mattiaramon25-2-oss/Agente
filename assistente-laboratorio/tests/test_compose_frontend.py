"""Il servizio `frontend` di compose.yaml: solo `docker compose config`, nessun container."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.postgres_prova import ENV_FINTO

pytestmark = pytest.mark.docker

CARTELLA = Path(__file__).resolve().parent.parent
VARIABILI_DA_TOGLIERE = ("FRONTEND_PORTA", "BACKEND_PORTA", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_PORTA")


def _config(tmp_path, variabili: dict) -> subprocess.CompletedProcess:
    """`docker compose config` con un .env temporaneo e un ambiente senza le variabili del front-end e di PostgreSQL."""
    file_env = tmp_path / "prova.env"
    file_env.write_text("\n".join(f"{k}={v}" for k, v in variabili.items()) + "\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in VARIABILI_DA_TOGLIERE and k not in ENV_FINTO}
    return subprocess.run(
        ["docker", "compose", "--env-file", str(file_env), "config", "--format", "json"],
        cwd=CARTELLA, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )


def test_frontend_solo_su_127(tmp_path):
    risultato = _config(tmp_path, {**ENV_FINTO, "FRONTEND_PORTA": "8780"})
    assert risultato.returncode == 0, risultato.stderr
    porte = json.loads(risultato.stdout)["services"]["frontend"]["ports"]
    assert porte, "il servizio frontend deve pubblicare una porta"
    assert all(p["host_ip"] == "127.0.0.1" for p in porte)
    assert porte[0]["target"] == 8080 and str(porte[0]["published"]) == "8780"


def test_config_senza_frontend_porta(tmp_path):
    """Senza FRONTEND_PORTA, BACKEND_PORTA né POSTGRES_* la configurazione resta valida, con i valori predefiniti."""
    risultato = _config(tmp_path, ENV_FINTO)
    assert risultato.returncode == 0, risultato.stderr
    frontend = json.loads(risultato.stdout)["services"]["frontend"]
    assert str(frontend["ports"][0]["published"]) == "8780"
    assert frontend["environment"]["BACKEND_PORTA"] == "8768"
