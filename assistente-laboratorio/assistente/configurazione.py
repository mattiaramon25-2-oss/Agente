"""Configurazione letta dalle variabili d'ambiente (nessun valore scritto nel codice)."""

from dataclasses import dataclass
from typing import Mapping

OBBLIGATORIE = ("LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL")


@dataclass(frozen=True)
class Configurazione:
    base_url: str
    modello: str


class ErroreConfigurazione(Exception):
    pass


def carica_configurazione(env: Mapping[str, str]) -> Configurazione:
    valori = {nome: (env.get(nome) or "").strip() for nome in OBBLIGATORIE}
    mancanti = [nome for nome, valore in valori.items() if not valore]
    if mancanti:
        raise ErroreConfigurazione(
            "Variabili d'ambiente mancanti: " + ", ".join(mancanti) + ". "
            "Copia .env.example in .env e imposta i valori "
            "(l'identificativo del modello è quello restituito da GET /v1/models)."
        )
    return Configurazione(base_url=valori["LMSTUDIO_BASE_URL"], modello=valori["LMSTUDIO_MODEL"])
