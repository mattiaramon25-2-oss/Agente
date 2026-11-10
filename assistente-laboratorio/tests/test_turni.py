"""Il turno in un thread: salvataggio solo dopo `fine`, anche con il browser scollegato."""

import logging
import threading

from assistente.sse import leggi_sse
from servizio_backend.turni import RegistroTurni, Turno
from tests.finti_backend import AgenteFinto, ArchivioInMemoria

STRUMENTI = [{"nome": "ora_attuale", "origine": "mcp", "argomenti": {}}]
FINE = ("fine", {"risposta": "Sono le 10.", "strumenti": STRUMENTI, "cronologia": [{"type": "ai"}]})
EVENTI = [("testo", {"pezzo": "Sono "}), ("strumento", {"nome": "ora_attuale", "origine": "mcp", "argomenti": {}}), FINE]


def prepara(eventi, **opzioni):
    archivio = ArchivioInMemoria()
    chat = archivio.crea_chat(None)
    agente = AgenteFinto(eventi, **opzioni)
    chiamate = []
    turno = Turno(chat["id"], "Che ore sono?", agente.apri_turno("Che ore sono?", [], ""), archivio,
                  lambda: chiamate.append(1))
    return archivio, chat["id"], turno, chiamate


def righe(blocchi):
    for blocco in blocchi:
        yield from blocco.splitlines()


def leggi(turno):
    turno.avvia()
    eventi = list(leggi_sse(righe(turno.eventi_sse())))
    turno.attendi(5)
    return eventi


def test_registro_turni():
    registro = RegistroTurni()
    assert registro.occupa(1) is True
    assert registro.occupa(1) is False
    assert registro.in_corso(1) is True and registro.in_corso(2) is False
    registro.libera(1)
    assert registro.in_corso(1) is False and registro.occupa(1) is True


def test_turno_ok_salva_e_finisce():
    archivio, chat_id, turno, chiamate = prepara(EVENTI)
    eventi = leggi(turno)
    assert [nome for nome, _ in eventi] == ["testo", "strumento", "fine"]
    fine = eventi[-1][1]
    assert fine["risposta"] == "Sono le 10." and fine["strumenti"] == STRUMENTI
    assert set(fine) == {"risposta", "strumenti", "messaggio_utente_id", "messaggio_assistente_id", "titolo"}
    messaggi = archivio.leggi_chat(chat_id)["messaggi"]
    assert [m["ruolo"] for m in messaggi] == ["utente", "assistente"]
    assert turno.esito == "ok" and turno.strumenti == ["ora_attuale"] and turno.scollegato is False
    assert chiamate == [1]


def test_errore_agente_non_salva():
    archivio, chat_id, turno, chiamate = prepara([("testo", {"pezzo": "x"}), ("errore", {"errore": "Modello spento.", "stato": 503})])
    eventi = leggi(turno)
    assert eventi[-1] == ("errore", {"errore": "Modello spento."})
    assert archivio.leggi_chat(chat_id)["messaggi"] == []
    assert turno.esito == "errore" and chiamate == [1]


def test_flusso_finito_senza_fine():
    archivio, chat_id, turno, chiamate = prepara([("testo", {"pezzo": "x"})])
    eventi = leggi(turno)
    assert eventi[-1][0] == "errore" and "non è stato salvato" in eventi[-1][1]["errore"]
    assert archivio.leggi_chat(chat_id)["messaggi"] == []
    assert chiamate == [1]


def test_agente_interrotto():
    archivio, chat_id, turno, chiamate = prepara(EVENTI, interrompi_dopo=1)
    eventi = leggi(turno)
    assert [nome for nome, _ in eventi] == ["testo", "errore"]
    assert archivio.leggi_chat(chat_id)["messaggi"] == [] and turno.esito == "errore"


def test_scollegato_salva_lo_stesso():
    cancello = threading.Event()
    archivio, chat_id, turno, chiamate = prepara(EVENTI, cancello=cancello)
    turno.avvia()
    flusso = turno.eventi_sse()
    assert next(flusso).startswith("event: testo")
    flusso.close()
    cancello.set()
    turno.attendi(5)
    assert len(archivio.leggi_chat(chat_id)["messaggi"]) == 2
    assert turno.scollegato is True and turno.esito == "ok" and chiamate == [1]


def test_salvataggio_fallito():
    cancello = threading.Event()
    archivio, chat_id, turno, chiamate = prepara(EVENTI, cancello=cancello)
    turno.avvia()
    archivio.spento = True
    cancello.set()
    eventi = list(leggi_sse(righe(turno.eventi_sse())))
    turno.attendi(5)
    assert eventi[-1][0] == "errore" and turno.esito == "errore" and chiamate == [1]
    archivio.spento = False
    assert archivio.leggi_chat(chat_id)["messaggi"] == []


def test_chiude_il_turno_dell_agente():
    agente = AgenteFinto(EVENTI)
    archivio = ArchivioInMemoria()
    chat = archivio.crea_chat(None)
    turno_agente = agente.apri_turno("d", [], "")
    turno = Turno(chat["id"], "d", turno_agente, archivio, lambda: None)
    leggi(turno)
    assert turno_agente.chiuso is True


def test_log_senza_testi(caplog):
    _, chat_id, turno, _ = prepara(EVENTI)
    with caplog.at_level(logging.INFO, logger="servizio_backend"):
        leggi(turno)
    assert f"richiesta endpoint=/chat/{chat_id}/messaggi chat_id={chat_id} esito=ok" in caplog.text
    assert 'strumenti=["ora_attuale"]' in caplog.text and "scollegato=false" in caplog.text and "durata=" in caplog.text
    assert "Che ore sono?" not in caplog.text and "Sono le 10." not in caplog.text
