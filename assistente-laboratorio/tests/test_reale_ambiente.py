"""L'ambiente delle prove reali non usa mai l'archivio delle note dell'utente."""

from logica.note import PERCORSO_NOTE
from tests.reale import archivio_per_prove


def test_archivio_temporaneo_se_non_indicato():
    from tests.reale import rimuovi_archivio_temporaneo

    percorso = archivio_per_prove(None)
    try:
        assert percorso != PERCORSO_NOTE and percorso.name == "note.sqlite3" and percorso.parent.exists()
    finally:
        rimuovi_archivio_temporaneo(percorso)


def test_archivio_indicato_rispettato(tmp_path):
    assert archivio_per_prove(tmp_path / "x.sqlite3") == tmp_path / "x.sqlite3"


def test_archivio_temporaneo_rimosso_dopo_l_uso():
    from tests.reale import archivio_per_prove, rimuovi_archivio_temporaneo

    percorso = archivio_per_prove(None)
    percorso.write_text("x", encoding="utf-8")
    rimuovi_archivio_temporaneo(percorso)
    assert not percorso.parent.exists()


def test_con_client_non_lascia_cartelle_temporanee(monkeypatch, tmp_path):
    import tempfile

    from tests.test_server_mcp import con_client

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    con_client(lambda c: c.list_tools())
    assert list(tmp_path.iterdir()) == []
