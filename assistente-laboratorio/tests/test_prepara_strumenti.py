"""prepara_strumenti con un comando del server personalizzato (usato dalle prove reali delle note)."""

import json
import sys

from assistente.avvio import prepara_strumenti
from assistente.configurazione import Configurazione


def test_comando_server_con_archivio_temporaneo(porta, tmp_path):
    archivio = tmp_path / "note.sqlite3"
    comando = [sys.executable, "-m", "server_mcp", "--porta", str(porta), "--note", str(archivio)]
    config = Configurazione("http://localhost:1234/v1", "finto", porta)
    with prepara_strumenti(config, log_server=tmp_path / "s.log", comando_server=comando) as strumenti:
        aggiungi = next(s for s in strumenti if s.name == "add_note")
        assert json.loads(aggiungi.invoke({"text": "prova"}))["id"] == 1
    assert archivio.exists()
