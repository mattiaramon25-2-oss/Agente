"""Configurazione letta dalle variabili d'ambiente (nessun valore scritto nel codice)."""

from dataclasses import dataclass
from typing import Mapping

OBBLIGATORIE = ("LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL", "MCP_PORTA", "VARIANTE_CALCOLATRICE", "VARIANTE_SCADENZE")
VARIANTI_CALCOLATRICE = ("mcp", "locale")
VARIANTI_SCADENZE = ("mcp", "fastapi")
PORTA_MINIMA = 1024
PORTA_MASSIMA = 65535


@dataclass(frozen=True)
class Configurazione:
    base_url: str
    modello: str
    porta_mcp: int
    # Valore predefinito solo per comodità di costruzione: nell'ambiente la variabile è obbligatoria.
    variante_calcolatrice: str = "mcp"
    variante_scadenze: str = "mcp"
    porta_api: int | None = None  # solo con variante_scadenze == "fastapi"


class ErroreConfigurazione(Exception):
    pass


def leggi_porta(nome: str, valore: str) -> int:
    """Intero tra 1024 e 65535 scritto solo con cifre."""
    if not valore.isdigit() or not PORTA_MINIMA <= int(valore) <= PORTA_MASSIMA:
        raise ErroreConfigurazione(
            f"{nome} non valida: '{valore}'. Usa un numero intero tra {PORTA_MINIMA} e {PORTA_MASSIMA}, per esempio 8765."
        )
    return int(valore)


def leggi_variante(nome: str, valore: str, ammessi: tuple[str, ...]) -> str:
    normalizzato = valore.strip().lower()
    if normalizzato not in ammessi:
        raise ErroreConfigurazione(f"{nome} non valida: '{valore.strip()}'. Valori ammessi: {', '.join(ammessi)}.")
    return normalizzato


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
    porta_mcp = leggi_porta("MCP_PORTA", valori["MCP_PORTA"])
    variante_scadenze = leggi_variante("VARIANTE_SCADENZE", valori["VARIANTE_SCADENZE"], VARIANTI_SCADENZE)
    porta_api = None
    if variante_scadenze == "fastapi":
        testo = (env.get("API_PORTA") or "").strip()
        if not testo:
            raise ErroreConfigurazione(
                "Variabili d'ambiente mancanti: API_PORTA (serve con VARIANTE_SCADENZE=fastapi). "
                "Aggiungila al file .env, per esempio API_PORTA=8766."
            )
        porta_api = leggi_porta("API_PORTA", testo)
        if porta_api == porta_mcp:
            raise ErroreConfigurazione("API_PORTA deve essere diversa da MCP_PORTA.")
    return Configurazione(
        base_url=valori["LMSTUDIO_BASE_URL"],
        modello=valori["LMSTUDIO_MODEL"],
        porta_mcp=porta_mcp,
        variante_calcolatrice=leggi_variante(
            "VARIANTE_CALCOLATRICE", valori["VARIANTE_CALCOLATRICE"], VARIANTI_CALCOLATRICE
        ),
        variante_scadenze=variante_scadenze,
        porta_api=porta_api,
    )
