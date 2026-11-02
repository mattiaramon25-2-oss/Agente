"""Grafo LangGraph della conversazione: stato, nodi e instradamento espliciti.

    START -> modello -> (instrada_dopo_modello) -> strumenti -> modello
                                                -> limite    -> END
                                                -> END
"""

import json
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from assistente.strumenti import NOME_OROLOGIO

MAX_GIRI_STRUMENTO = 3
TESTO_LIMITE = (
    "Non sono riuscito a completare la richiesta: troppe chiamate all'orologio. Prova a riformularla."
)


class StatoConversazione(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    fuso_utente: str
    giri_strumento: int  # giri di strumento nel turno corrente


def messaggio_sistema(fuso_utente: str) -> SystemMessage:
    return SystemMessage(
        "Sei un assistente utile. Rispondi nella lingua in cui scrive l'utente.\n"
        f"Per conoscere la data o l'ora usa sempre lo strumento {NOME_OROLOGIO}: "
        "non inventarle e non dedurle dai messaggi precedenti.\n"
        f"Il fuso orario dell'utente è {fuso_utente}: usalo quando l'utente non indica un altro luogo o fuso.\n"
        "Se l'utente indica un luogo, passa allo strumento il nome IANA del fuso corrispondente "
        "(per esempio Asia/Tokyo per Tokyo)."
    )


def _errore(testo: str) -> str:
    return json.dumps({"errore": testo}, ensure_ascii=False)


def _malformate(messaggio) -> list[dict]:
    """Chiamate con argomenti non JSON: vanno chiuse anche loro, o la cronologia resta invalida."""
    return list(getattr(messaggio, "invalid_tool_calls", None) or [])


def _malformate_chiuse(messaggio, testo: str) -> list[ToolMessage]:
    return [
        ToolMessage(_errore(testo), tool_call_id=c.get("id") or "", name=c.get("name") or "", status="error")
        for c in _malformate(messaggio)
    ]


def instrada_dopo_modello(stato: StatoConversazione) -> Literal["strumenti", "limite", "__end__"]:
    ultimo = stato["messages"][-1]
    if not getattr(ultimo, "tool_calls", None) and not _malformate(ultimo):
        return END
    if stato["giri_strumento"] >= MAX_GIRI_STRUMENTO:
        return "limite"
    return "strumenti"


def crea_grafo(modello, strumenti: list[BaseTool]):
    """`modello` ha `.invoke(messaggi) -> AIMessage` ed è già collegato agli strumenti."""
    per_nome = {strumento.name: strumento for strumento in strumenti}

    def nodo_modello(stato: StatoConversazione) -> dict:
        risposta = modello.invoke([messaggio_sistema(stato["fuso_utente"]), *stato["messages"]])
        return {"messages": [risposta]}

    def nodo_strumenti(stato: StatoConversazione) -> dict:
        risultati = []
        for chiamata in stato["messages"][-1].tool_calls:
            strumento = per_nome.get(chiamata["name"])
            if strumento is None:
                contenuto = _errore(f"Strumento sconosciuto: '{chiamata['name']}'.")
            else:
                try:
                    contenuto = strumento.invoke(chiamata["args"])
                except Exception as eccezione:  # anche argomenti non validi
                    contenuto = _errore(f"Argomenti non validi per {chiamata['name']}: {eccezione}")
            risultati.append(ToolMessage(contenuto, tool_call_id=chiamata["id"], name=chiamata["name"]))
        risultati += _malformate_chiuse(
            stato["messages"][-1], "Argomenti non validi: devono essere JSON, per esempio {\"fuso\": \"Europe/Rome\"}."
        )
        return {"messages": risultati, "giri_strumento": stato["giri_strumento"] + 1}

    def nodo_limite(stato: StatoConversazione) -> dict:
        in_sospeso = [
            # status="error": la chiamata non è stata eseguita.
            ToolMessage(
                _errore("limite di chiamate raggiunto"), tool_call_id=c["id"], name=c["name"], status="error"
            )
            for c in stato["messages"][-1].tool_calls
        ]
        in_sospeso += _malformate_chiuse(stato["messages"][-1], "limite di chiamate raggiunto")
        return {"messages": [*in_sospeso, AIMessage(TESTO_LIMITE)]}

    costruttore = StateGraph(StatoConversazione)
    costruttore.add_node("modello", nodo_modello)
    costruttore.add_node("strumenti", nodo_strumenti)
    costruttore.add_node("limite", nodo_limite)
    costruttore.add_edge(START, "modello")
    costruttore.add_conditional_edges("modello", instrada_dopo_modello, ["strumenti", "limite", END])
    costruttore.add_edge("strumenti", "modello")
    costruttore.add_edge("limite", END)
    return costruttore.compile()


def esegui_turno(grafo, cronologia: list[BaseMessage], fuso_utente: str, testo: str) -> list[BaseMessage]:
    """Esegue un turno e restituisce la nuova cronologia completa; `cronologia` non viene modificata."""
    stato = grafo.invoke(
        {
            "messages": [*cronologia, HumanMessage(testo)],
            "fuso_utente": fuso_utente,
            "giri_strumento": 0,
        }
    )
    return list(stato["messages"])
