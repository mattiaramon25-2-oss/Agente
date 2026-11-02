import json
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.grafo import (
    MAX_GIRI_STRUMENTO,
    TESTO_LIMITE,
    crea_grafo,
    esegui_turno,
    instrada_dopo_modello,
    messaggio_sistema,
)
from assistente.strumenti import crea_strumento_orologio
from tests.finti import ModelloFinto, chiamata_orologio

ISTANTE = datetime(2026, 11, 2, 14, 4, 5, tzinfo=timezone.utc)
FUSO = "Europe/Rome"


def prepara(risposte):
    modello = ModelloFinto(risposte)
    grafo = crea_grafo(modello, [crea_strumento_orologio(lambda: ISTANTE)])
    return modello, grafo


def tipi(messaggi):
    return [type(m).__name__ for m in messaggi]


def test_messaggio_sistema():
    messaggio = messaggio_sistema(FUSO)
    assert isinstance(messaggio, SystemMessage)
    assert "Europe/Rome" in messaggio.content
    assert "ora_corrente" in messaggio.content


def test_instradamento():
    assert MAX_GIRI_STRUMENTO == 3
    risposta = {"messages": [AIMessage("ciao")], "fuso_utente": FUSO, "giri_strumento": 0}
    assert instrada_dopo_modello(risposta) == "__end__"
    for giri in range(3):
        stato = {"messages": [chiamata_orologio(FUSO)], "fuso_utente": FUSO, "giri_strumento": giri}
        assert instrada_dopo_modello(stato) == "strumenti"
    stato = {"messages": [chiamata_orologio(FUSO)], "fuso_utente": FUSO, "giri_strumento": 3}
    assert instrada_dopo_modello(stato) == "limite"


def test_risposta_diretta():
    modello, grafo = prepara([AIMessage("Ciao!")])
    cronologia = esegui_turno(grafo, [], FUSO, "ciao")
    assert tipi(cronologia) == ["HumanMessage", "AIMessage"]
    assert cronologia[0].content == "ciao"
    assert cronologia[1].content == "Ciao!"
    prima = modello.chiamate[0]
    assert isinstance(prima[0], SystemMessage) and FUSO in prima[0].content
    assert not any(isinstance(m, SystemMessage) for m in cronologia)


def test_ciclo_con_orologio():
    modello, grafo = prepara([chiamata_orologio("Asia/Tokyo", "c1"), AIMessage("Sono le 23:04.")])
    cronologia = esegui_turno(grafo, [], FUSO, "Che ore sono a Tokyo?")
    assert tipi(cronologia) == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
    risultato = cronologia[2]
    assert risultato.tool_call_id == "c1"
    assert json.loads(risultato.content)["data_ora"] == "2026-11-02T23:04:05+09:00"
    assert any(isinstance(m, ToolMessage) for m in modello.chiamate[1])
    assert cronologia[-1].content == "Sono le 23:04."


def test_cronologia_tra_turni():
    modello, grafo = prepara([AIMessage("Ciao!"), AIMessage("Bene.")])
    primo = esegui_turno(grafo, [], FUSO, "ciao")
    copia_primo = list(primo)
    secondo = esegui_turno(grafo, primo, FUSO, "come va?")
    vista = [m.content for m in modello.chiamate[1][1:]]
    assert vista == ["ciao", "Ciao!", "come va?"]
    assert primo == copia_primo and len(primo) == 2
    assert [m.content for m in secondo] == ["ciao", "Ciao!", "come va?", "Bene."]


def test_limite_raggiunto():
    chiamate = [chiamata_orologio(FUSO, f"c{i}") for i in range(1, 5)]
    modello, grafo = prepara(chiamate)
    cronologia = esegui_turno(grafo, [], FUSO, "che ore sono?")
    assert isinstance(cronologia[-1], AIMessage)
    assert cronologia[-1].content == TESTO_LIMITE
    assert len(modello.chiamate) == 4
    richieste = [c["id"] for m in cronologia if isinstance(m, AIMessage) for c in m.tool_calls]
    risposte = [m.tool_call_id for m in cronologia if isinstance(m, ToolMessage)]
    assert richieste == ["c1", "c2", "c3", "c4"]
    assert sorted(risposte) == sorted(richieste)


def test_strumento_sconosciuto_e_argomenti_errati():
    richiesta = AIMessage(
        content="",
        tool_calls=[
            {"name": "meteo", "args": {}, "id": "x1", "type": "tool_call"},
            {"name": "ora_corrente", "args": {}, "id": "x2", "type": "tool_call"},
        ],
    )
    _, grafo = prepara([richiesta, AIMessage("ok")])
    cronologia = esegui_turno(grafo, [], FUSO, "boh")
    risultati = [m for m in cronologia if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in risultati] == ["x1", "x2"]
    for m in risultati:
        assert "errore" in json.loads(m.content)
    assert cronologia[-1].content == "ok"


def test_giri_ripartono_a_ogni_turno():
    turno1 = [chiamata_orologio(FUSO, f"a{i}") for i in range(3)] + [AIMessage("fine 1")]
    turno2 = [chiamata_orologio(FUSO, "b0"), AIMessage("fine 2")]
    _, grafo = prepara(turno1 + turno2)
    cronologia = esegui_turno(grafo, [], FUSO, "uno")
    assert cronologia[-1].content == "fine 1"
    cronologia = esegui_turno(grafo, cronologia, FUSO, "due")
    assert cronologia[-1].content == "fine 2"
    assert TESTO_LIMITE not in [m.content for m in cronologia]


def test_chiamata_con_json_malformato():
    # Un modello piccolo può produrre argomenti che non sono JSON: finiscono in invalid_tool_calls.
    malformata = AIMessage(
        content="",
        invalid_tool_calls=[
            {"name": "ora_corrente", "args": "{fuso: Europe/Rome", "id": "z1", "error": None,
             "type": "invalid_tool_call"}
        ],
    )
    modello, grafo = prepara([malformata, AIMessage("ok")])
    cronologia = esegui_turno(grafo, [], FUSO, "che ore sono?")
    risultati = [m for m in cronologia if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in risultati] == ["z1"]
    assert "errore" in json.loads(risultati[0].content)
    assert len(modello.chiamate) == 2
    assert cronologia[-1].content == "ok"


def test_limite_chiude_anche_le_chiamate_malformate():
    malformata = AIMessage(
        content="",
        invalid_tool_calls=[
            {"name": "ora_corrente", "args": "{", "id": "z9", "error": None, "type": "invalid_tool_call"}
        ],
    )
    chiamate = [chiamata_orologio(FUSO, f"c{i}") for i in range(1, 4)]
    _, grafo = prepara([*chiamate, malformata])
    cronologia = esegui_turno(grafo, [], FUSO, "che ore sono?")
    assert cronologia[-1].content == TESTO_LIMITE
    assert "z9" in [m.tool_call_id for m in cronologia if isinstance(m, ToolMessage)]
