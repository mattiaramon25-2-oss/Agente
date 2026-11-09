"""Ambito dell'assistente letto da `risorse/ambito.json`: si cambia il file, non il codice."""

import json
from dataclasses import dataclass
from pathlib import Path

from assistente.errori import ErroreAvvio

PERCORSO_AMBITO = Path(__file__).resolve().parent.parent / "risorse" / "ambito.json"


@dataclass(frozen=True)
class Ambito:
    in_ambito: tuple[str, ...]
    fuori_ambito: tuple[str, ...]
    rifiuto: str


def _elenco(dati: dict, chiave: str, percorso: Path) -> tuple[str, ...]:
    valore = dati.get(chiave)
    if not isinstance(valore, list) or not valore or not all(isinstance(v, str) and v.strip() for v in valore):
        raise ErroreAvvio(f"{percorso.name}: '{chiave}' deve essere un elenco non vuoto di testi ({percorso}).")
    return tuple(v.strip() for v in valore)


def carica_ambito(percorso: Path = PERCORSO_AMBITO) -> Ambito:
    percorso = Path(percorso)
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ErroreAvvio(f"File dell'ambito non trovato: {percorso} (ambito.json).") from None
    except ValueError as eccezione:
        raise ErroreAvvio(f"{percorso.name} non è JSON valido: {eccezione}") from None
    if not isinstance(dati, dict):
        raise ErroreAvvio(f"{percorso.name}: serve un oggetto con in_ambito, fuori_ambito e rifiuto.")
    rifiuto = dati.get("rifiuto")
    if not isinstance(rifiuto, str) or not rifiuto.strip():
        raise ErroreAvvio(f"{percorso.name}: 'rifiuto' deve essere un testo non vuoto.")
    return Ambito(
        in_ambito=_elenco(dati, "in_ambito", percorso),
        fuori_ambito=_elenco(dati, "fuori_ambito", percorso),
        rifiuto=rifiuto.strip(),
    )
