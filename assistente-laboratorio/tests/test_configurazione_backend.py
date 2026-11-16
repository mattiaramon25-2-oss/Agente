import pytest

from assistente.configurazione import ErroreConfigurazione
from servizio_backend.configurazione import ConfigurazioneBackend, carica_configurazione_backend

BASE = {
    "BACKEND_PORTA": "8768",
    "AGENTE_PORTA": "8767",
    "POSTGRES_USER": "assistente",
    "POSTGRES_PASSWORD": "segreta",
    "POSTGRES_DB": "assistente",
}


def test_valori_completi():
    config = carica_configurazione_backend(BASE)
    assert isinstance(config, ConfigurazioneBackend)
    assert config.porta == 8768
    assert config.url_agente == "http://127.0.0.1:8767"
    assert config.porta_postgres == 5432
    assert "host=127.0.0.1" in config.dsn
    assert "dbname=assistente" in config.dsn
    assert "port=5432" in config.dsn
    assert "connect_timeout=5" in config.dsn


def test_manca_la_password():
    env = {k: v for k, v in BASE.items() if k != "POSTGRES_PASSWORD"}
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione_backend(env)
    assert "POSTGRES_PASSWORD" in str(errore.value)
    assert "scegli tu una password" in str(errore.value)


def test_porta_uguale_a_quella_dell_agente():
    with pytest.raises(ErroreConfigurazione):
        carica_configurazione_backend({**BASE, "BACKEND_PORTA": "8767"})


def test_porta_uguale_a_mcp():
    with pytest.raises(ErroreConfigurazione):
        carica_configurazione_backend({**BASE, "MCP_PORTA": "8768"})


def test_porta_uguale_a_api():
    with pytest.raises(ErroreConfigurazione):
        carica_configurazione_backend({**BASE, "API_PORTA": "8768"})


def test_porta_postgres_facoltativa_e_letta():
    assert carica_configurazione_backend({**BASE, "POSTGRES_PORTA": "5433"}).porta_postgres == 5433


def test_porta_postgres_non_valida():
    with pytest.raises(ErroreConfigurazione):
        carica_configurazione_backend({**BASE, "POSTGRES_PORTA": "abc"})


def test_indirizzi_predefiniti():
    config = carica_configurazione_backend(BASE)
    assert config.host == "127.0.0.1"
    assert config.url_agente == "http://127.0.0.1:8767"
    assert "host=127.0.0.1" in config.dsn


def test_indirizzi_di_docker():
    env = {**BASE, "BACKEND_HOST": "0.0.0.0", "POSTGRES_HOST": "database", "AGENTE_INDIRIZZO": "agente"}
    config = carica_configurazione_backend(env)
    assert config.host == "0.0.0.0"
    assert config.url_agente == "http://agente:8767"
    assert "host=database" in config.dsn
    assert config.host_postgres == "database"


def test_backend_host_non_ip():
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione_backend({**BASE, "BACKEND_HOST": "localhost"})
    assert "BACKEND_HOST" in str(errore.value)


def test_spazi_contano_come_vuoti():
    config = carica_configurazione_backend({**BASE, "POSTGRES_HOST": "  "})
    assert config.host_postgres == "127.0.0.1"


def test_valori_senza_psycopg():
    import subprocess
    import sys

    risultato = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from servizio_backend.configurazione import leggi_valori_backend; print('psycopg' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert risultato.stdout.strip() == "False"
