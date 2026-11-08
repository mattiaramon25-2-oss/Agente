"""Grafo LangGraph della conversazione: stato, nodi e instradamento espliciti.

    START -> modello -> (instrada_dopo_modello) -> strumenti -> modello
                                                -> limite    -> END
                                                -> END
"""

import json
import logging
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from assistente.registro import formatta

NOME_OROLOGIO = "ora_corrente"  # nome pubblicato dal server MCP
MAX_GIRI_STRUMENTO = 3
TESTO_LIMITE = (
    "Non sono riuscito a completare la richiesta: troppe chiamate agli strumenti. Prova a riformularla."
)
TESTO_NON_JSON = "Argomenti non validi: devono essere un oggetto JSON con gli argomenti dello strumento."

registro = logging.getLogger("assistente.strumenti")


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
        "(per esempio Asia/Tokyo per Tokyo).\n"
        "Per conversioni di unità e altri calcoli usa sempre lo strumento adatto tra quelli disponibili: "
        "non farli a mente.\n"
        "Per domande sui corsi dell'ITS usa gli strumenti del catalogo e non inventare corsi che non "
        "compaiono nei risultati.\n"
        "Per le note: aggiungi una nota solo se l'utente chiede di ricordare o annotare qualcosa; "
        "elimina le note solo per ID; se l'utente non indica l'ID, prima elencale e chiedigli quale eliminare; "
        "prima di eliminare, anche se una sola nota corrisponde, mostra ID e testo e chiedi conferma all'utente.\n"
        "Se lo strumento del meteo dichiara di aver scelto una città tra più corrispondenze, dillo all'utente "
        "nominando la città scelta."
    )


def _errore(testo: str) -> str:
    return json.dumps({"errore": testo}, ensure_ascii=False)


def _malformate(messaggio) -> list[dict]:
    """Chiamate con argomenti non JSON: vanno chiuse anche loro, o la cronologia resta invalida."""
    return list(getattr(messaggio, "invalid_tool_calls", None) or [])


def _esito(contenuto: object) -> str:
    """ok, errore_tool o errore_collegamento, letto dal contenuto JSON restituito dallo strumento."""
    try:
        dati = json.loads(contenuto) if isinstance(contenuto, str) else None
    except ValueError:
        dati = None
    if isinstance(dati, dict) and "errore" in dati:
        return "errore_collegamento" if dati.get("tipo") == "collegamento" else "errore_tool"
    return "ok"


def _argomenti_mancanti(strumento: BaseTool, argomenti: object) -> list[str]:
    """Argomenti obbligatori dello schema che la richiesta del modello non contiene."""
    schema = strumento.tool_call_schema
    if not isinstance(schema, dict):
        schema = schema.model_json_schema()
    presenti = argomenti if isinstance(argomenti, dict) else {}
    return [nome for nome in schema.get("required", []) if nome not in presenti]


def _registra(origine: str, chiamata: dict, esito: str, contenuto: object, messaggio: ToolMessage) -> None:
    registro.info(
        formatta(
            {
                "origine": origine,
                "tool": chiamata.get("name") or "",
                "call_id": chiamata.get("id") or "",
                "argomenti": chiamata.get("args"),
                "esito": esito,
                "risultato": contenuto if isinstance(contenuto, str) else str(contenuto),
                "tool_message.call_id": messaggio.tool_call_id,
            }
        )
    )


def _malformate_chiuse(messaggio, testo: str, esito: str) -> list[ToolMessage]:
    chiusi = []
    for c in _malformate(messaggio):
        contenuto = _errore(testo)
        tool_message = ToolMessage(contenuto, tool_call_id=c.get("id") or "", name=c.get("name") or "", status="error")
        _registra("sconosciuta", c, esito, contenuto, tool_message)
        chiusi.append(tool_message)
    return chiusi


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
                origine, esito = "sconosciuta", "strumento_sconosciuto"
                contenuto = _errore(f"Strumento sconosciuto: '{chiamata['name']}'.")
            else:
                origine = (strumento.metadata or {}).get("origine", "locale")
                # Controllo dell'host prima dell'esecuzione (slide 5), uguale per ogni variante.
                mancanti = _argomenti_mancanti(strumento, chiamata["args"])
                if mancanti:
                    contenuto = json.dumps(
                        {
                            "errore": f"Argomenti mancanti per {chiamata['name']}: {', '.join(mancanti)}. "
                            "Riprova indicando tutti gli argomenti richiesti.",
                            "tipo": "strumento",
                        },
                        ensure_ascii=False,
                    )
                    esito = "errore_tool"
                else:
                    try:
                        contenuto = strumento.invoke(chiamata["args"])
                        esito = _esito(contenuto)
                    except Exception as eccezione:  # anche argomenti non validi
                        contenuto = _errore(f"Argomenti non validi per {chiamata['name']}: {eccezione}")
                        esito = "errore_tool"
            messaggio = ToolMessage(
                contenuto,
                tool_call_id=chiamata["id"],
                name=chiamata["name"],
                status="success" if esito == "ok" else "error",
            )
            _registra(origine, chiamata, esito, contenuto, messaggio)
            risultati.append(messaggio)
        risultati += _malformate_chiuse(stato["messages"][-1], TESTO_NON_JSON, "errore_tool")
        return {"messages": risultati, "giri_strumento": stato["giri_strumento"] + 1}

    def nodo_limite(stato: StatoConversazione) -> dict:
        in_sospeso = []
        for c in stato["messages"][-1].tool_calls:
            # status="error": la chiamata non è stata eseguita.
            contenuto = _errore("limite di chiamate raggiunto")
            messaggio = ToolMessage(contenuto, tool_call_id=c["id"], name=c["name"], status="error")
            origine = (getattr(per_nome.get(c["name"]), "metadata", None) or {}).get("origine", "sconosciuta")
            _registra(origine, c, "limite", contenuto, messaggio)
            in_sospeso.append(messaggio)
        in_sospeso += _malformate_chiuse(stato["messages"][-1], "limite di chiamate raggiunto", "limite")
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
