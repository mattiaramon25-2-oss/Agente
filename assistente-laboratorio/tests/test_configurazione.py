import pytest

from assistente.configurazione import Configurazione, ErroreConfigurazione, carica_configurazione


def test_configurazione_completa():
    env = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b", "MCP_PORTA": "8765"}
    assert carica_configurazione(env) == Configurazione("http://localhost:1234/v1", "google/gemma-4-e2b", 8765)


def test_valori_ripuliti_dagli_spazi():
    env = {"LMSTUDIO_BASE_URL": " http://localhost:1234/v1 ", "LMSTUDIO_MODEL": "google/gemma-4-e2b\n", "MCP_PORTA": " 8765 "}
    assert carica_configurazione(env) == Configurazione("http://localhost:1234/v1", "google/gemma-4-e2b", 8765)


def test_variabili_mancanti():
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione({})
    messaggio = str(errore.value)
    assert "LMSTUDIO_BASE_URL" in messaggio
    assert "LMSTUDIO_MODEL" in messaggio
    assert "MCP_PORTA" in messaggio
    assert ".env.example" in messaggio


def test_variabile_vuota():
    env = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "  ", "MCP_PORTA": "8765"}
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione(env)
    assert "LMSTUDIO_MODEL" in str(errore.value)
    assert "LMSTUDIO_BASE_URL" not in str(errore.value)


@pytest.mark.parametrize("valore", ["abc", "80", "70000", "8765.0", "-8765"])
def test_porta_mcp_non_valida(valore):
    env = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "m", "MCP_PORTA": valore}
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione(env)
    assert f"MCP_PORTA non valida: '{valore}'" in str(errore.value) and "tra 1024 e 65535" in str(errore.value)
