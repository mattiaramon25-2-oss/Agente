"""Logica pura del convertitore di unità: nessuna dipendenza da MCP."""

import math
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from logica.errori import ErroreStrumento
from logica.numeri import numero_json

# Esponente di 10 rispetto all'unità base di ogni grandezza.
_METRICHE = {
    "lunghezza": {"km": 3, "hm": 2, "dam": 1, "m": 0, "dm": -1, "cm": -2, "mm": -3},
    "massa": {"kg": 3, "hg": 2, "dag": 1, "g": 0, "dg": -1, "cg": -2, "mg": -3},
    "volume": {"hl": 2, "dal": 1, "l": 0, "dl": -1, "cl": -2, "ml": -3},
}
_TEMPERATURE = ("°C", "°F")
_MINIMO = {"°C": Decimal("-273.15"), "°F": Decimal("-459.67")}

UNITA_AMMESSE = tuple(u for unita in _METRICHE.values() for u in unita) + _TEMPERATURE

_GRANDEZZA = {u: g for g, unita in _METRICHE.items() for u in unita}
_GRANDEZZA.update({u: "temperatura" for u in _TEMPERATURE})


class ErroreConversione(ErroreStrumento):
    """Richiesta di conversione non valida, con messaggio per il modello."""


def _leggi_valore(valore: object) -> tuple[int | float, Decimal]:
    """Interpreta il valore e lo restituisce come numero e come Decimal."""
    if isinstance(valore, bool):
        raise ErroreConversione("Valore non numerico: un booleano non è un numero.")
    if isinstance(valore, int):
        return valore, Decimal(valore)
    if isinstance(valore, str) and "," in valore:
        raise ErroreConversione("Valore non valido: usa il punto come separatore decimale, per esempio 2.5.")
    try:
        numero = float(valore)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        raise ErroreConversione(f"Valore non numerico: {valore!r}.") from None
    if not math.isfinite(numero):
        raise ErroreConversione("Il valore deve essere un numero finito.")
    return numero, Decimal(repr(numero))


def _controlla_unita(unita: object) -> None:
    if not isinstance(unita, str) or unita not in _GRANDEZZA:
        raise ErroreConversione(f"Unità sconosciuta: '{unita}'. Unità ammesse: {', '.join(UNITA_AMMESSE)}.")


def _calcola(x: Decimal, da: str, a: str, grandezza: str) -> Decimal:
    if da == a:
        return x
    if grandezza == "temperatura":
        if da == "°C":
            return (x * 9 / 5 + 32).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return ((x - 32) * 5 / 9).quantize(Decimal("0.01"), ROUND_HALF_UP)
    tabella = _METRICHE[grandezza]
    with localcontext() as contesto:  # le potenze di 10 sono esatte: nessun arrotondamento a 28 cifre
        contesto.prec = 400
        return x.scaleb(tabella[da] - tabella[a])


def converti(valore: object, da: object, a: object) -> dict:
    """Converte `valore` da `da` ad `a`; solleva ErroreConversione se non è valido."""
    numero, x = _leggi_valore(valore)
    _controlla_unita(da)
    _controlla_unita(a)
    grandezza = _GRANDEZZA[da]
    if grandezza != _GRANDEZZA[a]:
        raise ErroreConversione(f"Le unità '{da}' e '{a}' appartengono a grandezze diverse: conversione impossibile.")
    if grandezza == "temperatura":
        if x < _MINIMO[da]:
            raise ErroreConversione(f"Temperatura sotto lo zero assoluto ({_MINIMO[da]} {da}).")
    elif x < 0:
        raise ErroreConversione(f"Valore negativo non ammesso per {grandezza}.")

    try:
        risultato = _calcola(x, da, a, grandezza)
    except InvalidOperation:  # arrotondamento oltre la precisione del contesto
        raise ErroreConversione("Risultato troppo grande per essere rappresentato.") from None
    try:
        decimale = float(risultato)
    except OverflowError:
        decimale = math.inf
    if not math.isfinite(decimale):
        raise ErroreConversione("Risultato troppo grande per essere rappresentato.")
    # Esatto: intero, numero decimale o, se un float perderebbe cifre, il testo del valore esatto.
    uscita = numero_json(risultato, inesatto=False)
    return {"valore": numero, "da": da, "a": a, "risultato": uscita, "grandezza": grandezza}
