"""Prova reale delle note persistenti, sempre su un archivio temporaneo (mai quello reale).

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s
I casi sono in sequenza sullo stesso archivio: aggiunta, eliminazione di un ID inesistente,
riavvio ed elenco; l'ultimo caso (eliminazione senza ID) è solo osservato e riportato.
"""

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistente.grafo import esegui_turno
from logica.note import ArchivioNote
from tests.reale import ambiente_reale

pytestmark = pytest.mark.lmstudio


@pytest.fixture(scope="module")
def archivio(tmp_path_factory):
    return tmp_path_factory.mktemp("note_reali") / "note.sqlite3"


def turno(ambiente, domanda):
    grafo, fuso_utente, _ = ambiente
    cronologia = esegui_turno(grafo, [], fuso_utente, domanda)  # sessione nuova
    chiamate = [c for m in cronologia if isinstance(m, AIMessage) for c in m.tool_calls]
    risultati = {m.tool_call_id: m for m in cronologia if isinstance(m, ToolMessage)}
    risposta = cronologia[-1]
    print(f"\n  domanda:   {domanda}")
    for c in chiamate:
        r = risultati.get(c["id"])
        print(f"  chiamata:  {c['name']} {c['args']} -> {r.status if r else '?'} {r.content if r else ''}")
    print(f"  risposta:  {risposta.text if isinstance(risposta, AIMessage) else risposta!r}")
    return chiamate, risultati, risposta


def test_aggiunta_ed_eliminazione_di_un_id_inesistente(archivio):
    with ambiente_reale(archivio_note=archivio) as ambiente:
        chiamate, risultati, _ = turno(ambiente, "Ricordami di consegnare il report venerdì")
        aggiunte = [c for c in chiamate if c["name"] == "add_note"]
        assert len(aggiunte) == 1, "serve una sola chiamata ad add_note"
        assert "report" in str(aggiunte[0]["args"].get("text", "")).casefold()
        assert risultati[aggiunte[0]["id"]].status == "success"

        chiamate, risultati, _ = turno(ambiente, "Elimina la nota 99")
        eliminazioni = [c for c in chiamate if c["name"] == "delete_note"]
        assert eliminazioni and int(eliminazioni[-1]["args"]["note_id"]) == 99
        assert risultati[eliminazioni[-1]["id"]].status == "error"
    note = ArchivioNote(archivio).elenca()["note"]
    assert len(note) == 1 and "report" in note[0]["testo"].casefold()


def test_le_note_restano_dopo_il_riavvio(archivio):
    with ambiente_reale(archivio_note=archivio) as ambiente:  # nuovo server sullo stesso archivio
        chiamate, risultati, risposta = turno(ambiente, "Quali note ho salvato?")
    elenchi = [json.loads(risultati[c["id"]].content) for c in chiamate
               if c["name"] == "list_notes" and risultati[c["id"]].status == "success"]
    assert elenchi and any("report" in n["testo"].casefold() for n in elenchi[-1]["note"])
    assert isinstance(risposta, AIMessage) and "report" in risposta.text.casefold()


def test_eliminazione_senza_id_solo_osservata(archivio):
    """Non dipende dal codice ma dal modello: si riporta se elenca le note prima di eliminare."""
    with ambiente_reale(archivio_note=archivio) as ambiente:
        chiamate, _, _ = turno(ambiente, "Elimina la nota sul report")
    nomi = [c["name"] for c in chiamate]
    elenca_prima = "list_notes" in nomi and ("delete_note" not in nomi or nomi.index("list_notes") < nomi.index("delete_note"))
    print(f"  osservazione: chiamate={nomi}; ha elencato prima di eliminare: {elenca_prima}")


def test_errore_controllato_note(archivio):
    """Slide 23: invocazione diretta, senza modello, con un ID inesistente."""
    with ambiente_reale(archivio_note=archivio) as (_, _, strumenti):
        errore = json.loads(next(s for s in strumenti if s.name == "delete_note").invoke({"note_id": 12345}))
    print(f"\n  errore controllato: {errore}")
    assert errore["tipo"] == "strumento" and "niente è stato eliminato" in errore["errore"]
