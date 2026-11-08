"""Modello finto per i test: risposte preparate, nessun server."""

import json
from datetime import datetime

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool, StructuredTool

from logica.errori import ErroreStrumento
from logica.orologio import ora_corrente as logica_ora_corrente


class ModelloFinto:
    def __init__(self, risposte: list[AIMessage | BaseException]):
        self.risposte = list(risposte)
        self.chiamate: list[list[BaseMessage]] = []

    def invoke(self, messaggi, config=None) -> AIMessage:
        self.chiamate.append(list(messaggi))
        if not self.risposte:
            raise AssertionError("il modello finto non ha più risposte preparate")
        risposta = self.risposte.pop(0)
        if isinstance(risposta, BaseException):
            raise risposta
        return risposta


def chiamata_orologio(fuso: str, id: str = "c1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "ora_corrente", "args": {"fuso": fuso}, "id": id, "type": "tool_call"}],
    )


def chiamata(nome: str, argomenti: dict, id: str = "c1") -> AIMessage:
    """Richiesta di strumento generica, come la produrrebbe il modello."""
    return AIMessage(content="", tool_calls=[{"name": nome, "args": argomenti, "id": id, "type": "tool_call"}])


def strumento_finto(risposta: str, nome: str = "converti_unita", origine: str = "mcp") -> BaseTool:
    """Strumento che restituisce sempre `risposta`, con l'origine indicata nei metadati."""

    def esegui(**argomenti) -> str:
        return risposta

    schema = {"type": "object", "properties": {}, "additionalProperties": True}
    return StructuredTool(name=nome, description="finto", args_schema=schema, func=esegui, metadata={"origine": origine})


def orologio_finto(istante: datetime) -> BaseTool:
    """Imita `ora_corrente` del server MCP con un istante fisso: stessa logica, errori come dal ponte."""

    def ora_corrente(fuso: str) -> str:
        try:
            return json.dumps(logica_ora_corrente(fuso, istante), ensure_ascii=False)
        except ErroreStrumento as errore:
            return json.dumps({"errore": str(errore), "tipo": "strumento"}, ensure_ascii=False)

    return StructuredTool.from_function(
        func=ora_corrente, name="ora_corrente", description="finto", metadata={"origine": "mcp"}
    )
