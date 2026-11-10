"""ArchivioPostgres senza database raggiungibile: nessun Docker, una porta chiusa su 127.0.0.1."""
import socket

import pytest
from psycopg.conninfo import make_conninfo

from servizio_backend.archivio import ArchivioPostgres, DatabaseNonRaggiungibile


@pytest.fixture
def archivio_spento():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    # La porta e' stata liberata: nessuno ascolta.
    dsn = make_conninfo(host="127.0.0.1", port=porta, user="u", password="p", dbname="d", connect_timeout=1)
    return ArchivioPostgres(dsn)


def test_controlla_con_database_spento(archivio_spento):
    with pytest.raises(DatabaseNonRaggiungibile, match=r"^il database PostgreSQL non risponde \("):
        archivio_spento.controlla()


def test_metodo_dati_con_database_spento(archivio_spento):
    with pytest.raises(DatabaseNonRaggiungibile, match=r"^il database PostgreSQL non risponde \("):
        archivio_spento.elenca_progetti()
