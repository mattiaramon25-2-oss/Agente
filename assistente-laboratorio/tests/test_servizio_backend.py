"""L'API del back-end con archivio in memoria e agente finto."""

import threading
import time

from fastapi.testclient import TestClient

from assistente.sse import leggi_sse
from servizio_backend.app import crea_app
from tests.finti_backend import AgenteFinto, ArchivioInMemoria

FINE = {"risposta": "Ciao!", "strumenti": [], "cronologia": [{"type": "ai", "data": {"content": "Ciao!"}}]}
EVENTI = [("testo", {"pezzo": "Ciao"}), ("testo", {"pezzo": "!"}), ("fine", FINE)]


def prepara(eventi=EVENTI, **opzioni):
    archivio = ArchivioInMemoria()
    agente = AgenteFinto(eventi, **opzioni)
    return TestClient(crea_app(archivio, agente)), archivio, agente


def turno(client, chat_id, messaggio="Ciao"):
    risposta = client.post(f"/chat/{chat_id}/messaggi", json={"messaggio": messaggio})
    return risposta, list(leggi_sse(risposta.text.splitlines()))


def test_salute():
    client, _, _ = prepara()
    assert client.get("/salute").json() == {"stato": "ok", "database": "ok", "agente": "ok"}
    client, _, _ = prepara(non_disponibile="spento")
    assert client.get("/salute").json()["agente"] == "non raggiungibile"


def test_database_spento_503():
    client, archivio, _ = prepara()
    archivio.spento = True
    for percorso in ("/chat", "/salute", "/progetti", "/ricerca?q=ab"):
        risposta = client.get(percorso)
        assert risposta.status_code == 503, percorso
        assert "non risponde" in risposta.json()["errore"]
    assert client.post("/chat", json={}).status_code == 503


def test_progetti():
    client, _, _ = prepara()
    creato = client.post("/progetti", json={"nome": "Zeta", "istruzioni": "Sii breve."})
    assert creato.status_code == 201
    assert creato.headers["content-type"] == "application/json; charset=utf-8"
    assert creato.json()["numero_chat"] == 0
    client.post("/progetti", json={"nome": "alfa"})
    assert [p["nome"] for p in client.get("/progetti").json()] == ["alfa", "Zeta"]
    pid = creato.json()["id"]
    assert client.get(f"/progetti/{pid}").json()["istruzioni"] == "Sii breve."
    assert client.patch(f"/progetti/{pid}", json={"nome": "Nuovo"}).json()["nome"] == "Nuovo"
    assert client.patch(f"/progetti/{pid}", json={}).json()["istruzioni"] == "Sii breve."
    assert client.get("/progetti/99").status_code == 404
    assert client.patch("/progetti/99", json={"nome": "x"}).status_code == 404
    assert client.delete("/progetti/99").status_code == 404
    risposta = client.delete(f"/progetti/{pid}")
    assert risposta.status_code == 204 and risposta.content == b""
    assert client.get(f"/progetti/{pid}").status_code == 404


def test_chat_e_filtro_per_progetto():
    client, _, _ = prepara()
    pid = client.post("/progetti", json={"nome": "P"}).json()["id"]
    libera = client.post("/chat", json={})
    assert libera.status_code == 201
    assert libera.json()["titolo"] == "Nuova chat" and libera.json()["messaggi"] == []
    assert client.post("/chat").status_code == 201  # corpo assente: nessun progetto
    dentro = client.post("/chat", json={"progetto_id": pid}).json()
    assert client.post("/chat", json={"progetto_id": 99}).status_code == 404
    assert len(client.get("/chat").json()) == 3
    assert [c["id"] for c in client.get(f"/chat?progetto={pid}").json()] == [dentro["id"]]
    assert len(client.get("/chat?progetto=nessuno").json()) == 2
    assert client.get("/chat?progetto=99").json() == []  # progetto sconosciuto: elenco vuoto
    assert client.get("/chat?progetto=abc").status_code == 400
    assert "progetto" in client.get("/chat?progetto=abc").json()["errore"]


