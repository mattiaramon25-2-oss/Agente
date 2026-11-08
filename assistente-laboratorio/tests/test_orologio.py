from datetime import datetime, timezone

import pytest

from logica.conversioni import ErroreConversione
from logica.errori import ErroreStrumento
from logica.orologio import ora_corrente, ora_utc, è_fuso_valido

ISTANTE = datetime(2026, 11, 2, 14, 4, 5, tzinfo=timezone.utc)  # lunedì


def test_ora_a_roma():
    assert ora_corrente("Europe/Rome", ISTANTE) == {
        "fuso": "Europe/Rome",
        "data_ora": "2026-11-02T15:04:05+01:00",
        "scarto_utc": "+01:00",
        "giorno_settimana": "lunedì",
    }


def test_ora_a_tokyo():
    r = ora_corrente("Asia/Tokyo", ISTANTE)
    assert r["data_ora"] == "2026-11-02T23:04:05+09:00"
    assert r["scarto_utc"] == "+09:00"


def test_ora_a_new_york():
    assert ora_corrente("America/New_York", ISTANTE)["data_ora"] == "2026-11-02T09:04:05-05:00"


def test_ora_legale():
    r = ora_corrente("Europe/Rome", datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc))
    assert r["data_ora"] == "2026-07-01T14:00:00+02:00"


@pytest.mark.parametrize("fuso", ["Mars/Olympus", "Roma", "europe/rome", "../../etc/passwd", "", None, 3])
def test_fuso_non_valido(fuso):
    with pytest.raises(ErroreStrumento, match="Fuso orario sconosciuto") as errore:
        ora_corrente(fuso, ISTANTE)
    assert "Europe/Rome" in str(errore.value)


def test_ora_utc_è_l_ora_attuale():
    assert abs((datetime.now(timezone.utc) - ora_utc()).total_seconds()) < 5
    assert ora_utc().utcoffset().total_seconds() == 0


def test_è_fuso_valido():
    assert è_fuso_valido("Europe/Rome") and è_fuso_valido("UTC")
    for nome in ("Roma", "", "../x", None, 3):
        assert not è_fuso_valido(nome)


def test_errore_conversione_e_errore_strumento():
    assert issubclass(ErroreConversione, ErroreStrumento)
