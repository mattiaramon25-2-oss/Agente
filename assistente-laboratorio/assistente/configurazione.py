"""Configurazione letta dalle variabili d'ambiente (nessun valore scritto nel codice)."""

import ipaddress
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


def leggi_porta_agente(env: Mapping[str, str], config: Configurazione) -> int:
    """AGENTE_PORTA, che serve solo al servizio HTTP dell'agente (python -m servizio_agente)."""
    testo = (env.get("AGENTE_PORTA") or "").strip()
    if not testo:
        raise ErroreConfigurazione(
            "Variabili d'ambiente mancanti: AGENTE_PORTA (serve al servizio HTTP dell'agente). "
            "Aggiungila al file .env, per esempio AGENTE_PORTA=8767."
        )
    porta = leggi_porta("AGENTE_PORTA", testo)
    if porta == config.porta_mcp:
        raise ErroreConfigurazione("AGENTE_PORTA deve essere diversa da MCP_PORTA.")
    if porta == config.porta_api:
        raise ErroreConfigurazione("AGENTE_PORTA deve essere diversa da API_PORTA.")
    return porta


HOST_AGENTE_PREDEFINITO = "127.0.0.1"


def leggi_host_agente(env: Mapping[str, str]) -> str:
    """AGENTE_HOST, facoltativa: indirizzo IP su cui ascolta il servizio dell'agente.

    Fuori da Docker resta 127.0.0.1; Docker Compose la imposta a 0.0.0.0, perché nel container la
    porta pubblicata arriva dall'interfaccia di rete del container, non da 127.0.0.1.
    """
    testo = (env.get("AGENTE_HOST") or "").strip()
    if not testo:
        return HOST_AGENTE_PREDEFINITO
    try:
        ipaddress.ip_address(testo)
    except ValueError:
        raise ErroreConfigurazione(
            f"AGENTE_HOST non valida: '{testo}'. Usa un indirizzo IP, per esempio 127.0.0.1 (predefinito) o 0.0.0.0."
        ) from None
    return testo
