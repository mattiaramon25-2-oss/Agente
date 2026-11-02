"""Collegamento al modello servito da LM Studio (API compatibile con OpenAI)."""

import json
import urllib.request
from typing import Callable

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistente.configurazione import Configurazione

# LM Studio non controlla la chiave, ma la libreria ne esige una: è un segnaposto, non una credenziale.
CHIAVE_SEGNAPOSTO = "lm-studio"


class ErroreServer(Exception):
    pass


def _leggi_json_http(url: str, timeout: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as risposta:
        return json.load(risposta)


def verifica_server(
    base_url: str,
    modello: str,
    leggi_json: Callable[[str, float], dict] = _leggi_json_http,
    timeout: float = 5.0,
) -> None:
    """Controlla che LM Studio risponda e che `modello` sia tra quelli restituiti da GET /models."""
    url = base_url.rstrip("/") + "/models"
    try:
        risposta = leggi_json(url, timeout)
    except ValueError as eccezione:  # anche json.JSONDecodeError
        raise ErroreServer(f"Risposta non valida da {url}: {eccezione}") from None
    except OSError as eccezione:  # URLError, TimeoutError, connessione rifiutata
        raise ErroreServer(
            f"Impossibile raggiungere LM Studio all'indirizzo {url} ({eccezione}). "
            "Controlla che LM Studio sia aperto con il server attivo e che LMSTUDIO_BASE_URL sia corretto."
        ) from None

    dati = risposta.get("data") if isinstance(risposta, dict) else None
    if not isinstance(dati, list) or not all(isinstance(m, dict) and "id" in m for m in dati):
        raise ErroreServer(f"Risposta inattesa da {url}: manca l'elenco dei modelli.")

    disponibili = [m["id"] for m in dati]
    if modello not in disponibili:
        elenco = ", ".join(disponibili) if disponibili else "(nessuno)"
        raise ErroreServer(
            f"Il modello '{modello}' non è disponibile su LM Studio. "
            f"Modelli disponibili: {elenco}. Imposta LMSTUDIO_MODEL con uno di questi."
        )


def crea_modello(config: Configurazione, strumenti: list[BaseTool]):
    chat = ChatOpenAI(
        model=config.modello,
        base_url=config.base_url,
        api_key=CHIAVE_SEGNAPOSTO,
        timeout=120,
        max_retries=1,
    )
    return chat.bind_tools(strumenti)
