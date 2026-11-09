"""Giorni e scadenze: data ISO + numero di giorni, di calendario o lavorativi.

Le festività nazionali italiane vengono da un file locale versionato
(`risorse/festivita_italia.json`). Il risultato è indicativo e non ha valore legale.
"""

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from pathlib import Path

from logica.errori import ErroreStrumento
from logica.orologio import GIORNI

PERCORSO_FESTIVITA = Path(__file__).resolve().parent.parent / "risorse" / "festivita_italia.json"
GIORNI_MASSIMI = 3650
NOTA = "Calcolo indicativo: non ha valore legale."

# Schema JSON degli argomenti, unico per tutte le varianti (MCP e FastAPI).
SCHEMA_DATA_INIZIO = {"type": "string", "description": "Data di partenza in formato ISO AAAA-MM-GG, per esempio 2026-12-23"}
SCHEMA_GIORNI = {"type": "integer", "description": f"Numero di giorni da aggiungere, da 0 a {GIORNI_MASSIMI}"}
SCHEMA_LAVORATIVI = {
    "type": "boolean",
    "description": "true per contare solo i giorni lavorativi (lunedì-venerdì esclusi i festivi), false per i giorni di calendario",
}

_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_CIFRE = re.compile(r"[0-9]+", re.ASCII)


@dataclass(frozen=True)
class Festivita:
    anni: frozenset[int]
    date: dict[date, str]


@cache
def carica_festivita(percorso: Path = PERCORSO_FESTIVITA) -> Festivita:
    with open(percorso, encoding="utf-8") as file:
        dati = json.load(file)
    return Festivita(
        anni=frozenset(dati["anni"]),
        date={date.fromisoformat(f["data"]): f["nome"] for f in dati["festivita"]},
    )


def _leggi_data(valore: object) -> date:
    if isinstance(valore, str) and _DATA_ISO.fullmatch(valore):
        try:
            return date.fromisoformat(valore)
        except ValueError:
            pass
    raise ErroreStrumento(f"Data non valida: '{valore}'. Usa il formato AAAA-MM-GG, per esempio 2026-12-23.")


def _leggi_giorni(valore: object) -> int:
    numero = None
    if isinstance(valore, int) and not isinstance(valore, bool):
        numero = valore
    elif isinstance(valore, float) and valore.is_integer():
        numero = int(valore)
    elif isinstance(valore, str) and _CIFRE.fullmatch(valore):
        numero = int(valore)
    if numero is None or not 0 <= numero <= GIORNI_MASSIMI:
        raise ErroreStrumento(f"giorni deve essere un numero intero tra 0 e {GIORNI_MASSIMI}.")
    return numero


def calcola_scadenza(
    data_inizio: object, giorni: object, lavorativi: object, festivita: Festivita | None = None
) -> dict:
    """Data di scadenza contando i giorni dal giorno successivo a `data_inizio`; solleva ErroreStrumento."""
    inizio = _leggi_data(data_inizio)
    quanti = _leggi_giorni(giorni)
    if not isinstance(lavorativi, bool):
        raise ErroreStrumento("lavorativi deve essere true o false.")
    calendario = festivita or carica_festivita()

    giorno = inizio
    contati = 0
    saltate: list[str] = []
    while contati < quanti:
        try:
            giorno += timedelta(days=1)
        except OverflowError:  # oltre il 9999-12-31 non esistono date
            raise ErroreStrumento("La scadenza supera la data massima gestibile (9999-12-31).") from None
        if not lavorativi:
            contati += 1
            continue
        if giorno.year not in calendario.anni:
            anni = sorted(calendario.anni)
            raise ErroreStrumento(
                f"Festività disponibili solo per gli anni {anni[0]}–{anni[-1]}: "
                "il calcolo dei giorni lavorativi esce da questo intervallo."
            )
        nome = calendario.date.get(giorno)
        if nome:
            saltate.append(f"{giorno.isoformat()} {nome}")
        elif giorno.weekday() < 5:
            contati += 1

    return {
        "data_inizio": data_inizio,
        "giorni": quanti,
        "lavorativi": lavorativi,
        "scadenza": giorno.isoformat(),
        "giorno_settimana": GIORNI[giorno.weekday()],
        "festivita_saltate": saltate,
        "nota": NOTA,
    }
