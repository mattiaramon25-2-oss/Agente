import json
from datetime import datetime, timezone

import pytest

from assistente.strumenti import NOME_OROLOGIO, crea_strumento_orologio, è_fuso_valido

ISTANTE = datetime(2026, 11, 2, 14, 4, 5, tzinfo=timezone.utc)  # lunedì


def chiedi(fuso, adesso=ISTANTE):
    orologio = crea_strumento_orologio(lambda: adesso)
    return json.loads(orologio.invoke({"fuso": fuso}))


def test_ora_a_roma():
    r = chiedi("Europe/Rome")
    assert r == {
        "fuso": "Europe/Rome",
        "data_ora": "2026-11-02T15:04:05+01:00",
        "scarto_utc": "+01:00",
        "giorno_settimana": "lunedì",
    }


def test_ora_a_tokyo():
    r = chiedi("Asia/Tokyo")
    assert r["data_ora"] == "2026-11-02T23:04:05+09:00"
    assert r["scarto_utc"] == "+09:00"


def test_ora_a_new_york():
    r = chiedi("America/New_York")
    assert r["data_ora"] == "2026-11-02T09:04:05-05:00"


def test_ora_legale():
    r = chiedi("Europe/Rome", datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc))
    assert r["data_ora"] == "2026-07-01T14:00:00+02:00"


@pytest.mark.parametrize("fuso", ["Roma", "", "../../etc/passwd", "europe/rome"])
def test_fusi_non_validi(fuso):
    r = chiedi(fuso)
    assert set(r) == {"errore"}
    assert "Europe/Rome" in r["errore"]


def test_nome_e_argomenti():
    orologio = crea_strumento_orologio(lambda: ISTANTE)
    assert orologio.name == "ora_corrente" == NOME_OROLOGIO
    assert list(orologio.args) == ["fuso"]


def test_orologio_predefinito_usa_l_ora_attuale():
    r = json.loads(crea_strumento_orologio().invoke({"fuso": "UTC"}))
    istante = datetime.fromisoformat(r["data_ora"])
    assert abs((datetime.now(timezone.utc) - istante).total_seconds()) < 5


def test_è_fuso_valido():
    assert è_fuso_valido("Europe/Rome")
    assert è_fuso_valido("UTC")
    for nome in ("Roma", "", "../x"):
        assert not è_fuso_valido(nome)