def test_leggi_sposta_cancella_chat():
    client, _, _ = prepara()
    pid = client.post("/progetti", json={"nome": "P"}).json()["id"]
    cid = client.post("/chat", json={}).json()["id"]
    assert client.get(f"/chat/{cid}").json()["id"] == cid
    assert "cronologia" not in client.get(f"/chat/{cid}").json()
    assert client.get("/chat/99").status_code == 404
    assert client.patch(f"/chat/{cid}", json={"progetto_id": pid}).json()["progetto_id"] == pid
    assert client.patch(f"/chat/{cid}", json={"progetto_id": None}).json()["progetto_id"] is None
    assert client.patch(f"/chat/{cid}", json={"progetto_id": 99}).status_code == 404
    assert client.patch("/chat/99", json={"progetto_id": None}).status_code == 404
    assert client.patch(f"/chat/{cid}", json={}).status_code == 400  # progetto_id obbligatorio
    assert client.delete("/chat/99").status_code == 404
    risposta = client.delete(f"/chat/{cid}")
    assert risposta.status_code == 204 and risposta.content == b""
    assert client.get(f"/chat/{cid}").status_code == 404


def test_validazione_400_in_italiano():
    client, _, _ = prepara()
    casi = [
        client.post("/progetti", json={"nome": ""}),
        client.post("/progetti", json={"nome": "x" * 101}),
        client.post("/progetti", json={"nome": "ok", "istruzioni": "x" * 4001}),
        client.patch("/progetti/1", json={"nome": "x" * 101}),
        client.post("/progetti", json={}),
        client.get("/ricerca?q=a"),
        client.get("/ricerca"),
        client.get("/chat/abc"),
    ]
    for risposta in casi:
        assert risposta.status_code == 400
        assert risposta.json()["errore"].startswith("Richiesta non valida")
    assert client.post("/progetti", json={"nome": "x" * 100, "istruzioni": "y" * 4000}).status_code == 201


def test_messaggio_vuoto_400_prima_della_chat():
    client, _, agente = prepara()
    cid = client.post("/chat", json={}).json()["id"]
    for testo in ("", "   ", "﻿ \n"):
        assert client.post(f"/chat/{cid}/messaggi", json={"messaggio": testo}).status_code == 400
    assert client.post("/chat/99/messaggi", json={"messaggio": " "}).status_code == 400
    assert agente.chiamate == []


def test_chat_inesistente_404():
    client, _, agente = prepara()
    risposta = client.post("/chat/99/messaggi", json={"messaggio": "ciao"})
    assert risposta.status_code == 404 and "errore" in risposta.json()
    assert agente.chiamate == []


def test_turno_streaming_e_salvato():
    client, _, _ = prepara()
    cid = client.post("/chat", json={}).json()["id"]
    risposta, eventi = turno(client, cid, "Come stai oggi?")
    assert risposta.status_code == 200
    assert risposta.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert risposta.headers["cache-control"] == "no-cache"
    assert [nome for nome, _ in eventi] == ["testo", "testo", "fine"]
    fine = eventi[-1][1]
    assert fine["risposta"] == "Ciao!" and fine["titolo"] == "Come stai oggi?"
    chat = client.get(f"/chat/{cid}").json()
    assert chat["titolo"] == "Come stai oggi?"
    assert [(m["ruolo"], m["testo"]) for m in chat["messaggi"]] == [("utente", "Come stai oggi?"), ("assistente", "Ciao!")]
    assert [m["id"] for m in chat["messaggi"]] == [fine["messaggio_utente_id"], fine["messaggio_assistente_id"]]


