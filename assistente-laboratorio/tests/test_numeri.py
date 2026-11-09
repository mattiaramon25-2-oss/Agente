"""Uscita dei numeri senza falsa esattezza: intero solo se esatto, testo se un numero JSON perderebbe cifre."""

from decimal import Decimal

import pytest

from logica.errori import ErroreStrumento
from logica.numeri import numero_json


@pytest.mark.parametrize("valore, atteso", [
    (Decimal("14"), 14), (Decimal("2E+3"), 2000), (Decimal("0.3"), 0.3), (Decimal("2.50"), 2.5),
    (Decimal("1E-6"), 1e-06), (Decimal(2 ** 200), 2 ** 200),
])
def test_valori_esatti_rappresentabili(valore, atteso):
    r = numero_json(valore, inesatto=False)
    assert r == atteso and type(r) is type(atteso)


@pytest.mark.parametrize("valore, testo", [
    (Decimal("123456789012345678.1"), "123456789012345678.1"),
    (Decimal("12345678901234.567"), "12345678901234.567"),
    (Decimal("1E-400"), "1E-400"),
])
def test_valori_esatti_con_troppe_cifre_come_testo(valore, testo):
    assert numero_json(valore, inesatto=False) == testo


def test_valore_arrotondato_mai_intero():
    r = numero_json(Decimal(1) / Decimal(7) * Decimal(10) ** 20, inesatto=True)
    assert type(r) is float and r == 1.42857142857143e19


def test_valore_arrotondato_a_15_cifre():
    assert numero_json(Decimal(1) / Decimal(3), inesatto=True) == 0.333333333333333


def test_valore_arrotondato_troppo_piccolo():
    with pytest.raises(ErroreStrumento, match="troppo piccolo"):
        numero_json(Decimal("1E-400") / Decimal(3), inesatto=True)
