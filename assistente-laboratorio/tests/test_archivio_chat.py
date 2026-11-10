"""Contratto dell'archivio delle chat: vale per ogni implementazione."""
import pytest

from servizio_backend.archivio import ArchivioPostgres, ChatInesistente, ProgettoInesistente
from servizio_backend.testi import TITOLO_PREDEFINITO
from tests.finti_backend import ArchivioInMemoria
from tests.postgres_prova import database_di_prova, svuota


@pytest.fixture(scope="module")
def database():
    """Un solo database PostgreSQL di prova per tutto il modulo."""
    with database_di_prova() as db:
        yield db


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=pytest.mark.docker)])
def archivio(request):
    if request.param == "memoria":
        a = ArchivioInMemoria()
        a.prepara()
        return a
    db = request.getfixturevalue("database")
    a = ArchivioPostgres(db.dsn)
    a.prepara()
    svuota(db.dsn)
    return a


def turno(archivio, chat_id, domanda, risposta, cronologia=None, strumenti=None):
    return archivio.salva_turno(
        chat_id, domanda, risposta, strumenti or [], cronologia or [{"ruolo": "x", "testo": domanda}]
    )


def test_progetti_crea_elenca_aggiorna(archivio):
    b = archivio.crea_progetto("beta", "")
    a = archivio.crea_progetto("Alfa", "istruzioni alfa")
    assert [p["nome"] for p in archivio.elenca_progetti()] == ["Alfa", "beta"]
    archivio.crea_chat(a["id"])
    archivio.crea_chat(a["id"])
    archivio.crea_chat(None)
    numeri = {p["nome"]: p["numero_chat"] for p in archivio.elenca_progetti()}
    assert numeri == {"Alfa": 2, "beta": 0}
    assert set(archivio.elenca_progetti()[0]) == {"id", "nome", "istruzioni", "numero_chat", "creato", "aggiornato"}

    aggiornato = archivio.aggiorna_progetto(a["id"], "Gamma", None)
    assert aggiornato["nome"] == "Gamma"
    assert aggiornato["istruzioni"] == "istruzioni alfa"
    assert aggiornato["aggiornato"] >= a["aggiornato"]
    aggiornato = archivio.aggiorna_progetto(a["id"], None, "nuove")
    assert (aggiornato["nome"], aggiornato["istruzioni"]) == ("Gamma", "nuove")
    assert archivio.leggi_progetto(b["id"])["nome"] == "beta"
    assert archivio.leggi_progetto(9999) is None
    assert archivio.aggiorna_progetto(9999, "x", None) is None


def test_chat_vuota_ha_titolo_predefinito(archivio):
    chat = archivio.crea_chat(None)
    assert chat["titolo"] == TITOLO_PREDEFINITO
    assert chat["messaggi"] == []
    assert archivio.elenca_chat()[0]["titolo"] == TITOLO_PREDEFINITO


def test_salva_turno_messaggi_titolo_cronologia(archivio):
    chat = archivio.crea_chat(None)
    primo = archivio.salva_turno(chat["id"], "Prima domanda", "Prima risposta", [], [{"n": 1}])
    assert primo["titolo"] == "Prima domanda"
    dopo_primo = archivio.leggi_chat(chat["id"])
    secondo = archivio.salva_turno(
        chat["id"], "Altra domanda", "Altra risposta", [{"nome": "ora"}], [{"n": 1}, {"n": 2}]
    )
    assert secondo["titolo"] == "Prima domanda"
    assert secondo["messaggio_utente_id"] > primo["messaggio_assistente_id"]

    letta = archivio.leggi_chat(chat["id"])
    assert letta["titolo"] == "Prima domanda"
    assert [(m["ruolo"], m["testo"]) for m in letta["messaggi"]] == [
        ("utente", "Prima domanda"),
        ("assistente", "Prima risposta"),
        ("utente", "Altra domanda"),
        ("assistente", "Altra risposta"),
    ]
    assert set(letta["messaggi"][0]) == {"id", "ruolo", "testo", "strumenti", "creato"}
    assert letta["messaggi"][3]["strumenti"] == [{"nome": "ora"}]
    assert archivio.contesto_turno(chat["id"]) == ([{"n": 1}, {"n": 2}], "")
    assert letta["aggiornata"] >= dopo_primo["aggiornata"] >= chat["aggiornata"]


def test_contesto_turno_chat_inesistente(archivio):
    assert archivio.contesto_turno(9999) is None


def test_salva_turno_chat_inesistente(archivio):
    with pytest.raises(ChatInesistente):
        archivio.salva_turno(9999, "d", "r", [], [])


def test_elenca_filtri(archivio):
    p = archivio.crea_progetto("P", "")
    fuori = archivio.crea_chat(None)
    dentro = archivio.crea_chat(p["id"])
    ultima = archivio.crea_chat(None)
    # senza turni l'ordine è per creazione: a parità di data, id decrescente
    assert [c["id"] for c in archivio.elenca_chat()] == [ultima["id"], dentro["id"], fuori["id"]]
    turno(archivio, fuori["id"], "ciao", "salve")
    elenco = archivio.elenca_chat()
    assert {c["id"] for c in elenco} == {fuori["id"], dentro["id"], ultima["id"]}
    chiavi = [(c["aggiornata"], c["id"]) for c in elenco]
    assert chiavi == sorted(chiavi, reverse=True)
    assert [c["id"] for c in archivio.elenca_chat(progetto_id=p["id"])] == [dentro["id"]]
    assert {c["id"] for c in archivio.elenca_chat(senza_progetto=True)} == {fuori["id"], ultima["id"]}
    assert set(archivio.elenca_chat()[0]) == {"id", "titolo", "progetto_id", "creata", "aggiornata"}


