import pytest

from assistente.fuso import RisultatoFuso, rileva_fuso


def non_chiamare():
    raise AssertionError("fuso_locale non doveva essere chiamato")


def test_host_windows():
    r = rileva_fuso({"FUSO_HOST_WINDOWS": "W. Europe Standard Time"}, non_chiamare)
    assert r == RisultatoFuso("Europe/Berlin", "host Windows", None)


def test_host_windows_tokyo():
    r = rileva_fuso({"FUSO_HOST_WINDOWS": "Tokyo Standard Time"}, non_chiamare)
    assert r == RisultatoFuso("Asia/Tokyo", "host Windows", None)


def test_locale_fuori_da_docker():
    r = rileva_fuso({}, lambda: "Europe/Rome")
    assert r == RisultatoFuso("Europe/Rome", "computer locale", None)


def test_docker_salta_il_locale():
    r = rileva_fuso({"ASSISTENTE_IN_DOCKER": "1", "FUSO_ORARIO": "Europe/Rome"}, non_chiamare)
    assert r.fuso == "Europe/Rome" and r.origine == "FUSO_ORARIO"
    assert r.avviso is None


def test_host_windows_sconosciuto():
    env = {"FUSO_HOST_WINDOWS": "Fuso Inventato", "ASSISTENTE_IN_DOCKER": "1", "FUSO_ORARIO": "Asia/Tokyo"}
    r = rileva_fuso(env, non_chiamare)
    assert r == RisultatoFuso("Asia/Tokyo", "FUSO_ORARIO", None)


def solleva():
    raise OSError("rilevamento non riuscito")


@pytest.mark.parametrize("fuso_locale", [solleva, lambda: None, lambda: "Roma"])
def test_locale_fallisce(fuso_locale):
    r = rileva_fuso({"FUSO_ORARIO": "Europe/Rome"}, fuso_locale)
    assert r == RisultatoFuso("Europe/Rome", "FUSO_ORARIO", None)


def test_ripiego_utc():
    r = rileva_fuso({"ASSISTENTE_IN_DOCKER": "1", "FUSO_ORARIO": "Roma"}, non_chiamare)
    assert r.fuso == "UTC" and r.origine == "ripiego"
    assert "avvia.ps1" in r.avviso and "FUSO_ORARIO" in r.avviso
