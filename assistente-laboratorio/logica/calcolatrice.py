"""Calcolatrice sicura: espressioni aritmetiche senza eval, solo operazioni consentite.

L'espressione viene analizzata con `ast` e valutata visitando una lista chiusa di nodi;
qualsiasi altro costrutto (nomi, chiamate, attributi, //) è rifiutato con un messaggio.
L'aritmetica è decimale esatta, come nel convertitore: 0.1 + 0.2 dà 0.3.
"""

import ast
from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow, localcontext

from logica.errori import ErroreStrumento

LUNGHEZZA_MASSIMA = 200
ESPONENTE_MASSIMO = 1000
LIMITE_RISULTATO = Decimal("1e300")
CIFRE_SIGNIFICATIVE = 15
CARATTERI_AMMESSI = set("0123456789.+-*/%() ")

_BINARI = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow)
_UNARI = (ast.USub, ast.UAdd)


def _controlla(valore: Decimal) -> Decimal:
    if abs(valore) >= LIMITE_RISULTATO:
        raise ErroreStrumento("Risultato troppo grande.")
    return valore


def _potenza(base: Decimal, esponente: Decimal) -> Decimal:
    if esponente != esponente.to_integral_value() or abs(esponente) > ESPONENTE_MASSIMO:
        raise ErroreStrumento(
            f"Esponente non ammesso: deve essere un intero tra -{ESPONENTE_MASSIMO} e {ESPONENTE_MASSIMO}."
        )
    if base == 0 and esponente < 0:  # Decimal darebbe Infinity, non un errore
        raise ErroreStrumento("Divisione per zero.")
    return base ** esponente


def _valuta(nodo: ast.AST, testo: str) -> Decimal:
    if isinstance(nodo, ast.Expression):
        return _valuta(nodo.body, testo)
    if isinstance(nodo, ast.Constant) and type(nodo.value) in (int, float):
        return Decimal(ast.get_source_segment(testo, nodo))
    if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, _UNARI):
        valore = _valuta(nodo.operand, testo)
        return -valore if isinstance(nodo.op, ast.USub) else valore
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, _BINARI):
        sinistro = _valuta(nodo.left, testo)
        destro = _valuta(nodo.right, testo)
        if isinstance(nodo.op, (ast.Div, ast.Mod)) and destro == 0:
            raise ErroreStrumento("Divisione per zero.")
        if isinstance(nodo.op, ast.Add):
            return _controlla(sinistro + destro)
        if isinstance(nodo.op, ast.Sub):
            return _controlla(sinistro - destro)
        if isinstance(nodo.op, ast.Mult):
            return _controlla(sinistro * destro)
        if isinstance(nodo.op, ast.Div):
            return _controlla(sinistro / destro)
        if isinstance(nodo.op, ast.Mod):
            return _controlla(sinistro % destro)
        return _controlla(_potenza(sinistro, destro))
    raise ErroreStrumento("Operazione non consentita.")


def _numero(valore: Decimal) -> int | float:
    """Intero esatto senza .0; altrimenti arrotondato a 15 cifre significative."""
    if valore == valore.to_integral_value():
        return int(valore)
    arrotondato = Decimal(format(valore, f".{CIFRE_SIGNIFICATIVE}g"))
    if arrotondato == arrotondato.to_integral_value():
        return int(arrotondato)
    return float(arrotondato)


def calcola(espressione: object) -> dict:
    """Calcola `espressione`; solleva ErroreStrumento se non è un'espressione ammessa."""
    if not isinstance(espressione, str):
        raise ErroreStrumento("L'espressione deve essere un testo.")
    testo = espressione.strip()
    if not testo:
        raise ErroreStrumento("Espressione vuota.")
    if len(espressione) > LUNGHEZZA_MASSIMA:
        raise ErroreStrumento(f"Espressione troppo lunga: al massimo {LUNGHEZZA_MASSIMA} caratteri.")
    if "," in testo:
        raise ErroreStrumento("Usa il punto come separatore decimale, per esempio 2.5.")
    for carattere in testo:
        if carattere not in CARATTERI_AMMESSI:
            raise ErroreStrumento(
                f"Carattere non consentito: '{carattere}'. Sono ammessi numeri, + - * / % ** e parentesi."
            )
    try:
        albero = ast.parse(testo, mode="eval")
    except SyntaxError:
        raise ErroreStrumento("Espressione non valida: errore di sintassi.") from None

    with localcontext() as contesto:
        contesto.prec = 50
        try:
            risultato = _valuta(albero, testo)
        except DivisionByZero:  # per esempio 0 ** -1
            raise ErroreStrumento("Divisione per zero.") from None
        except (Overflow, InvalidOperation):
            raise ErroreStrumento("Risultato troppo grande.") from None
    return {"espressione": espressione, "risultato": _numero(risultato)}
