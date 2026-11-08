"""Catalogo locale dei corsi: ricerca esatta (sottostringa) e dettaglio per codice.

I dati sono in `risorse/catalogo_corsi.json`. È ricerca su dati strutturati, non RAG:
una ricerca senza risultati restituisce una lista vuota, mai elementi inventati.
"""

import json
import re
from pathlib import Path

from logica.errori import ErroreStrumento

PERCORSO_CATALOGO = Path(__file__).resolve().parent.parent / "risorse" / "catalogo_corsi.json"
MAX_RISULTATI = 20
RISULTATI_PREDEFINITI = 5
CAMPI = {"codice": str, "titolo": str, "sede": str, "durata_ore": int}

# Schemi JSON degli argomenti (nomi dalla slide 28), unici per ogni registrazione.
SCHEMA_QUERY = {"type": "string", "description": "Parola da cercare nel titolo, nella sede o nel codice dei corsi"}
SCHEMA_MAX_RESULTS = {
    "type": "integer",
    "minimum": 1,
    "maximum": MAX_RISULTATI,
    "default": RISULTATI_PREDEFINITI,
    "description": f"Numero massimo di corsi da restituire, da 1 a {MAX_RISULTATI}",
}
SCHEMA_CODE = {"type": "string", "description": "Codice esatto del corso, per esempio DLL-01"}

_CIFRE = re.compile(r"[0-9]+", re.ASCII)


def carica_catalogo(percorso: Path = PERCORSO_CATALOGO) -> list[dict]:
    """Legge e valida il file; un file non valido è un errore di avvio (ValueError), non dello strumento."""
    try:
        with open(percorso, encoding="utf-8") as file:
            corsi = json.load(file)
    except (OSError, ValueError) as errore:
        raise ValueError(f"Catalogo non valido in {percorso}: {errore}") from None
    if not isinstance(corsi, list):
        raise ValueError(f"Catalogo non valido in {percorso}: serve una lista di corsi.")
    codici = set()
    for posizione, corso in enumerate(corsi, start=1):
        for campo, tipo in CAMPI.items():
            valore = corso.get(campo) if isinstance(corso, dict) else None
            if not isinstance(valore, tipo) or isinstance(valore, bool):
                raise ValueError(f"Catalogo non valido in {percorso}: corso {posizione}, campo '{campo}'.")
        if corso["codice"] in codici:
            raise ValueError(f"Catalogo non valido in {percorso}: codice duplicato '{corso['codice']}'.")
        codici.add(corso["codice"])
    return corsi


def _leggi_max(valore: object) -> int:
    numero = None
    if isinstance(valore, int) and not isinstance(valore, bool):
        numero = valore
    elif isinstance(valore, float) and valore.is_integer():
        numero = int(valore)
    elif isinstance(valore, str) and _CIFRE.fullmatch(valore):
        numero = int(valore)
    if numero is None or not 1 <= numero <= MAX_RISULTATI:
        raise ErroreStrumento(f"max_results deve essere un intero tra 1 e {MAX_RISULTATI}.")
    return numero


def cerca(catalogo: list[dict], query: object, max_results: object = RISULTATI_PREDEFINITI) -> dict:
    """Corsi il cui codice, titolo o sede contiene `query` (senza distinguere maiuscole), nell'ordine del file."""
    if not isinstance(query, str) or not query.strip():
        raise ErroreStrumento("La ricerca richiede una parola non vuota.")
    limite = _leggi_max(max_results)
    cercata = query.strip().casefold()
    trovati = [
        corso for corso in catalogo
        if any(cercata in corso[campo].casefold() for campo in ("codice", "titolo", "sede"))
    ]
    return {
        "query": query,
        "risultati": [{"codice": c["codice"], "titolo": c["titolo"], "sede": c["sede"]} for c in trovati[:limite]],
        "totale": len(trovati),
    }


def dettaglio(catalogo: list[dict], code: object) -> dict:
    """Il corso completo con codice esattamente uguale a `code`."""
    for corso in catalogo:
        if isinstance(code, str) and corso["codice"] == code:
            return dict(corso)
    raise ErroreStrumento(f"Nessun corso con codice '{code}'. Usa prima search_catalog per trovare il codice.")
