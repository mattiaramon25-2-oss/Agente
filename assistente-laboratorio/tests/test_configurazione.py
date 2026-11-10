import pytest

from assistente.configurazione import Configurazione, ErroreConfigurazione, carica_configurazione


def test_configurazione_completa():
    env = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b", "MCP_PORTA": "8765", "VARIANTE_CALCOLATRICE": "mcp", "VARIANTE_SCADENZE": "mcp"}
    assert carica_configurazione(env) == Configurazione("http://localhost:1234/v1", "google/gemma-4-e2b", 8765)


def test_valori_ripuliti_dagli_spazi():
    env = {"LMSTUDIO_BASE_URL": " http://localhost:1234/v1 ", "LMSTUDIO_MODEL": "google/gemma-4-e2b\n", "MCP_PORTA": " 8765 ", "VARIANTE_CALCOLATRICE": "mcp", "VARIANTE_SCADENZE": "mcp"}
    assert carica_configurazione(env) == Configurazione("http://localhost:1234/v1", "google/gemma-4-e2b", 8765)


def test_variabili_mancanti():
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione({})
    messaggio = str(errore.value)
    assert "LMSTUDIO_BASE_URL" in messaggio
    assert "LMSTUDIO_MODEL" in messaggio
    assert "MCP_PORTA" in messaggio
    assert "VARIANTE_CALCOLATRICE" in messaggio
    assert "VARIANTE_SCADENZE" in messaggio
    assert ".env.example" in messaggio
    # Chi ha già un .env non deve sovrascriverlo: il messaggio chiede di aggiungere, non di copiare.
    assert "Copia .env.example in .env" not in messaggio
    assert "Aggiungi" in messaggio


def test_variabile_vuota():
    env = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "  ", "MCP_PORTA": "8765", "VARIANTE_CALCOLATRICE": "mcp", "VARIANTE_SCADENZE": "mcp"}
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione(env)
    assert "LMSTUDIO_MODEL" in str(errore.value)
    assert "LMSTUDIO_BASE_URL" not in str(errore.value)


@pytest.mark.parametrize("valore", ["abc", "80", "70000", "8765.0", "-8765"])
def test_porta_mcp_non_valida(valore):
    env = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "m", "MCP_PORTA": valore, "VARIANTE_CALCOLATRICE": "mcp", "VARIANTE_SCADENZE": "mcp"}
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione(env)
    assert f"MCP_PORTA non valida: '{valore}'" in str(errore.value) and "tra 1024 e 65535" in str(errore.value)


BASE = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "m", "MCP_PORTA": "8765", "VARIANTE_SCADENZE": "mcp"}


@pytest.mark.parametrize("valore, atteso", [("mcp", "mcp"), ("MCP", "mcp"), (" locale ", "locale")])
def test_variante_calcolatrice(valore, atteso):
    assert carica_configurazione({**BASE, "VARIANTE_CALCOLATRICE": valore}).variante_calcolatrice == atteso


def test_variante_calcolatrice_non_valida():
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione({**BASE, "VARIANTE_CALCOLATRICE": "remoto"})
    assert str(errore.value) == "VARIANTE_CALCOLATRICE non valida: 'remoto'. Valori ammessi: mcp, locale."


COMPLETA = {**BASE, "VARIANTE_CALCOLATRICE": "mcp"}


def test_variante_scadenze_fastapi_con_porta():
    config = carica_configurazione({**COMPLETA, "VARIANTE_SCADENZE": " FastAPI ", "API_PORTA": "8766"})
    assert (config.variante_scadenze, config.porta_api) == ("fastapi", 8766)


def test_variante_scadenze_non_valida():
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione({**COMPLETA, "VARIANTE_SCADENZE": "http"})
    assert str(errore.value) == "VARIANTE_SCADENZE non valida: 'http'. Valori ammessi: mcp, fastapi."


def test_fastapi_senza_porta():
    with pytest.raises(ErroreConfigurazione, match="API_PORTA"):
        carica_configurazione({**COMPLETA, "VARIANTE_SCADENZE": "fastapi"})


@pytest.mark.parametrize("valore", ["abc", "80", "70000"])
def test_porta_api_non_valida(valore):
    with pytest.raises(ErroreConfigurazione, match=f"API_PORTA non valida: '{valore}'"):
        carica_configurazione({**COMPLETA, "VARIANTE_SCADENZE": "fastapi", "API_PORTA": valore})


def test_porta_api_uguale_a_quella_mcp():
    with pytest.raises(ErroreConfigurazione) as errore:
        carica_configurazione({**COMPLETA, "VARIANTE_SCADENZE": "fastapi", "API_PORTA": "8765"})
    assert str(errore.value) == "API_PORTA deve essere diversa da MCP_PORTA."


def test_con_mcp_la_porta_api_e_ignorata():
    config = carica_configurazione({**COMPLETA, "VARIANTE_SCADENZE": "mcp", "API_PORTA": "non valida"})
    assert (config.variante_scadenze, config.porta_api) == ("mcp", None)


def test_porta_agente():
    from assistente.configurazione import leggi_porta_agente

    config = Configurazione("http://x/v1", "m", 8765, variante_scadenze="fastapi", porta_api=8766)
    assert leggi_porta_agente({"AGENTE_PORTA": " 8767 "}, config) == 8767
    for valore, testo in [("", "AGENTE_PORTA=8767"), ("80", "tra 1024 e 65535"), ("abc", "tra 1024 e 65535"),
                          ("8765", "diversa da MCP_PORTA"), ("8766", "diversa da API_PORTA")]:
        with pytest.raises(ErroreConfigurazione, match=testo):
            leggi_porta_agente({"AGENTE_PORTA": valore}, config)
    with pytest.raises(ErroreConfigurazione, match="AGENTE_PORTA"):
        leggi_porta_agente({}, config)
