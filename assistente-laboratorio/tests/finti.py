"""Modello finto per i test: risposte preparate, nessun server."""

from langchain_core.messages import AIMessage, BaseMessage


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