def test_istruzioni_del_progetto_all_agente():
    client, _, agente = prepara()
    pid = client.post("/progetti", json={"nome": "P", "istruzioni": "Rispondi in rima."}).json()["id"]
    con = client.post("/chat", json={"progetto_id": pid}).json()["id"]
    senza = client.post("/chat", json={}).json()["id"]
    turno(client, con)
    turno(client, senza)
    assert agente.chiamate[0][2] == "Rispondi in rima."
    assert agente.chiamate[1][2] == ""


def test_seconda_domanda_usa_la_cronologia_salvata():
    client, _, agente = prepara()
    cid = client.post("/chat", json={}).json()["id"]
    turno(client, cid, "prima")
    turno(client, cid, "seconda")
    assert agente.chiamate[0][1] == []
    assert agente.chiamate[1][1] == FINE["cronologia"]
    assert agente.chiamate[1][0] == "seconda"


def test_errore_dell_agente_non_salva():
    client, _, _ = prepara([("testo", {"pezzo": "a"}), ("errore", {"errore": "modello spento"})])
    cid = client.post("/chat", json={}).json()["id"]
    _, eventi = turno(client, cid)
    assert eventi[-1] == ("errore", {"errore": "modello spento"})
    assert client.get(f"/chat/{cid}").json()["messaggi"] == []


def test_agente_non_disponibile_503():
    client, _, agente = prepara(non_disponibile="L'agente è spento.")
    cid = client.post("/chat", json={}).json()["id"]
    risposta = client.post(f"/chat/{cid}/messaggi", json={"messaggio": "ciao"})
    assert risposta.status_code == 503
    assert risposta.json() == {"errore": "L'agente è spento."}
    agente.non_disponibile = None  # riacceso: il registro è stato liberato
    risposta, eventi = turno(client, cid)
    assert risposta.status_code == 200 and eventi[-1][0] == "fine"


def test_database_spento_durante_il_contesto_libera_il_registro():
    client, archivio, _ = prepara()
    cid = client.post("/chat", json={}).json()["id"]
    archivio.spento = True
    assert client.post(f"/chat/{cid}/messaggi", json={"messaggio": "x"}).status_code == 503
    archivio.spento = False
    assert turno(client, cid)[1][-1][0] == "fine"


def test_409_durante_un_turno():
    cancello = threading.Event()
    client, _, agente = prepara(cancello=cancello)
    pid = client.post("/progetti", json={"nome": "P"}).json()["id"]
    occupata = client.post("/chat", json={"progetto_id": pid}).json()["id"]
    libera = client.post("/chat", json={}).json()["id"]
    esito = {}
    primo = threading.Thread(target=lambda: esito.update(r=turno(client, occupata)))
    primo.start()
    try:
        for _ in range(100):
            if agente.chiamate:
                break
            time.sleep(0.05)
        assert agente.chiamate
        secondo = client.post(f"/chat/{occupata}/messaggi", json={"messaggio": "ancora"})
        assert secondo.status_code == 409
        assert secondo.json() == {"errore": "C'è già una risposta in corso in questa chat."}
        for percorso in (f"/chat/{occupata}", f"/progetti/{pid}"):
            risposta = client.delete(percorso)
            assert risposta.status_code == 409
            assert risposta.json() == {"errore": "C'è un turno in corso in questa chat: aspetta che finisca."}
        assert client.get("/chat").status_code == 200
        assert client.delete(f"/chat/{libera}").status_code == 204
    finally:
        cancello.set()
        primo.join(10)
    assert esito["r"][1][-1][0] == "fine"
    assert client.delete(f"/progetti/{pid}").status_code == 204


def test_ricerca():
    client, _, _ = prepara()
    cid = client.post("/chat", json={}).json()["id"]
    turno(client, cid, "Cerco la parola Girasole")
    risultati = client.get("/ricerca?q=girasole").json()
    assert len(risultati) == 1
    assert set(risultati[0]) == {"chat_id", "titolo", "progetto_id", "messaggio_id", "ruolo", "estratto"}
    assert risultati[0]["chat_id"] == cid
    assert client.get("/ricerca?q=inesistente").json() == []
