"""Configurazione del back-end delle chat, letta dalle variabili d'ambiente."""

from dataclasses import dataclass
from typing import Mapping

from assistente.configurazione import HOST_AGENTE_PREDEFINITO, ErroreConfigurazione, leggi_indirizzo_ip, leggi_porta

OBBLIGATORIE = ("BACKEND_PORTA", "AGENTE_PORTA", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
PORTA_POSTGRES_PREDEFINITA = "5432"


@dataclass(frozen=True)
class ValoriBackend:
    porta: int
    host: str
    porta_agente: int
    indirizzo_agente: str
    utente: str
    password: str
    database: str
    host_postgres: str
    porta_postgres: int


@dataclass(frozen=True)
class ConfigurazioneBackend:
    porta: int
    host: str
    url_agente: str
    dsn: str
    host_postgres: str
    porta_postgres: int


def leggi_valori_backend(env: Mapping[str, str]) -> ValoriBackend:
    """Legge e controlla le variabili del back-end; non importa psycopg (la usa anche l'avvio su Windows)."""
    valori = {nome: (env.get(nome) or "").strip() for nome in OBBLIGATORIE}
    mancanti = [nome for nome, valore in valori.items() if not valore]
    if mancanti:
        raise ErroreConfigurazione(
            "Variabili d'ambiente mancanti: " + ", ".join(mancanti) + ". "
            "Aggiungile al file .env prendendole da .env.example; per POSTGRES_PASSWORD scegli tu una password."
        )
    porta = leggi_porta("BACKEND_PORTA", valori["BACKEND_PORTA"])
    porta_agente = leggi_porta("AGENTE_PORTA", valori["AGENTE_PORTA"])
    if porta == porta_agente:
        raise ErroreConfigurazione("BACKEND_PORTA deve essere diversa da AGENTE_PORTA.")
    for nome in ("MCP_PORTA", "API_PORTA"):
        testo = (env.get(nome) or "").strip()
        if testo and porta == leggi_porta(nome, testo):
            raise ErroreConfigurazione(f"BACKEND_PORTA deve essere diversa da {nome}.")
    porta_postgres = leggi_porta(
        "POSTGRES_PORTA", (env.get("POSTGRES_PORTA") or "").strip() or PORTA_POSTGRES_PREDEFINITA
    )
    return ValoriBackend(
        porta=porta,
        host=leggi_indirizzo_ip("BACKEND_HOST", env),
        porta_agente=porta_agente,
        indirizzo_agente=(env.get("AGENTE_INDIRIZZO") or "").strip() or HOST_AGENTE_PREDEFINITO,
        utente=valori["POSTGRES_USER"],
        password=valori["POSTGRES_PASSWORD"],
        database=valori["POSTGRES_DB"],
        host_postgres=(env.get("POSTGRES_HOST") or "").strip() or HOST_AGENTE_PREDEFINITO,
        porta_postgres=porta_postgres,
    )


def carica_configurazione_backend(env: Mapping[str, str]) -> ConfigurazioneBackend:
    from psycopg.conninfo import make_conninfo

    v = leggi_valori_backend(env)
    dsn = make_conninfo(
        host=v.host_postgres,
        port=v.porta_postgres,
        user=v.utente,
        password=v.password,
        dbname=v.database,
        connect_timeout=5,
    )
    return ConfigurazioneBackend(
        porta=v.porta,
        host=v.host,
        url_agente=f"http://{v.indirizzo_agente}:{v.porta_agente}",
        dsn=dsn,
        host_postgres=v.host_postgres,
        porta_postgres=v.porta_postgres,
    )
