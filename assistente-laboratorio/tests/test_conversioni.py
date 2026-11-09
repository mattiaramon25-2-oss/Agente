import math
import pytest
from logica.conversioni import UNITA_AMMESSE, ErroreConversione, converti

def test_risultato_completo():
    assert converti(2.5, "km", "m") == {"valore": 2.5, "da": "km", "a": "m", "risultato": 2500, "grandezza": "lunghezza"}

@pytest.mark.parametrize("valore, da, a, atteso", [
    (0.1, "km", "m", 100), (750, "ml", "l", 0.75), (3, "kg", "g", 3000), (1, "mg", "kg", 1e-06),
    (5, "hl", "cl", 50000), (1, "dag", "dg", 100), (12, "dam", "dm", 1200), (0, "cm", "m", 0),
    (100, "°F", "°C", 37.78), (37, "°C", "°F", 98.6), (-40, "°C", "°F", -40), (0, "°C", "°F", 32),
    (2.5, "km", "km", 2.5), ("2.5", "km", "m", 2500),
])
def test_conversioni(valore, da, a, atteso):
    risultato = converti(valore, da, a)["risultato"]
    assert risultato == atteso and type(risultato) is type(atteso)

def test_grandezze():
    assert [converti(1, u, u)["grandezza"] for u in ("m", "g", "l", "°C")] == ["lunghezza", "massa", "volume", "temperatura"]

def test_elenco_unita():
    assert UNITA_AMMESSE == ("km", "hm", "dam", "m", "dm", "cm", "mm", "kg", "hg", "dag", "g", "dg", "cg", "mg",
                             "hl", "dal", "l", "dl", "cl", "ml", "°C", "°F")

@pytest.mark.parametrize("valore, da, a, frammento", [
    ("2,5", "km", "m", "punto"), ("abc", "km", "m", "non numerico"), (True, "km", "m", "non numerico"),
    (None, "km", "m", "non numerico"), (math.nan, "km", "m", "finito"), (math.inf, "km", "m", "finito"),
    (-1, "km", "m", "negativo"), (-300, "°C", "°F", "zero assoluto"), (-460, "°F", "°C", "zero assoluto"),
    (1, "Km", "m", "Unità sconosciuta"), (1, " km", "m", "Unità sconosciuta"), (1, "m", "C", "Unità sconosciuta"),
    (1, "kg", "m", "grandezze"), (1, "°C", "l", "grandezze"), (1e308, "km", "mm", "troppo grande"),
    (1e30, "°C", "°F", "troppo grande"), (1e30, "°F", "°C", "troppo grande"),
])
def test_errori(valore, da, a, frammento):
    with pytest.raises(ErroreConversione) as errore:
        converti(valore, da, a)
    assert frammento in str(errore.value)

def test_unita_sconosciuta_elenca_le_ammesse():
    with pytest.raises(ErroreConversione) as errore:
        converti(1, "miglia", "m")
    assert "km, hm, dam, m" in str(errore.value) and "°C, °F" in str(errore.value)


def test_interi_lunghi_esatti():
    assert converti(1234567890123456789012345678901, "m", "km")["risultato"] == "1234567890123456789012345678.901"
    assert converti(10**30 + 1, "km", "mm")["risultato"] == 10**36 + 10**6


def test_nessun_artefatto_della_virgola_mobile():
    assert converti(12345678901234567, "mm", "m")["risultato"] == "12345678901234.567"
