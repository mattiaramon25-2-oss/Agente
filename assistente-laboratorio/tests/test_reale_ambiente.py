"""L'ambiente delle prove reali non usa mai l'archivio delle note dell'utente."""

from logica.note import PERCORSO_NOTE
from tests.reale import archivio_per_prove


def test_archivio_temporaneo_se_non_indicato():
    percorso = archivio_per_prove(None)
    assert percorso != PERCORSO_NOTE and percorso.name == "note.sqlite3" and percorso.parent.exists()


def test_archivio_indicato_rispettato(tmp_path):
    assert archivio_per_prove(tmp_path / "x.sqlite3") == tmp_path / "x.sqlite3"
