import pytest

from assistente.configurazione import Configurazione, ErroreConfigurazione, carica_configurazione


def test_configurazione_completa():
    env = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}
    assert carica_configurazione(env) == Configurazione("http://localhost:1234/v1", "google/gemma-4-e2b")


def test_valori_ripuliti_dagli_spazi():
    env = {"LMSTUDIO_BASE_URL": " http://localhost:1234/v1 ", "LMSTUDIO_MODEL": "google/gemma-4-e2b\n"}
    assert carica_configurazione(env) == Configurazione("http://localhost:1234/v1", "google/gemma-4-e2b")


def test_variabili_mancanti():
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione({})
    messaggio = str(errore.value)
    assert "LMSTUDIO_BASE_URL" in messaggio
    assert "LMSTUDIO_MODEL" in messaggio
    assert ".env.example" in messaggio


def test_variabile_vuota():
    env = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "  "}
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione(env)
    assert "LMSTUDIO_MODEL" in str(errore.value)
    assert "LMSTUDIO_BASE_URL" not in str(errore.value)
