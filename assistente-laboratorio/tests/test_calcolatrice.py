import pytest

from logica.calcolatrice import ESPONENTE_MASSIMO, LUNGHEZZA_MASSIMA, calcola
from logica.errori import ErroreStrumento


def test_costanti():
    assert (LUNGHEZZA_MASSIMA, ESPONENTE_MASSIMO) == (200, 1000)


@pytest.mark.parametrize("espressione, atteso", [
    ("(3 + 4) * 2", 14), ("0.1 + 0.2", 0.3), ("2 + 3 * 4", 14), ("2 ** 3 ** 2", 512), ("-2 ** 2", -4),
    ("10 / 4", 2.5), ("1 / 3", 0.333333333333333), ("7 % 3", 1), ("-7 % 3", -1), ("4 / 2", 2),
    ("2 ** -1", 0.5), ("  5  ", 5), ("+3", 3),
])
def test_calcoli(espressione, atteso):
    r = calcola(espressione)
    assert r == {"espressione": espressione, "risultato": atteso} and type(r["risultato"]) is type(atteso)


@pytest.mark.parametrize("espressione, frammento", [
    ("__import__('os')", "non consentit"), ("().__class__", "non consentit"), ("abs(-1)", "non consentit"),
    ("1_000 + 1", "non consentit"), ("1e3", "non consentit"), ("0x10", "non consentit"), ("7 // 2", "non consentit"),
    ("2,5 + 1", "punto"), ("", "vuota"), ("   ", "vuota"), ("1+" * 101 + "1", "200 caratteri"),
    ("(1 + 2", "sintassi"), ("1 / 0", "zero"), ("5 % 0", "zero"), ("0 ** -1", "Divisione per zero"),
    ("2 ** 0.5", "Esponente"), ("2 ** 10000", "Esponente"), ("9 ** 9 ** 9", "Esponente"),
    ("10 ** 999 * 10 ** 999", "troppo grande"),
])
def test_rifiuti(espressione, frammento):
    with pytest.raises(ErroreStrumento, match=frammento):
        calcola(espressione)


@pytest.mark.parametrize("valore", [None, 14, True, ["1+1"]])
def test_non_testo(valore):
    with pytest.raises(ErroreStrumento, match="testo"):
        calcola(valore)


@pytest.mark.parametrize("espressione, atteso", [
    ("2 ** 200", 2 ** 200), ("10 ** 60 + 1", 10 ** 60 + 1), ("10 ** 60 % 7", 10 ** 60 % 7),
    ("99999999999999999999999999 * 99999999999999999999999999", 99999999999999999999999999 ** 2),
])
def test_interi_grandi_esatti(espressione, atteso):
    assert calcola(espressione)["risultato"] == atteso
