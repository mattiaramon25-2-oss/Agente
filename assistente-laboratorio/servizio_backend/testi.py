"""Testi comuni del back-end: titolo di una chat ed estratto di un risultato di ricerca."""

TITOLO_PREDEFINITO = "Nuova chat"
_LUNGHEZZA_TITOLO = 60


def titolo_da(domanda: str) -> str:
    """Le prime parole della domanda: al massimo 60 caratteri, tagliati su uno spazio se si può."""
    testo = " ".join(domanda.split())
    if len(testo) <= _LUNGHEZZA_TITOLO:
        return testo
    taglio = testo[:_LUNGHEZZA_TITOLO]
    if testo[_LUNGHEZZA_TITOLO] != " " and " " in taglio:
        taglio = taglio[: taglio.rindex(" ")]
    return taglio.rstrip() + "…"


def estratto(testo: str, q: str, larghezza: int = 80) -> str:
    """Una finestra di `larghezza` caratteri centrata sulla prima occorrenza di `q`."""
    if len(testo) <= larghezza:
        return testo
    posizione = testo.lower().find(q.lower())
    centro = (posizione if posizione >= 0 else 0) + len(q) // 2
    inizio = max(0, min(centro - larghezza // 2, len(testo) - larghezza))
    fine = inizio + larghezza
    return ("…" if inizio > 0 else "") + testo[inizio:fine] + ("…" if fine < len(testo) else "")
