"""Pezzi comuni delle prove con Docker Compose, senza psycopg (si importa anche dove non si carica)."""
import socket
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent.parent
# Valori finti per le variabili `:?` degli altri servizi: Compose controlla tutto il file.
ENV_FINTO = {
    "MCP_PORTA": "8765",
    "VARIANTE_CALCOLATRICE": "mcp",
    "VARIANTE_SCADENZE": "mcp",
    "AGENTE_PORTA": "8767",
    "LMSTUDIO_BASE_URL_DOCKER": "http://host.docker.internal:1234/v1",
    "LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1",
    "LMSTUDIO_MODEL": "prova",
}
LIMITE_COMPOSE = 300


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
