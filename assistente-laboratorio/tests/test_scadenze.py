from datetime import date

import pytest

from logica.errori import ErroreStrumento
from logica.scadenze import PERCORSO_FESTIVITA, calcola_scadenza, carica_festivita


def test_esempio_della_specifica():
    assert calcola_scadenza("2026-12-23", 3, True) == {
        "data_inizio": "2026-12-23", "giorni": 3, "lavorativi": True, "scadenza": "2026-12-29",
        "giorno_settimana": "martedì", "festivita_saltate": ["2026-12-25 Natale", "2026-12-26 Santo Stefano"],
        "nota": "Calcolo indicativo: non ha valore legale."}


@pytest.mark.parametrize("inizio, giorni, lavorativi, scadenza", [
    ("2026-12-23", 3, False, "2026-12-26"), ("2026-11-06", 1, True, "2026-11-09"),   # venerdì → lunedì
    ("2026-11-07", 1, True, "2026-11-09"),                                            # inizio di sabato
    ("2026-04-03", 1, True, "2026-04-07"),                                            # Pasquetta 2026
    ("2026-12-31", 1, True, "2027-01-04"), ("2026-03-10", 0, True, "2026-03-10"),
    ("2028-12-29", 365, False, "2029-12-29"), ("2026-01-30", "3", False, "2026-02-02"),
    ("2026-01-30", 3.0, False, "2026-02-02"),
    ("2027-10-01", 1, True, "2027-10-05"),                                            # 4 ottobre 2027, lunedì
])
def test_scadenze(inizio, giorni, lavorativi, scadenza):
    assert calcola_scadenza(inizio, giorni, lavorativi)["scadenza"] == scadenza


def test_giorni_normalizzati_nel_risultato():
    assert calcola_scadenza("2026-01-30", "3", False)["giorni"] == 3


def test_calendario_senza_festivita_saltate():
    assert calcola_scadenza("2026-12-23", 3, False)["festivita_saltate"] == []


@pytest.mark.parametrize("data", ["2026-02-30", "30/01/2026", "20261223", "2026-1-5", "", None, 20261223, "２026-01-01"])
def test_date_non_valide(data):
    with pytest.raises(ErroreStrumento, match="Data non valida"):
        calcola_scadenza(data, 1, True)


@pytest.mark.parametrize("giorni", [-1, 3651, 2.5, True, "tre", None, "-1", " 3"])
def test_giorni_non_validi(giorni):
    with pytest.raises(ErroreStrumento, match="giorni deve essere"):
        calcola_scadenza("2026-03-10", giorni, True)


@pytest.mark.parametrize("lavorativi", ["true", 1, None])
def test_lavorativi_non_booleano(lavorativi):
    with pytest.raises(ErroreStrumento, match="lavorativi deve essere"):
        calcola_scadenza("2026-03-10", 1, lavorativi)


def test_fuori_dagli_anni_coperti():
    with pytest.raises(ErroreStrumento, match="2026–2028"):
        calcola_scadenza("2028-12-29", 5, True)


def test_file_delle_festivita():
    f = carica_festivita()
    assert PERCORSO_FESTIVITA.name == "festivita_italia.json"
    assert f.anni == {2026, 2027, 2028} and len(f.date) == 36 and f.date[date(2027, 3, 29)] == "Pasquetta"
    # Festa nazionale di San Francesco dal 2026 (legge 8 ottobre 2025, n. 151).
    assert all(f.date[date(anno, 10, 4)] == "San Francesco" for anno in (2026, 2027, 2028))


@pytest.mark.parametrize("inizio, giorni, lavorativi", [("9999-12-31", 1, False), ("9999-01-01", 3650, False), ("9999-12-31", 1, True)])
def test_oltre_la_data_massima(inizio, giorni, lavorativi):
    with pytest.raises(ErroreStrumento, match="data massima"):
        calcola_scadenza(inizio, giorni, lavorativi)
