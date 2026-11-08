"""Configurazione letta dalle variabili d'ambiente (nessun valore scritto nel codice)."""

from dataclasses import dataclass
from typing import Mapping

OBBLIGATORIE = ("LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL", "MCP_PORTA")
PORTA_MINIMA = 1024
PORTA_MASSIMA = 65535


@dataclass(frozen=True)
class Configurazione:
    base_url: str
    modello: str
    porta_mcp: int


class ErroreConfigurazione(Exception):
    pass


def leggi_porta(nome: str, valore: str) -> int:
    """Intero tra 1024 e 65535 scritto solo con cifre."""
    if not valore.isdigit() or not PORTA_MINIMA <= int(valore) <= PORTA_MASSIMA:
        raise ErroreConfigurazione(
            f"{nome} non valida: '{valore}'. Usa un numero intero tra {PORTA_MINIMA} e {PORTA_MASSIMA}, per esempio 8765."
        )
    return int(valore)


def carica_configurazione(env: Mapping[str, str]) -> Configurazione:
    valori = {nome: (env.get(nome) or "").strip() for nome in OBBLIGATORIE}
    mancanti = [nome for nome, valore in valori.items() if not valore]
    if mancanti:
        raise ErroreConfigurazione(
            "Variabili d'ambiente mancanti: " + ", ".join(mancanti) + ". "
            "Aggiungi le righe mancanti al file .env, prendendole da .env.example "
            "(se il .env non esiste ancora, crealo copiando .env.example). "
            "L'identificativo del modello è quello restituito da GET /v1/models."
        )
    return Configurazione(
        base_url=valori["LMSTUDIO_BASE_URL"],
        modello=valori["LMSTUDIO_MODEL"],
        porta_mcp=leggi_porta("MCP_PORTA", valori["MCP_PORTA"]),
    )
