"""Router dell'ambito: decide se una domanda è «conversazione» (va all'agente) o «fuori_ambito».

Usa lo stesso modello di LM Studio, senza strumenti, con un prompt suo e un output strutturato.
Non valuta gli strumenti: se servono, lo decide l'agente.
"""

import logging
from typing import Literal

import openai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from assistente.ambito import Ambito
from assistente.registro import formatta

MAX_MESSAGGI_ROUTER = 6  # la nuova domanda e gli ultimi messaggi testuali prima di lei
CONVERSAZIONE = "conversazione"
FUORI_AMBITO = "fuori_ambito"

registro = logging.getLogger("assistente.router")


class DecisioneRouter(BaseModel):
    categoria: Literal["conversazione", "fuori_ambito"] = Field(
        description="conversazione se la richiesta rientra nell'ambito, fuori_ambito altrimenti"
    )
    motivo: str = Field(description="una frase breve che spiega la scelta")


def prompt_router(ambito: Ambito) -> SystemMessage:
    in_ambito = "\n".join(f"- {voce}" for voce in ambito.in_ambito)
    fuori = "\n".join(f"- {voce}" for voce in ambito.fuori_ambito)
    return SystemMessage(
        "Sei il router di un assistente. Non rispondi all'utente: classifichi soltanto la sua ultima richiesta.\n"
        f"Rientrano nell'ambito (categoria «{CONVERSAZIONE}»):\n{in_ambito}\n"
        f"Sono fuori ambito (categoria «{FUORI_AMBITO}»):\n{fuori}\n"
        "I messaggi brevi che continuano il discorso precedente (per esempio «e a Roma?», «sì, eliminala», "
        f"«la 2») sono «{CONVERSAZIONE}».\n"
        "Non decidere quali strumenti usare e non valutare se servono strumenti: se ne occupa l'assistente.\n"
        "Rispondi con la categoria e un motivo di una frase."
    )


def messaggi_router(ambito: Ambito, messaggi: list[BaseMessage]) -> list[BaseMessage]:
    """Prompt del router più gli ultimi messaggi di utente e assistente con testo (non quelli di strumento)."""
    testuali = [
        m for m in messaggi if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and m.text.strip())
    ]
    return [prompt_router(ambito), *testuali[-MAX_MESSAGGI_ROUTER:]]


def _categoria(risposta: object) -> tuple[str, str]:
    if isinstance(risposta, dict):
        risposta = DecisioneRouter.model_validate(risposta)  # ValidationError è un ValueError
    if not isinstance(risposta, DecisioneRouter):
        raise ValueError(f"risposta del router inattesa: {risposta!r}")
    return risposta.categoria, risposta.motivo


def decidi(router, ambito: Ambito, messaggi: list[BaseMessage]) -> str:
    """Restituisce la categoria; se l'output non è valido la domanda passa all'agente (errore nel log)."""
    try:
        categoria, motivo = _categoria(router.invoke(messaggi_router(ambito, messaggi)))
        campi = {"nodo": "router", "categoria": categoria, "motivo": motivo, "esito": "ok"}
    except openai.APIConnectionError:  # anche il timeout: gestito come per l'agente
        raise
    except Exception as eccezione:  # un router difettoso non blocca l'utente
        categoria = CONVERSAZIONE
        campi = {"nodo": "router", "categoria": categoria, "motivo": "", "esito": "errore", "errore": repr(eccezione)}
    registro.info(formatta(campi))
    return categoria
