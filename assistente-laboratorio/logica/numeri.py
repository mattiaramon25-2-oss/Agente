"""Uscita dei numeri verso il modello senza falsa esattezza (usata da calcolatrice e convertitore).

Regole:
- valore esatto e intero → int;
- valore esatto che un numero JSON (float) rappresenta senza perdere cifre → float;
- valore esatto con troppe cifre per un float → testo del valore esatto (per esempio
  "123456789012345678.1"): meglio un testo vero che un numero con cifre inventate;
- valore già arrotondato (divisione periodica) → float a 15 cifre significative, MAI int,
  così non sembra un intero esatto.
"""

import math
from decimal import Decimal, localcontext

from logica.errori import ErroreStrumento

CIFRE_SIGNIFICATIVE = 15


def numero_json(valore: Decimal, inesatto: bool) -> int | float | str:
    if not inesatto:
        if valore == valore.to_integral_value():
            return int(valore)
        decimale = float(valore)
        if decimale != 0 and math.isfinite(decimale) and Decimal(repr(decimale)) == valore:
            return decimale
        with localcontext() as contesto:  # normalize() arrotonda alla precisione del contesto
            contesto.prec = max(28, len(valore.as_tuple().digits))
            return str(valore.normalize())
    arrotondato = Decimal(format(valore, f".{CIFRE_SIGNIFICATIVE}g"))
    decimale = float(arrotondato)
    if decimale == 0 and valore != 0:
        raise ErroreStrumento("Risultato troppo piccolo per essere rappresentato.")
    return decimale
