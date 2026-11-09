"""Ogni pacchetto importato direttamente dal codice ha la versione fissata in requirements.txt."""

from pathlib import Path

REQUISITI = Path(__file__).resolve().parent.parent / "requirements.txt"


def test_pacchetti_usati_direttamente_fissati():
    fissati = {riga.split("==")[0].strip().lower() for riga in REQUISITI.read_text(encoding="utf-8").splitlines() if "==" in riga}
    for pacchetto in ("pydantic", "starlette", "httpx", "fastapi", "uvicorn", "fastmcp", "mcp", "langchain-mcp-adapters"):
        assert pacchetto in fissati, pacchetto
