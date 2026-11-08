"""Servizio FastAPI delle scadenze, provato con il client di test di FastAPI (senza rete)."""

import logging

import pytest
from fastapi.testclient import TestClient

from logica.scadenze import calcola_scadenza
from servizio_api.app import crea_app


@pytest.fixture
def client():
    return TestClient(crea_app())


def test_scadenza_ok(client, caplog):
    caplog.set_level(logging.INFO, logger="servizio_api")
    r = client.get("/scadenza", params={"data_inizio": "2026-12-23", "giorni": 3, "lavorativi": "true"})
    assert r.status_code == 200 and r.json() == calcola_scadenza("2026-12-23", 3, True)
    assert "endpoint=/scadenza" in caplog.text and "esito=ok" in caplog.text


def test_errore_dello_strumento(client, caplog):
    caplog.set_level(logging.INFO, logger="servizio_api")
    r = client.get("/scadenza", params={"data_inizio": "2026-02-30", "giorni": 1, "lavorativi": "true"})
    assert r.status_code == 400 and r.json()["errore"].startswith("Data non valida")
    assert "esito=errore" in caplog.text


def test_stesso_testo_d_errore_della_logica(client):
    r = client.get("/scadenza", params={"data_inizio": "2028-12-29", "giorni": 5, "lavorativi": "true"})
    assert r.status_code == 400 and "2026–2028" in r.json()["errore"]


@pytest.mark.parametrize("params", [
    {"giorni": 1, "lavorativi": "true"},
    {"data_inizio": "2026-03-10", "giorni": "tre", "lavorativi": "true"},
    {"data_inizio": "2026-03-10", "giorni": 1, "lavorativi": "forse"},
])
def test_errori_di_tipo_in_italiano(client, params):
    r = client.get("/scadenza", params=params)
    assert r.status_code == 400 and r.json()["errore"].startswith("Argomenti non validi per calcola_scadenza")


def test_errore_di_tipo_nomina_il_parametro(client):
    r = client.get("/scadenza", params={"giorni": 1, "lavorativi": "true"})
    assert "data_inizio: mancante" in r.json()["errore"]


def test_openapi_descrive_scadenza(client):
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Servizio scadenze" and "/scadenza" in schema["paths"]
