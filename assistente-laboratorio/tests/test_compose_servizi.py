"""I quattro servizi di compose.yaml accesi da `docker compose up -d`: solo `docker compose config`, nessun container."""
import json
import os
import subprocess

import pytest

from tests.compose_prova import CARTELLA, ENV_FINTO

pytestmark = pytest.mark.docker

VARIABILI_DA_TOGLIERE = (
    "FRONTEND_PORTA", "BACKEND_PORTA", "BACKEND_INDIRIZZO", "BACKEND_HOST", "AGENTE_INDIRIZZO",
    "POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_PORTA",
)
ENV_PROVA = {**ENV_FINTO, "BACKEND_PORTA": "8768"}


def _servizi(tmp_path, variabili: dict | None = None) -> dict:
    """I servizi di `docker compose config`, con i profili `cli` e `test` attivi perché compaiano anche quelli."""
    file_env = tmp_path / "prova.env"
    contenuto = {**ENV_PROVA, **(variabili or {})}
    file_env.write_text("\n".join(f"{k}={v}" for k, v in contenuto.items()) + "\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in VARIABILI_DA_TOGLIERE and k not in ENV_FINTO}
    risultato = subprocess.run(
        ["docker", "compose", "--env-file", str(file_env), "--profile", "cli", "--profile", "test",
         "config", "--format", "json"],
        cwd=CARTELLA, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    assert risultato.returncode == 0, risultato.stderr
    return json.loads(risultato.stdout)["services"]


def test_quattro_servizi_senza_profilo(tmp_path):
    servizi = _servizi(tmp_path)
    senza_profilo = {nome for nome, servizio in servizi.items() if "profiles" not in servizio}
    assert senza_profilo == {"database", "agente", "backend", "frontend"}
    assert servizi["assistente"]["profiles"] == ["cli"]
    assert servizi["test"]["profiles"] == ["test"]


def test_backend_senza_porte_e_indirizzi_di_docker(tmp_path):
    backend = _servizi(tmp_path)["backend"]
    assert not backend.get("ports"), "il back-end non deve pubblicare porte: ci arriva solo nginx"
    ambiente = backend["environment"]
    assert ambiente["BACKEND_HOST"] == "0.0.0.0"
    assert ambiente["POSTGRES_HOST"] == "database"
    assert ambiente["POSTGRES_PORTA"] == "5432"
    assert ambiente["AGENTE_INDIRIZZO"] == "agente"
    assert backend["depends_on"]["database"]["condition"] == "service_healthy"


def test_riavvio_e_healthcheck(tmp_path):
    servizi = _servizi(tmp_path)
    for nome in ("agente", "backend"):
        assert servizi[nome].get("restart") == "on-failure", nome
        assert servizi[nome].get("healthcheck", {}).get("test"), nome
    for nome in ("database", "frontend"):
        assert "restart" not in servizi[nome], nome


def test_porte_solo_su_127(tmp_path):
    servizi = _servizi(tmp_path)
    porte = [(nome, p) for nome, servizio in servizi.items() for p in servizio.get("ports", [])]
    assert porte, "almeno un servizio pubblica una porta"
    for nome, porta in porte:
        assert porta.get("host_ip") == "127.0.0.1", (nome, porta)


def test_frontend_indirizzo_del_backend(tmp_path):
    assert _servizi(tmp_path)["frontend"]["environment"]["BACKEND_INDIRIZZO"] == "backend"
    altro = _servizi(tmp_path, {"BACKEND_INDIRIZZO": "host.docker.internal"})
    assert altro["frontend"]["environment"]["BACKEND_INDIRIZZO"] == "host.docker.internal"