def test_sposta_chat(archivio):
    p = archivio.crea_progetto("P", "")
    chat = archivio.crea_chat(None)
    assert archivio.sposta_chat(chat["id"], p["id"])["progetto_id"] == p["id"]
    assert archivio.leggi_chat(chat["id"])["progetto_id"] == p["id"]
    assert archivio.sposta_chat(chat["id"], None)["progetto_id"] is None
    assert archivio.sposta_chat(9999, None) is None


def test_sposta_in_progetto_inesistente(archivio):
    chat = archivio.crea_chat(None)
    with pytest.raises(ProgettoInesistente):
        archivio.sposta_chat(chat["id"], 9999)
    with pytest.raises(ProgettoInesistente):
        archivio.crea_chat(9999)


def test_cancella_chat(archivio):
    chat = archivio.crea_chat(None)
    turno(archivio, chat["id"], "ciao", "salve")
    assert archivio.cancella_chat(chat["id"]) is True
    assert archivio.cancella_chat(chat["id"]) is False
    assert archivio.leggi_chat(chat["id"]) is None
    assert archivio.cerca("ciao") == []


def test_cancella_progetto_cancella_chat_e_messaggi(archivio):
    p = archivio.crea_progetto("P", "")
    chat = archivio.crea_chat(p["id"])
    turno(archivio, chat["id"], "domanda unica", "risposta unica")
    altra = archivio.crea_chat(None)
    assert archivio.cancella_progetto(p["id"]) is True
    assert archivio.cancella_progetto(p["id"]) is False
    assert archivio.leggi_progetto(p["id"]) is None
    assert archivio.leggi_chat(chat["id"]) is None
    assert archivio.cerca("unica") == []
    assert archivio.leggi_chat(altra["id"]) is not None


def test_ricerca_caratteri_speciali(archivio):
    chat = archivio.crea_chat(None)
    for testo in ["100% sicuro", "a_b", "c\\d", "Gatto"]:
        turno(archivio, chat["id"], testo, "ok")
    assert [r["estratto"] for r in archivio.cerca("%")] == ["100% sicuro"]
    assert [r["estratto"] for r in archivio.cerca("_")] == ["a_b"]
    assert [r["estratto"] for r in archivio.cerca("\\")] == ["c\\d"]
    trovati = archivio.cerca("GATTO")
    assert [r["estratto"] for r in trovati] == ["Gatto"]
    r = trovati[0]
    assert set(r) == {"chat_id", "titolo", "progetto_id", "messaggio_id", "ruolo", "estratto"}
    assert (r["chat_id"], r["ruolo"], r["titolo"]) == (chat["id"], "utente", "100% sicuro")


def test_ricerca_in_entrambi_i_ruoli(archivio):
    chat = archivio.crea_chat(None)
    turno(archivio, chat["id"], "domanda", "risposta con zebra")
    trovati = archivio.cerca("ZEBRA")
    assert [r["ruolo"] for r in trovati] == ["assistente"]


def test_ricerca_al_massimo_50_dai_piu_recenti(archivio):
    chat = archivio.crea_chat(None)
    for i in range(30):
        turno(archivio, chat["id"], f"cane {i}", f"cane risposta {i}")
    trovati = archivio.cerca("cane")
    assert len(trovati) == 50
    ids = [r["messaggio_id"] for r in trovati]
    assert ids == sorted(ids, reverse=True)
    tutti = [m["id"] for m in archivio.leggi_chat(chat["id"])["messaggi"]]
    assert ids == sorted(tutti, reverse=True)[:50]


def test_istruzioni_nel_contesto_turno(archivio):
    p = archivio.crea_progetto("P", "Rispondi sempre in rima.")
    chat = archivio.crea_chat(p["id"])
    assert archivio.contesto_turno(chat["id"]) == ([], "Rispondi sempre in rima.")
    archivio.aggiorna_progetto(p["id"], None, "Sii breve.")
    assert archivio.contesto_turno(chat["id"])[1] == "Sii breve."
    archivio.sposta_chat(chat["id"], None)
    assert archivio.contesto_turno(chat["id"])[1] == ""


@pytest.mark.docker
def test_postgres_turno_fallito_non_salva_nulla(database):
    """Il turno e' una transazione: se fallisce dopo i due INSERT, il rollback annulla anche i messaggi."""
    a = ArchivioPostgres(database.dsn)
    a.prepara()
    svuota(database.dsn)
    chat = a.crea_chat(None)
    a.salva_turno(chat["id"], "domanda iniziale", "risposta iniziale", [], [{"n": 1}])
    prima = a.leggi_chat(chat["id"])
    # Jsonb non sa scrivere un object(): l'errore arriva all'UPDATE, dopo i due INSERT gia' eseguiti.
    with pytest.raises(TypeError):
        a.salva_turno(chat["id"], "domanda zebra", "risposta zebra", [], [object()])
    dopo = a.leggi_chat(chat["id"])
    assert [m["testo"] for m in dopo["messaggi"]] == ["domanda iniziale", "risposta iniziale"]
    assert dopo["titolo"] == prima["titolo"]
    assert a.cerca("zebra") == []
    assert a.contesto_turno(chat["id"]) == ([{"n": 1}], "")
    # titolo ancora nullo: una chat vuota con turno fallito resta «Nuova chat»
    vuota = a.crea_chat(None)
    with pytest.raises(TypeError):
        a.salva_turno(vuota["id"], "domanda", "risposta", [], [object()])
    assert a.leggi_chat(vuota["id"])["titolo"] == TITOLO_PREDEFINITO
    assert a.leggi_chat(vuota["id"])["messaggi"] == []
