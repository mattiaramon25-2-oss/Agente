from datetime import datetime, timezone

import pytest

from logica.errori import ErroreStrumento
from logica.note import PERCORSO_NOTE, ArchivioNote

ISTANTE = datetime(2026, 11, 8, 9, 15, 2, tzinfo=timezone.utc)


@pytest.fixture
def archivio(tmp_path):
    return ArchivioNote(tmp_path / "sotto" / "note.sqlite3", adesso=lambda: ISTANTE)


def test_percorso_predefinito():
    assert PERCORSO_NOTE.parent.name == "archivio" and PERCORSO_NOTE.name == "note.sqlite3"


def test_nessun_file_prima_della_prima_operazione(tmp_path):
    percorso = tmp_path / "sotto" / "note.sqlite3"
    ArchivioNote(percorso)
    assert not percorso.exists() and not percorso.parent.exists()


def test_aggiungi(archivio):
    assert archivio.aggiungi("  consegnare il report venerdì ") == {
        "id": 1, "testo": "consegnare il report venerdì", "creata": "2026-11-08T09:15:02+00:00", "esito": "nota creata"}


def test_elenco_dalla_piu_recente_e_limite(archivio):
    for t in ("a", "b", "c"):
        archivio.aggiungi(t)
    r = archivio.elenca("2")
    assert [n["testo"] for n in r["note"]] == ["c", "b"] and r["totale_archivio"] == 3
    assert r["note"][0] == {"id": 3, "testo": "c", "creata": "2026-11-08T09:15:02+00:00"}


def test_limit_predefinito_e_nullo(archivio):
    for i in range(12):
        archivio.aggiungi(f"n{i}")
    assert len(archivio.elenca()["note"]) == 10 and len(archivio.elenca(None)["note"]) == 10


def test_archivio_vuoto(archivio):
    assert archivio.elenca() == {"note": [], "totale_archivio": 0}


def test_elimina(archivio):
    archivio.aggiungi("a")
    archivio.aggiungi("b")
    assert archivio.elimina(1) == {"id": 1, "testo": "a", "esito": "nota eliminata"}
    assert [n["id"] for n in archivio.elenca()["note"]] == [2]


def test_id_inesistente_non_elimina(archivio):
    archivio.aggiungi("a")
    with pytest.raises(ErroreStrumento, match="Nessuna nota con ID 99: niente è stato eliminato"):
        archivio.elimina(99)
    assert archivio.elenca()["totale_archivio"] == 1


def test_id_mai_riusati(archivio):
    archivio.aggiungi("a")
    archivio.elimina(1)
    assert archivio.aggiungi("b")["id"] == 2


def test_id_come_testo(archivio):
    archivio.aggiungi("a")
    assert archivio.elimina("1")["id"] == 1


def test_persistenza(archivio):
    archivio.aggiungi("resta")
    assert ArchivioNote(archivio.percorso).elenca()["note"][0]["testo"] == "resta"


@pytest.mark.parametrize("testo, frammento", [("", "vuoto"), ("   ", "vuoto"), (None, "vuoto"), ("x" * 501, "500")])
def test_testo_non_valido(archivio, testo, frammento):
    with pytest.raises(ErroreStrumento, match=frammento):
        archivio.aggiungi(testo)
    assert archivio.elenca()["totale_archivio"] == 0


def test_testo_di_500_caratteri(archivio):
    assert len(archivio.aggiungi("x" * 500)["testo"]) == 500


@pytest.mark.parametrize("limit", [0, 51, True, "dieci"])
def test_limit_non_valido(archivio, limit):
    with pytest.raises(ErroreStrumento, match="tra 1 e 50"):
        archivio.elenca(limit)


@pytest.mark.parametrize("note_id", [0, -1, True, 1.5, "uno", None])
def test_note_id_non_valido(archivio, note_id):
    with pytest.raises(ErroreStrumento, match="intero positivo"):
        archivio.elimina(note_id)


def test_archivio_non_accessibile(tmp_path):
    (tmp_path / "file").write_text("non una cartella")
    with pytest.raises(ErroreStrumento, match="Archivio delle note non accessibile"):
        ArchivioNote(tmp_path / "file" / "note.sqlite3").aggiungi("a")


def test_database_corrotto(tmp_path):
    percorso = tmp_path / "note.sqlite3"
    percorso.write_bytes(b"questo non e' un database sqlite" * 10)
    with pytest.raises(ErroreStrumento, match="Archivio delle note non accessibile"):
        ArchivioNote(percorso).elenca()
