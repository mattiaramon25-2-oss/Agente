"""Configurazione del back-end delle chat, letta dalle variabili d'ambiente."""

from dataclasses import dataclass
from typing import Mapping

from psycopg.conninfo import make_conninfo

from assistente.configurazione import ErroreConfigurazione, leggi_porta

OBBLIGATORIE = ("BACKEND_PORTA", "AGENTE_PORTA", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
PORTA_POSTGRES_PREDEFINITA = "5432"


@dataclass(frozen=True)
class ConfigurazioneBackend:
    porta: int
    url_agente: str
    dsn: str
    porta_postgres: int


def carica_configurazione_backend(env: Mapping[str, str]) -> ConfigurazioneBackend:
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
    dsn = make_conninfo(
        host="127.0.0.1",
        port=porta_postgres,
        user=valori["POSTGRES_USER"],
        password=valori["POSTGRES_PASSWORD"],
        dbname=valori["POSTGRES_DB"],
        connect_timeout=5,
    )
    return ConfigurazioneBackend(
        porta=porta,
        url_agente=f"http://127.0.0.1:{porta_agente}",
        dsn=dsn,
        porta_postgres=porta_postgres,
    )
